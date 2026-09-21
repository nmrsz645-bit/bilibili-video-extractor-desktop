"""哔哩哔哩下载：yt-dlp 选择当前账号可访问的最佳音视频并由 ffmpeg 合并。"""
import asyncio
import logging
import os
import shutil
import threading
from pathlib import Path

from config import APP_DIR, SESSION_DIR, USER_AGENT

logger = logging.getLogger(__name__)


def _safe_title(value: str) -> str:
    import re
    return (re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (value or "").strip()).rstrip(". ") or "哔哩哔哩视频")[:120]


def _ffmpeg_location() -> str:
    """必须找到 ffmpeg 才允许下载，避免最高画质的音视频分离后留下半成品。"""
    candidates = [
        os.environ.get("BILIBILI_FFMPEG_LOCATION", ""),
        str(APP_DIR / "tools" / "ffmpeg" / "bin"),
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / "ffmpeg.exe").is_file():
            return candidate
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return str(Path(system_ffmpeg).parent)
    raise RuntimeError("未找到 ffmpeg 音视频合并组件；请使用包含 ffmpeg 的完整程序包")


async def _export_cookie_file(path: Path):
    from playwright.async_api import async_playwright
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR), headless=True, user_agent=USER_AGENT, locale="zh-CN",
        )
        try:
            cookies = await context.cookies(["https://www.bilibili.com", "https://api.bilibili.com"])
        finally:
            await context.close()
    lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookies:
        domain = cookie.get("domain", "")
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = str(int(cookie.get("expires", 0) or 0))
        lines.append("\t".join([domain, include_subdomains, cookie.get("path", "/"), secure, expires,
                                cookie.get("name", ""), cookie.get("value", "")]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_cookie_file(path: Path):
    asyncio.run(_export_cookie_file(path))


def download_items(items: list[dict], directory: Path, state: dict):
    """后台顺序下载；一个 BV 可包含多 P，yt-dlp 会逐 P 生成标题 - P01.mp4。"""
    try:
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("未安装 yt-dlp 下载组件，请安装完整程序包")
        ffmpeg_location = _ffmpeg_location()
        directory.mkdir(parents=True, exist_ok=True)
        cookie_file = directory / ".bilibili-cookies.txt"
        try:
            export_cookie_file(cookie_file)
            for item in items:
                title = _safe_title(item.get("title", ""))
                state["message"] = f"正在下载：{title}"
                options = {
                    "format": "bv*+ba/b",
                    "merge_output_format": "mp4",
                    "outtmpl": str(directory / f"{title} - P%(playlist_index)02d.%(ext)s"),
                    "cookiefile": str(cookie_file),
                    "ffmpeg_location": ffmpeg_location,
                    "noplaylist": False,
                    "retries": 3,
                    "fragment_retries": 3,
                    "continuedl": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                try:
                    with yt_dlp.YoutubeDL(options) as ydl:
                        ydl.download([item["video_url"]])
                    state["done"] += 1
                    state["message"] = f"已完成：{title}"
                except Exception as exc:
                    state["failed"] += 1
                    state["message"] = f"下载失败：{title}（{exc}）"
                    logger.warning("下载 %s 失败: %s", item.get("bvid"), exc)
        finally:
            cookie_file.unlink(missing_ok=True)
    except Exception as exc:
        state["failed"] = state["total"]
        state["message"] = f"下载任务无法启动：{exc}"
        logger.exception("下载任务异常")
    finally:
        state["running"] = False


def start_download(items: list[dict], directory: Path, state: dict):
    state.update({"running": True, "total": len(items), "done": 0, "failed": 0, "message": "准备下载最高可获取画质…"})
    threading.Thread(target=download_items, args=(items, directory, state), daemon=True).start()
