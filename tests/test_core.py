"""离线核心测试：不访问用户账号、浏览器会话或哔哩哔哩网站。"""
import asyncio
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

import db
from bilibili_client import BilibiliBrowserClient, parse_bvid, parse_mid


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.original_path = db.DB_PATH
        db.DB_PATH = Path(self.folder.name) / "bili-test.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.folder.cleanup()

    def test_parsers_and_view_mapping(self):
        self.assertEqual(parse_bvid("分享 https://www.bilibili.com/video/BV1xx411c7mD"), "BV1XX411C7MD")
        self.assertEqual(parse_mid("https://space.bilibili.com/123456"), "123456")
        video = BilibiliBrowserClient._video_from_view({
            "bvid": "BV1xx411c7mD", "aid": 7, "title": "<em>测试</em> 标题", "pubdate": 1700000000,
            "owner": {"name": "测试UP", "mid": 8},
            "stat": {"view": 1, "like": 2, "reply": 3, "share": 4, "favorite": 5},
            "pages": [{"cid": 9, "page": 1, "part": "第一P"}],
        })
        self.assertEqual(video["title"], "测试 标题")
        self.assertEqual((video["view_count"], video["like_count"], video["comment_count"], video["share_count"], video["favorite_count"]), (1, 2, 3, 4, 5))
        self.assertEqual(video["pages"][0]["part"], "第一P")

    def test_result_storage_and_xlsx(self):
        db.upsert_result("single", {
            "bvid": "BV1xx411c7mD", "aid": "7", "author_name": "测试UP", "author_mid": "8",
            "title": "测试标题", "video_url": "https://www.bilibili.com/video/BV1xx411c7mD", "published_at": 1700000000,
            "view_count": 10, "like_count": 20, "comment_count": 30, "share_count": 40, "favorite_count": 50,
            "pages": [{"cid": 1, "page": 1, "part": "P1"}],
        }, input_url="https://www.bilibili.com/video/BV1xx411c7mD")
        rows = db.list_results("single")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pages"][0]["cid"], 1)
        from web import app as web_app
        payload = asyncio.run(web_app.api_single_results())
        self.assertEqual(payload["rows"][0]["bvid"], "BV1xx411c7mD")
        workbook = load_workbook(BytesIO(web_app._xlsx_bytes("single")))
        worksheet = workbook.active
        self.assertIn("作者ID", [cell.value for cell in worksheet[1]])
        self.assertIn("评论数", [cell.value for cell in worksheet[1]])
        self.assertEqual(worksheet.cell(2, 2).value, "8")

    def test_single_result_keeps_duplicate_bvids_in_input_order(self):
        first = {
            "bvid": "BV1xx411c7mD", "aid": "7", "author_name": "测试UP", "author_mid": "8",
            "title": "第一次", "video_url": "https://www.bilibili.com/video/BV1xx411c7mD", "published_at": 1700000000,
            "view_count": 1, "like_count": 2, "comment_count": 3, "share_count": 4, "favorite_count": 5, "pages": [],
        }
        second = dict(first, title="第二次")
        db.upsert_result("single", first, input_url="first", input_order=0)
        db.upsert_result("single", second, input_url="second", input_order=1)
        rows = db.list_results("single")
        self.assertEqual([row["input_url"] for row in rows], ["first", "second"])
        self.assertEqual([row["title"] for row in rows], ["第一次", "第二次"])

    def test_single_link_normalization_keeps_duplicate_lines(self):
        from web import app as web_app
        links, invalid = web_app._normalise_lines(
            "https://www.bilibili.com/video/BV1xx411c7mD\nhttps://b23.tv/abcd\nhttps://www.bilibili.com/video/BV1xx411c7mD",
            web_app.SINGLE_URL_PATTERN,
            deduplicate=False,
        )
        self.assertEqual(invalid, [])
        self.assertEqual(links, [
            "https://www.bilibili.com/video/BV1xx411c7mD",
            "https://b23.tv/abcd",
            "https://www.bilibili.com/video/BV1xx411c7mD",
        ])

    def test_single_invalid_link_is_rejected_before_browser(self):
        from web import app as web_app
        response = asyncio.run(web_app.api_single_extract({"urls": "not a bilibili link"}))
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
