"""通过可见、独立的 Chromium 登录会话读取哔哩哔哩公开视频资料。"""
import asyncio
import hashlib
import logging
import re
import time
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

from playwright.async_api import Page, async_playwright

from config import SESSION_DIR, USER_AGENT

logger = logging.getLogger(__name__)


async def _checkpoint(pause_gate):
    if pause_gate is not None:
        await pause_gate.checkpoint()

_BV_RE = re.compile(r"\b(BV[0-9A-Za-z]{10})\b")
_MID_RE = re.compile(r"space\.bilibili\.com/(\d+)|\b(\d{4,})\b", re.IGNORECASE)
_WBI_MIXIN_TABLE = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def parse_bvid(value: str) -> str | None:
    match = _BV_RE.search(value or "")
    return match.group(1) if match else None


def parse_mid(value: str) -> str | None:
    match = _MID_RE.search(value or "")
    if not match:
        return None
    return match.group(1) or match.group(2)


def clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", unescape(value or ""))).strip()


class BilibiliBrowserClient:
    """每次任务复用一个可见浏览器，所有请求使用该登录态。"""

    def __init__(self):
        self._wbi_mixin_key = ""

    async def open_login(self, hold_ms: int = 600_000):
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR), headless=False,
                viewport={"width": 1440, "height": 900}, user_agent=USER_AGENT, locale="zh-CN",
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.bilibili.com/", wait_until="domcontentloaded")
            await page.wait_for_timeout(hold_ms)
            await context.close()

    async def _context(self):
        """Compatibility placeholder; contexts are managed inside each public operation."""
        raise RuntimeError("请使用 fetch_* 方法")

    async def _json_fetch(self, page: Page, url: str) -> dict:
        """在已登录页面上下文中 fetch，保留 Cookie、Referer 与浏览器指纹。"""
        return await page.evaluate("""async (url) => {
            const res = await fetch(url, {credentials: 'include'});
            const text = await res.text();
            try { return JSON.parse(text); } catch (_) { return {code: -1, message: text.slice(0, 180)}; }
        }""", url)

    async def _ensure_wbi_key(self, page: Page):
        if self._wbi_mixin_key:
            return
        payload = await self._json_fetch(page, "https://api.bilibili.com/x/web-interface/nav")
        data = payload.get("data", {}) or {}
        wbi_img = data.get("wbi_img", {}) or {}
        img = Path(urlparse(wbi_img.get("img_url", "")).path).stem
        sub = Path(urlparse(wbi_img.get("sub_url", "")).path).stem
        raw = img + sub
        if len(raw) < 64:
            raise RuntimeError("未取得哔哩哔哩 WBI 签名密钥，请先在浏览器完成登录或刷新页面")
        self._wbi_mixin_key = "".join(raw[index] for index in _WBI_MIXIN_TABLE)[:32]

    async def _wbi_fetch(self, page: Page, endpoint: str, params: dict) -> dict:
        await self._ensure_wbi_key(page)
        values = {key: str(value) for key, value in params.items() if value not in (None, "")}
        values["wts"] = str(int(time.time()))
        values = {key: re.sub(r"[!'()*]", "", value) for key, value in values.items()}
        query = urlencode(sorted(values.items()))
        values["w_rid"] = hashlib.md5((query + self._wbi_mixin_key).encode("utf-8")).hexdigest()
        payload = await self._json_fetch(page, f"https://api.bilibili.com{endpoint}?{urlencode(values)}")
        if int(payload.get("code", -1) if payload.get("code") is not None else -1) != 0:
            raise RuntimeError(str(payload.get("message") or "哔哩哔哩接口返回异常"))
        return payload

    @staticmethod
    def _video_from_view(data: dict) -> dict:
        stat = data.get("stat", {}) or {}
        owner = data.get("owner", {}) or {}
        pages = data.get("pages", []) or []
        bvid = str(data.get("bvid", "") or "")
        return {
            "bvid": bvid,
            "aid": str(data.get("aid", "") or ""),
            "author_name": str(owner.get("name", "") or ""),
            "author_mid": str(owner.get("mid", "") or ""),
            "title": clean_title(data.get("title", "")),
            "video_url": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
            "published_at": int(data.get("pubdate", 0) or 0),
            "view_count": int(stat.get("view", 0) or 0),
            "like_count": int(stat.get("like", 0) or 0),
            "comment_count": int(stat.get("reply", 0) or 0),
            "share_count": int(stat.get("share", 0) or 0),
            "favorite_count": int(stat.get("favorite", 0) or 0),
            "pages": [{"cid": item.get("cid"), "page": item.get("page"), "part": item.get("part", "")}
                      for item in pages],
        }

    async def _resolve_bvid(self, page: Page, raw_url: str) -> str:
        bvid = parse_bvid(raw_url)
        if bvid:
            return bvid
        await page.goto(raw_url, wait_until="domcontentloaded", timeout=30_000)
        bvid = parse_bvid(page.url)
        if bvid:
            return bvid
        text = await page.title()
        bvid = parse_bvid(text)
        if bvid:
            return bvid
        raise ValueError("无法识别 BV 号，请粘贴哔哩哔哩视频链接")

    async def _view(self, page: Page, bvid: str) -> dict:
        payload = await self._json_fetch(page, f"https://api.bilibili.com/x/web-interface/view?bvid={quote(bvid)}")
        if int(payload.get("code", -1) if payload.get("code") is not None else -1) != 0:
            raise RuntimeError(str(payload.get("message") or "未读取到视频资料"))
        return self._video_from_view(payload.get("data", {}) or {})

    async def _launch(self):
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        p = await async_playwright().start()
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR), headless=False,
            viewport={"width": 1440, "height": 900}, user_agent=USER_AGENT, locale="zh-CN",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        return p, context, page

    async def read_profile(self, mid: str) -> tuple[dict | None, str | None]:
        return (await self.read_profiles([mid])).get(mid, (None, "未读取到 UP 主资料"))

    async def read_profiles(self, mids: list[str]) -> dict[str, tuple[dict | None, str | None]]:
        p, context, page = await self._launch()
        results: dict[str, tuple[dict | None, str | None]] = {}
        try:
            for mid in dict.fromkeys(mids):
                try:
                    await page.goto(f"https://space.bilibili.com/{mid}", wait_until="domcontentloaded", timeout=30_000)
                    relation = await self._json_fetch(page, f"https://api.bilibili.com/x/relation/stat?vmid={mid}")
                    info = await self._wbi_fetch(page, "/x/space/wbi/acc/info", {"mid": mid})
                    user = info.get("data", {}) or {}
                    stats = relation.get("data", {}) or {}
                    results[mid] = ({
                        "nickname": user.get("name", ""), "avatar_url": user.get("face", ""),
                        "follower_count": int(stats.get("follower", 0) or 0),
                        "following_count": int(stats.get("following", 0) or 0),
                    }, None)
                except Exception as exc:
                    results[mid] = (None, str(exc))
            return results
        finally:
            await context.close()
            await p.stop()

    async def fetch_creator_videos(self, mid: str, *, start_ts: int | None, end_ts: int | None,
                                    top_count: int | None, on_video=None, on_progress=None, pause_gate=None) -> list[dict]:
        await _checkpoint(pause_gate)
        p, context, page = await self._launch()
        videos: list[dict] = []
        try:
            await _checkpoint(pause_gate)
            await page.goto(f"https://space.bilibili.com/{mid}", wait_until="domcontentloaded", timeout=30_000)
            page_number = 1
            while True:
                await _checkpoint(pause_gate)
                payload = await self._wbi_fetch(page, "/x/space/wbi/arc/search", {
                    "mid": mid, "pn": page_number, "ps": 30, "order": "pubdate",
                })
                page_data = payload.get("data", {}) or {}
                items = ((page_data.get("list", {}) or {}).get("vlist", []) or [])
                if not items:
                    break
                stop = False
                for item in items:
                    await _checkpoint(pause_gate)
                    published = int(item.get("created", 0) or 0)
                    if top_count is None:
                        if start_ts is not None and published < start_ts:
                            stop = True
                            break
                        if end_ts is not None and published > end_ts:
                            continue
                    bvid = str(item.get("bvid", "") or "")
                    if not bvid:
                        continue
                    try:
                        video = await self._view(page, bvid)
                    except Exception as exc:
                        logger.warning("读取 BV%s 失败: %s", bvid, exc)
                        if on_progress:
                            on_progress(len(videos), bvid, str(exc))
                        continue
                    await _checkpoint(pause_gate)
                    videos.append(video)
                    if on_video:
                        on_video(video)
                    if on_progress:
                        on_progress(len(videos), bvid, None)
                    if top_count is not None and len(videos) >= top_count:
                        stop = True
                        break
                if stop or len(items) < 30:
                    break
                page_number += 1
            return videos
        finally:
            await context.close()
            await p.stop()

    async def fetch_search_videos(self, raw_topic: str, *, start_ts: int | None, end_ts: int | None,
                                  max_results: int, on_video=None, on_progress=None, pause_gate=None) -> tuple[str, list[dict]]:
        await _checkpoint(pause_gate)
        p, context, page = await self._launch()
        videos: list[dict] = []
        try:
            query = (raw_topic or "").strip()
            if query.startswith(("http://", "https://")):
                await _checkpoint(pause_gate)
                await page.goto(query, wait_until="domcontentloaded", timeout=30_000)
                query = await page.evaluate("""() => document.querySelector('meta[name=keywords]')?.content || document.title""")
            query = clean_title(query).lstrip("#＃").replace("_哔哩哔哩", "").strip()
            if not query:
                raise ValueError("未能从话题链接识别关键词，请直接输入话题名或搜索关键词")
            await _checkpoint(pause_gate)
            await page.goto(f"https://search.bilibili.com/video?keyword={quote(query)}", wait_until="domcontentloaded")
            page_number = 1
            while len(videos) < max_results:
                await _checkpoint(pause_gate)
                payload = await self._wbi_fetch(page, "/x/web-interface/wbi/search/type", {
                    "search_type": "video", "keyword": query, "page": page_number, "page_size": 42, "order": "pubdate",
                })
                items = (payload.get("data", {}) or {}).get("result", []) or []
                if not items:
                    break
                for item in items:
                    await _checkpoint(pause_gate)
                    published = int(item.get("pubdate", 0) or 0)
                    if start_ts is not None and published < start_ts:
                        continue
                    if end_ts is not None and published > end_ts:
                        continue
                    bvid = str(item.get("bvid", "") or "")
                    if not bvid:
                        continue
                    try:
                        video = await self._view(page, bvid)
                    except Exception as exc:
                        if on_progress:
                            on_progress(len(videos), bvid, str(exc))
                        continue
                    await _checkpoint(pause_gate)
                    videos.append(video)
                    if on_video:
                        on_video(video)
                    if on_progress:
                        on_progress(len(videos), bvid, None)
                    if len(videos) >= max_results:
                        break
                if len(items) < 42:
                    break
                page_number += 1
            return query, videos
        finally:
            await context.close()
            await p.stop()

    async def fetch_single_videos(self, urls: list[str], on_video=None, on_progress=None,
                                  pause_gate=None) -> tuple[list[dict], list[dict]]:
        await _checkpoint(pause_gate)
        p, context, page = await self._launch()
        videos, failures = [], []
        try:
            for position, raw_url in enumerate(urls, start=1):
                await _checkpoint(pause_gate)
                try:
                    bvid = await self._resolve_bvid(page, raw_url)
                    await _checkpoint(pause_gate)
                    hostname = (urlparse(page.url).hostname or "").lower()
                    if hostname not in {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}:
                        await page.goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=30_000)
                    video = await self._view(page, bvid)
                    await _checkpoint(pause_gate)
                    videos.append(video)
                    if on_video:
                        on_video(position, raw_url, video)
                    if on_progress:
                        on_progress(position, raw_url, None)
                except Exception as exc:
                    failures.append({"input": raw_url, "error": str(exc)})
                    if on_progress:
                        on_progress(position, raw_url, str(exc))
            return videos, failures
        finally:
            await context.close()
            await p.stop()
