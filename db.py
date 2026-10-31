"""哔哩哔哩视频提取器的独立 SQLite 数据层。"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "bilibili_extractor.db"

VIDEO_RESULTS_SQL = """
CREATE TABLE IF NOT EXISTS video_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL CHECK(source IN ('creator','topic','single')),
    query_label TEXT,
    input_url TEXT,
    input_order INTEGER NOT NULL DEFAULT 0,
    author_name TEXT,
    author_mid TEXT,
    bvid TEXT NOT NULL,
    aid TEXT,
    title TEXT,
    video_url TEXT,
    published_at INTEGER,
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    pages_json TEXT DEFAULT '[]',
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, bvid, input_order)
);
"""


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS creators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mid TEXT NOT NULL UNIQUE,
            nickname TEXT,
            follower_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            avatar_url TEXT,
            input_url TEXT,
            profile_status TEXT DEFAULT '未读取',
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        _migrate_video_results(db)
        db.executescript(VIDEO_RESULTS_SQL + """
        CREATE INDEX IF NOT EXISTS idx_video_results_source_time
            ON video_results(source, published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_video_results_creator_time
            ON video_results(source, author_name, published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_video_results_single_order
            ON video_results(source, input_order, id);
        """)


def _migrate_video_results(db: sqlite3.Connection):
    """保留旧开发数据，并为单作品的逐行顺序加入独立唯一键。"""
    columns = {row["name"] for row in db.execute("PRAGMA table_info(video_results)").fetchall()}
    if not columns or "input_order" in columns:
        return
    db.execute("ALTER TABLE video_results RENAME TO video_results_legacy")
    db.executescript(VIDEO_RESULTS_SQL)
    db.execute("""
        INSERT INTO video_results(
            id, source, query_label, input_url, input_order, author_name, author_mid, bvid, aid, title,
            video_url, published_at, view_count, like_count, comment_count, share_count, favorite_count,
            pages_json, fetched_at
        ) SELECT
            id, source, query_label, input_url, 0, author_name, author_mid, bvid, aid, title,
            video_url, published_at, view_count, like_count, comment_count, share_count, favorite_count,
            pages_json, fetched_at
        FROM video_results_legacy
    """)
    db.execute("DROP TABLE video_results_legacy")


def add_creator(mid: str, input_url: str = "") -> int:
    with get_db() as db:
        db.execute("INSERT OR IGNORE INTO creators(mid, input_url) VALUES (?, ?)", (mid, input_url))
        row = db.execute("SELECT id FROM creators WHERE mid = ?", (mid,)).fetchone()
        return int(row["id"])


def list_creators() -> list[dict]:
    with get_db() as db:
        return [dict(row) for row in db.execute("SELECT * FROM creators ORDER BY id").fetchall()]


def update_creator_profile(mid: str, profile: dict, status: str = "已读取"):
    with get_db() as db:
        db.execute("""
            UPDATE creators SET nickname=?, follower_count=?, following_count=?, avatar_url=?,
                profile_status=?, updated_at=CURRENT_TIMESTAMP WHERE mid=?
        """, (
            profile.get("nickname", ""), int(profile.get("follower_count", 0) or 0),
            int(profile.get("following_count", 0) or 0), profile.get("avatar_url", ""), status, mid,
        ))


def clear_creators() -> dict:
    with get_db() as db:
        creators = int(db.execute("SELECT COUNT(*) AS c FROM creators").fetchone()["c"])
        videos = int(db.execute("SELECT COUNT(*) AS c FROM video_results WHERE source='creator'").fetchone()["c"])
        db.execute("DELETE FROM video_results WHERE source='creator'")
        db.execute("DELETE FROM creators")
        return {"creators": creators, "videos": videos}


def clear_results(source: str) -> int:
    _assert_source(source)
    with get_db() as db:
        count = int(db.execute("SELECT COUNT(*) AS c FROM video_results WHERE source=?", (source,)).fetchone()["c"])
        db.execute("DELETE FROM video_results WHERE source=?", (source,))
        return count


def upsert_result(source: str, video: dict, *, query_label: str = "", input_url: str = "", input_order: int = 0) -> int:
    _assert_source(source)
    with get_db() as db:
        row = db.execute("""
            INSERT INTO video_results(
                source, query_label, input_url, input_order, author_name, author_mid, bvid, aid, title, video_url,
                published_at, view_count, like_count, comment_count, share_count, favorite_count, pages_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, bvid, input_order) DO UPDATE SET
                query_label=excluded.query_label, input_url=excluded.input_url,
                author_name=excluded.author_name, author_mid=excluded.author_mid, aid=excluded.aid,
                title=excluded.title, video_url=excluded.video_url, published_at=excluded.published_at,
                view_count=excluded.view_count, like_count=excluded.like_count,
                comment_count=excluded.comment_count, share_count=excluded.share_count,
                favorite_count=excluded.favorite_count, pages_json=excluded.pages_json,
                fetched_at=CURRENT_TIMESTAMP
            RETURNING id
        """, (
            source, query_label, input_url, int(input_order), video.get("author_name", ""), str(video.get("author_mid", "")),
            video["bvid"], str(video.get("aid", "")), video.get("title", ""), video.get("video_url", ""),
            int(video.get("published_at", 0) or 0), int(video.get("view_count", 0) or 0),
            int(video.get("like_count", 0) or 0), int(video.get("comment_count", 0) or 0),
            int(video.get("share_count", 0) or 0), int(video.get("favorite_count", 0) or 0),
            json.dumps(video.get("pages", []), ensure_ascii=False),
        )).fetchone()
        return int(row["id"])


def list_results(source: str) -> list[dict]:
    _assert_source(source)
    with get_db() as db:
        if source == "creator":
            rows = db.execute("""
                SELECT video_results.* FROM video_results
                LEFT JOIN creators ON creators.mid = video_results.author_mid
                WHERE video_results.source = ?
                ORDER BY creators.id IS NULL, creators.id ASC,
                         video_results.published_at DESC, video_results.id DESC
            """, (source,)).fetchall()
        else:
            ordering = "input_order ASC, id ASC" if source == "single" else "published_at DESC, id DESC"
            rows = db.execute(f"SELECT * FROM video_results WHERE source=? ORDER BY {ordering}", (source,)).fetchall()
    result = []
    for row in rows:
        value = dict(row)
        value["pages"] = json.loads(value.pop("pages_json") or "[]")
        result.append(value)
    return result


def get_results_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    rows: list[dict] = []
    with get_db() as db:
        for start in range(0, len(ids), 500):
            batch = ids[start:start + 500]
            marks = ",".join("?" for _ in batch)
            rows.extend(dict(row) for row in db.execute(
                f"SELECT * FROM video_results WHERE id IN ({marks})", batch
            ).fetchall())
    for row in rows:
        row["pages"] = json.loads(row.pop("pages_json") or "[]")
    by_id = {row["id"]: row for row in rows}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def _assert_source(source: str):
    if source not in {"creator", "topic", "single"}:
        raise ValueError("无效结果来源")
