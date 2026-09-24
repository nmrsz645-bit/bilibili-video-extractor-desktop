"""暂停提取的离线测试：不访问浏览器资料或网络。"""
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import db
from bilibili_client import BilibiliBrowserClient
from pause_control import PauseGate


class FakePage:
    url = "https://www.bilibili.com/"

    async def goto(self, url, **_kwargs):
        self.url = url


class FakeContext:
    async def close(self):
        pass


class FakePlaywright:
    async def stop(self):
        pass


class PauseTests(unittest.IsolatedAsyncioTestCase):
    async def test_gate_blocks_until_resume(self):
        gate = PauseGate()
        gate.pause()
        self.assertFalse(gate.waiting)
        checkpoint = asyncio.create_task(gate.checkpoint())
        await asyncio.sleep(0.08)
        self.assertFalse(checkpoint.done())
        self.assertTrue(gate.waiting)
        gate.resume()
        await asyncio.wait_for(checkpoint, 1)
        self.assertFalse(gate.waiting)

    async def test_repeated_pause_keeps_waiting_status(self):
        gate = PauseGate()
        gate.pause()
        checkpoint = asyncio.create_task(gate.checkpoint())
        try:
            await asyncio.sleep(0.08)
            self.assertTrue(gate.waiting)
            gate.pause()
            await asyncio.sleep(0.15)
            self.assertTrue(gate.waiting)
            self.assertFalse(checkpoint.done())
        finally:
            gate.resume()
            await asyncio.wait_for(checkpoint, 1)

    async def test_each_extraction_stops_between_videos_and_resumes(self):
        for source in ("creator", "topic", "single"):
            with self.subTest(source=source):
                gate = PauseGate()
                client = BilibiliBrowserClient()
                page = FakePage()
                seen = []

                async def fake_launch():
                    return FakePlaywright(), FakeContext(), page

                async def fake_wbi(_page, _endpoint, _params):
                    if source == "creator":
                        return {"data": {"list": {"vlist": [
                            {"bvid": "BV1", "created": 10}, {"bvid": "BV2", "created": 9},
                        ]}}}
                    return {"data": {"result": [
                        {"bvid": "BV1", "pubdate": 10}, {"bvid": "BV2", "pubdate": 9},
                    ]}}

                async def fake_view(_page, bvid):
                    return {"bvid": bvid}

                async def fake_resolve(_page, raw_url):
                    return raw_url

                def on_video(*args):
                    seen.append(args[-1]["bvid"])
                    if len(seen) == 1:
                        gate.pause()

                client._launch = fake_launch
                client._wbi_fetch = fake_wbi
                client._view = fake_view
                client._resolve_bvid = fake_resolve
                if source == "creator":
                    task = asyncio.create_task(client.fetch_creator_videos(
                        "1234", start_ts=None, end_ts=None, top_count=None,
                        on_video=on_video, pause_gate=gate,
                    ))
                elif source == "topic":
                    task = asyncio.create_task(client.fetch_search_videos(
                        "测试", start_ts=None, end_ts=None, max_results=2,
                        on_video=on_video, pause_gate=gate,
                    ))
                else:
                    task = asyncio.create_task(client.fetch_single_videos(
                        ["BV1", "BV2"], on_video=on_video, pause_gate=gate,
                    ))
                try:
                    await asyncio.sleep(0.08)
                    self.assertEqual(seen, ["BV1"])
                    self.assertFalse(task.done())
                finally:
                    gate.resume()
                await asyncio.wait_for(task, 1)
                self.assertEqual(seen, ["BV1", "BV2"])

    async def test_pause_endpoint_keeps_task_running_until_resumed(self):
        from web import app as web_app

        state = web_app._creator_state
        original = state.copy()
        try:
            state.update({"running": True, "paused": False})
            response = await web_app.api_pause_extract("creator")
            self.assertTrue(response["paused"])
            self.assertTrue(state["running"])
            self.assertTrue(state["paused"])
            self.assertTrue(web_app._is_busy())
            self.assertFalse((await web_app.api_creator_status())["pause_waiting"])
            response = await web_app.api_resume_extract("creator")
            self.assertFalse(response["paused"])
            self.assertFalse(state["paused"])
        finally:
            web_app._pause_gates["creator"].resume()
            state.clear()
            state.update(original)

    async def test_each_extraction_page_exposes_pause_and_resume_controls(self):
        from web import app as web_app

        for source in ("creator", "topic", "single"):
            with self.subTest(source=source):
                html = web_app.render(f"{source}.html").body.decode("utf-8")
                self.assertIn('id="pause-extract"', html)
                self.assertIn('onclick="togglePause()"', html)
                self.assertIn(f"/api/extract/{source}/", html)

    async def test_single_api_keeps_partial_results_and_resumes_same_job(self):
        from web import app as web_app

        first = "BV1xx411c7mD"
        second = "BV1eUty6xErd"
        urls = [f"https://www.bilibili.com/video/{value}" for value in (first, second)]
        reached_first = threading.Event()
        continue_work = threading.Event()
        original_path = db.DB_PATH

        class FakeClient:
            async def fetch_single_videos(self, input_urls, on_video, on_progress, pause_gate):
                videos = []
                for index, (url, bvid) in enumerate(zip(input_urls, (first, second)), start=1):
                    if index == 2:
                        await asyncio.to_thread(continue_work.wait)
                        await pause_gate.checkpoint()
                    video = {"bvid": bvid, "title": bvid, "pages": []}
                    videos.append(video)
                    on_video(index, url, video)
                    on_progress(index, url, None)
                    if index == 1:
                        reached_first.set()
                return videos, []

        with tempfile.TemporaryDirectory() as folder:
            db.DB_PATH = Path(folder) / "pause-test.db"
            db.init_db()
            try:
                with patch.object(web_app, "BilibiliBrowserClient", FakeClient):
                    job = asyncio.create_task(web_app.api_single_extract({"urls": "\n".join(urls)}))
                    try:
                        self.assertTrue(await asyncio.to_thread(reached_first.wait, 2))
                        self.assertTrue((await web_app.api_pause_extract("single"))["paused"])
                        continue_work.set()
                        await asyncio.sleep(0.15)
                        self.assertTrue((await web_app.api_single_status())["pause_waiting"])
                        self.assertEqual([row["bvid"] for row in db.list_results("single")], [first])
                        self.assertFalse(job.done())
                    finally:
                        continue_work.set()
                        await web_app.api_resume_extract("single")
                    result = await asyncio.wait_for(job, 2)
                    self.assertEqual(result["total"], 2)
                    self.assertEqual([row["bvid"] for row in db.list_results("single")], [first, second])
            finally:
                db.DB_PATH = original_path

    async def test_cancelled_http_request_does_not_block_paused_worker(self):
        from web import app as web_app

        started = threading.Event()
        released = threading.Event()

        def worker():
            started.set()
            released.wait()
            return 1

        task = asyncio.create_task(web_app._run_in_thread(worker))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            task.cancel()
            await asyncio.sleep(0.05)
            self.assertFalse(task.done())
        finally:
            released.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)


if __name__ == "__main__":
    unittest.main()
