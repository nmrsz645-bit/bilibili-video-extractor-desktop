"""哔哩哔哩视频提取桌面入口：本地服务 + 原生 WebView 窗口。"""
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

def _paths() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS), Path(sys.executable).resolve().parent
    root = Path(__file__).resolve().parent
    return root, root


RESOURCE_DIR, APP_DIR = _paths()
USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "哔哩哔哩视频提取"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(USER_DATA_DIR)
sys.path.insert(0, str(RESOURCE_DIR))
os.environ["BILIBILI_EXTRACTOR_DATA"] = str(USER_DATA_DIR)

# 发布包可以放入自己的 Chromium 内核，不依赖旧程序或系统环境。
bundled_browsers = APP_DIR / "ms-playwright"
if bundled_browsers.is_dir():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browsers)
bundled_ffmpeg = APP_DIR / "tools" / "ffmpeg" / "bin"
if (bundled_ffmpeg / "ffmpeg.exe").is_file():
    os.environ["BILIBILI_FFMPEG_LOCATION"] = str(bundled_ffmpeg)


def _show_error(message: str):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "哔哩哔哩视频提取启动失败", 0x10)
    except Exception:
        pass


def _check_desktop_runtime():
    """冻结版在加载 pywebview 前检查 .NET Framework，避免只弹出难懂的 pythonnet 错误。"""
    if not getattr(sys, "frozen", False):
        return
    try:
        import clr
        clr.AddReference("System.Windows.Forms")
    except Exception as exc:
        raise RuntimeError(
            "此程序需要 Microsoft .NET Framework 4.8.1 或更高版本才能创建桌面窗口。\n\n"
            "请安装或修复 .NET Framework 后重试：\nhttps://dotnet.microsoft.com/download/dotnet-framework"
        ) from exc


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(url: str) -> bool:
    for _ in range(80):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    _check_desktop_runtime()
    import db
    db.DB_PATH = USER_DATA_DIR / "data" / "bilibili_extractor.db"
    logging.basicConfig(filename=str(USER_DATA_DIR / "desktop.log"), level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    import uvicorn
    import webview
    from web.app import app
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    loading = "<html><body style='font-family:Microsoft YaHei;text-align:center;padding-top:180px;color:#475569'><h2>哔哩哔哩视频提取正在加载…</h2></body></html>"
    window = webview.create_window("哔哩哔哩视频提取", html=loading, width=1320, height=860, min_size=(1000, 680))

    def load():
        if _wait(url):
            window.load_url(url)
        else:
            window.load_html("<h2 style='font-family:Microsoft YaHei;text-align:center;padding-top:180px'>本地服务启动失败，请查看 desktop.log。</h2>")
    try:
        webview.start(load)
    finally:
        server.should_exit = True


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("桌面程序启动失败", exc_info=exc)
        _show_error(str(exc) or "程序启动失败，请查看 desktop.log")
        raise SystemExit(1)
