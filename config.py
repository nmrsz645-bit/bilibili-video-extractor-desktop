"""新项目独立配置与数据目录。"""
import os
from pathlib import Path

APP_DIR = Path(__file__).parent
USER_DATA_DIR = Path(os.environ["BILIBILI_EXTRACTOR_DATA"]) if os.environ.get("BILIBILI_EXTRACTOR_DATA") else (
    Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "哔哩哔哩视频提取"
)
SESSION_DIR = USER_DATA_DIR / "browser_session"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
