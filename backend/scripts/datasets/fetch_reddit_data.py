#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reddit 数据采集（Apify Actor：harshmaur/reddit-scraper）

文档与计费说明见：https://apify.com/harshmaur/reddit-scraper

认证：在 backend/.env 中设置 APIFY_REDDIT_KEY（Apify API Token）。

输出：默认 --format nested，写 { "posts": [ 每帖含 "comments" 树（replies 嵌套） ], "other": [ 非帖/非评等 ] }；
      需 Actor 原始扁平列表时用 --format flat。
过滤：导出前丢弃 title 与 body 均为空（去空白后）的帖子及其评论。
评论：默认仅导出「一级评论」；导出条数用 --top-comments-limit（默认 5）。
传给 Apify 的 --max-comments-per-post 包含楼中楼条数；若仍与 total 过小，数据集里一级评论可能很少（见脚本说明）。
发帖人资料（可选）：--fetch-post-author-profiles 时对每个唯一发帖人再跑一轮用户页 URL，将结果写入帖子的 authorProfile；仅从帖对象取 OP，不包含评论里的 author。

模式：
- post：单条 startUrl（默认示例为一篇帖子）。
- popular-subreddits：默认用 /r/popular 帖流（可从每条帖的 community 字段归纳热门版）；不要用
  /subreddits/popular/ —— Actor 拉取的 *.json 常被 Reddit 403，数据集会为空。
- search-communities：用关键词 + searchCommunities（不依赖上述 .json 列表端点）。
- communities-hot：对每个版抓「热门/最新/Top」列表上的帖，并可选沿帖爬评论；版名可通过命令行 --community 传入，
  若不传则使用脚本里的 DEFAULT_COMMUNITIES_HOT（可自行改）。

运行方式对齐 fetch_twitter_data.py：
- 默认：抓取 → 写入 SQLite（backend/data/datasets/oasis_datasets.db，可与 Twitter 共库）→ **仅向 stdout 打印入库结果 JSON**。
- `--preview`：只向 stdout 打印抓取结果 JSON，**不写库**（与 Twitter 的 --preview 一致）。
- `--out`：另存抓取结果到文件（可选）；默认运行不以「整包帖子 JSON」占满 stdout。
- `--db-path`：SQLite 路径，默认同 Twitter 脚本。
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from apify_client import ApifyClient
from dotenv import dotenv_values, load_dotenv

REDDIT_PLATFORM = "reddit"
REDDIT_DB_TYPE = "reddit"
# 用户简介写入 SQLite users.bio（对接 import 时的 description 字段）；KOL：totalKarma 大于该值
REDDIT_KOL_MIN_TOTAL_KARMA = 100_000

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=True)

# 与 fetch_twitter_data 写入同一文件；DDL 默认值/迁移逻辑需与其保持一致
_DEFAULT_SQLITE_PATH_FALLBACK = _PROJECT_ROOT / "data" / "datasets" / "oasis_datasets.db"
_DEFAULT_SQLITE_PATH_ENV_KEYS = ("OASIS_DATASETS_DB", "SOCITWIN_DATASETS_DB", "SOCITWIN_SQLITE_PATH")
_DEFAULT_SQLITE_PATH_ENV_RAW = next(
    (str(os.environ[k]).strip() for k in _DEFAULT_SQLITE_PATH_ENV_KEYS if str(os.environ.get(k) or "").strip()),
    "",
)
DEFAULT_SQLITE_PATH = (
    Path(_DEFAULT_SQLITE_PATH_ENV_RAW).expanduser().resolve()
    if _DEFAULT_SQLITE_PATH_ENV_RAW
    else _DEFAULT_SQLITE_PATH_FALLBACK
)
_SQLITE_LEGACY_ROW_TYPE = "twitter"


def _reddit_comment_ts_key(d: Dict[str, Any]) -> str:
    return str(d.get("commentCreatedAt") or d.get("createdAt") or "")


def _sqlite_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sqlite_normalize(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _sqlite_topic_key(topic_label: str) -> str:
    if not isinstance(topic_label, str):
        return ""
    return " ".join(topic_label.strip().lower().split())


def _sqlite_topic_key_to_news_id_map(news_rows: List[Dict[str, Any]]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for r in news_rows:
        if not isinstance(r, dict):
            continue
        label = str(r.get("name") or "").strip()
        nid = str(r.get("news_id") or "").strip()
        if label and nid:
            m[_sqlite_topic_key(label)] = nid
    return m


def _sqlite_json_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _sqlite_ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA user_version = 1;

        CREATE TABLE IF NOT EXISTS topics (
            platform TEXT NOT NULL,
            "type" TEXT NOT NULL DEFAULT 'twitter',
            topic_key TEXT NOT NULL,
            topic_label TEXT NOT NULL,
            topic_type TEXT NOT NULL DEFAULT 'trend',
            trend_rank INTEGER,
            post_count INTEGER NOT NULL DEFAULT 0,
            reply_count INTEGER NOT NULL DEFAULT 0,
            user_count INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT,
            last_seen_at TEXT,
            news_external_id TEXT,
            raw_json TEXT,
            PRIMARY KEY (platform, topic_key)
        );

        CREATE TABLE IF NOT EXISTS users (
            platform TEXT NOT NULL,
            "type" TEXT NOT NULL DEFAULT 'twitter',
            external_user_id TEXT NOT NULL,
            username TEXT,
            display_name TEXT,
            bio TEXT,
            location TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            follower_count INTEGER,
            following_count INTEGER,
            tweet_count INTEGER,
            user_type TEXT,
            profile_json TEXT,
            raw_json TEXT,
            PRIMARY KEY (platform, external_user_id)
        );

        CREATE TABLE IF NOT EXISTS contents (
            platform TEXT NOT NULL,
            "type" TEXT NOT NULL DEFAULT 'twitter',
            external_content_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            author_external_user_id TEXT,
            parent_external_content_id TEXT,
            root_external_content_id TEXT,
            text TEXT,
            language TEXT,
            created_at TEXT,
            like_count INTEGER,
            reply_count INTEGER,
            share_count INTEGER,
            view_count INTEGER,
            raw_json TEXT,
            PRIMARY KEY (platform, external_content_id)
        );

        CREATE TABLE IF NOT EXISTS content_topics (
            platform TEXT NOT NULL,
            "type" TEXT NOT NULL DEFAULT 'twitter',
            external_content_id TEXT NOT NULL,
            topic_key TEXT NOT NULL,
            relevance_score REAL NOT NULL DEFAULT 1.0,
            PRIMARY KEY (platform, external_content_id, topic_key)
        );

        CREATE TABLE IF NOT EXISTS user_topics (
            platform TEXT NOT NULL,
            "type" TEXT NOT NULL DEFAULT 'twitter',
            topic_key TEXT NOT NULL,
            external_user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content_count INTEGER NOT NULL DEFAULT 0,
            news_external_id TEXT,
            PRIMARY KEY (platform, topic_key, external_user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_topics_platform ON topics(platform);
        CREATE INDEX IF NOT EXISTS idx_contents_platform_author ON contents(platform, author_external_user_id);
        CREATE INDEX IF NOT EXISTS idx_content_topics_platform_topic ON content_topics(platform, topic_key);
        CREATE INDEX IF NOT EXISTS idx_user_topics_platform_topic ON user_topics(platform, topic_key);
        """
    )
    _sqlite_migrate_topics_news_external_id(conn)
    _sqlite_migrate_user_topics_news_external_id(conn)
    for _tbl in ("topics", "users", "contents", "content_topics", "user_topics"):
        _sqlite_migrate_table_row_type(conn, _tbl)
    conn.commit()


def _sqlite_migrate_table_row_type(conn: sqlite3.Connection, table: str) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    col_names = {row[1] for row in cur.fetchall()}
    if not col_names or "type" in col_names:
        return
    conn.execute(
        f'ALTER TABLE "{table}" ADD COLUMN "type" TEXT DEFAULT \'{_SQLITE_LEGACY_ROW_TYPE}\''
    )
    conn.execute(
        f'UPDATE "{table}" SET "type" = ? WHERE "type" IS NULL',
        (_SQLITE_LEGACY_ROW_TYPE,),
    )


def _sqlite_migrate_user_topics_news_external_id(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(user_topics)")
    col_names = {row[1] for row in cur.fetchall()}
    if col_names and "news_external_id" not in col_names:
        conn.execute("ALTER TABLE user_topics ADD COLUMN news_external_id TEXT")


def _sqlite_migrate_topics_news_external_id(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(topics)")
    col_names = {row[1] for row in cur.fetchall()}
    if col_names and "news_external_id" not in col_names:
        conn.execute("ALTER TABLE topics ADD COLUMN news_external_id TEXT")


def import_reddit_payload_to_sqlite(
    payload: Dict[str, Any],
    fetch_options: Dict[str, Any],
    db_path: Path,
) -> Dict[str, Any]:
    """将 build_sqlite_payload_from_nested 的产物写入 oasis_datasets.db（与 Twitter 共用 schema）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    platform = REDDIT_PLATFORM
    row_type = REDDIT_DB_TYPE

    collected_at = _sqlite_normalize(payload.get("meta", {}).get("collected_at")) or _sqlite_now_iso()
    topics_payload = payload.get("topics") if isinstance(payload.get("topics"), list) else []
    users_payload = payload.get("users") if isinstance(payload.get("users"), list) else []
    posts_payload = payload.get("posts") if isinstance(payload.get("posts"), list) else []
    replies_payload = payload.get("replies") if isinstance(payload.get("replies"), list) else []
    meta_obj = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    trends_payload = meta_obj.get("trends_processed")
    if not isinstance(trends_payload, list):
        trends_payload = []
    news_rows_meta = meta_obj.get("news_rows")
    if not isinstance(news_rows_meta, list):
        news_rows_meta = []
    topic_key_to_news_id = _sqlite_topic_key_to_news_id_map(
        [x for x in news_rows_meta if isinstance(x, dict)]
    )

    trend_order = {
        _sqlite_topic_key(str(topic)): idx + 1
        for idx, topic in enumerate(trends_payload or [])
        if _sqlite_topic_key(str(topic))
    }

    topic_labels: Dict[str, str] = {}
    topic_post_count: Dict[str, int] = {}
    topic_reply_count: Dict[str, int] = {}
    topic_users: Dict[str, set[str]] = {}
    user_topic_stats: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def ensure_topic(topic_label: str) -> Optional[str]:
        tkey = _sqlite_topic_key(topic_label)
        if not tkey:
            return None
        if tkey not in topic_labels:
            topic_labels[tkey] = topic_label
            topic_post_count[tkey] = 0
            topic_reply_count[tkey] = 0
            topic_users[tkey] = set()
        return tkey

    for topic_label in topics_payload:
        if isinstance(topic_label, str):
            ensure_topic(topic_label)

    content_topic_rows: List[Tuple[str, str, str, float]] = []
    contents_rows: List[Tuple[Any, ...]] = []

    def track_user_topic(topic_key: str, external_user_id: str, role_name: str) -> None:
        if not topic_key or not external_user_id:
            return
        topic_users.setdefault(topic_key, set()).add(external_user_id)
        stat = user_topic_stats.setdefault(
            (topic_key, external_user_id),
            {"content_count": 0, "roles": set()},
        )
        stat["content_count"] += 1
        stat["roles"].add(role_name)

    for post in posts_payload:
        if not isinstance(post, dict):
            continue
        external_content_id = _sqlite_normalize(post.get("twitter_post_id"))
        author_external_user_id = _sqlite_normalize(post.get("twitter_author_id"))
        if not external_content_id:
            continue

        contents_rows.append(
            (
                platform,
                row_type,
                external_content_id,
                "post",
                author_external_user_id or None,
                None,
                _sqlite_normalize(post.get("twitter_conversation_id")) or external_content_id,
                _sqlite_normalize(post.get("content")) or None,
                _sqlite_normalize(post.get("language")) or None,
                _sqlite_normalize(post.get("createdAt")) or None,
                post.get("like_count"),
                post.get("reply_count"),
                post.get("share_count"),
                post.get("view_count"),
                _sqlite_json_text(post),
            )
        )

        for topic_label in post.get("source_topics", []) or []:
            if not isinstance(topic_label, str):
                continue
            tkey = ensure_topic(topic_label)
            if not tkey:
                continue
            content_topic_rows.append((platform, row_type, external_content_id, tkey, 1.0))
            topic_post_count[tkey] = topic_post_count.get(tkey, 0) + 1
            track_user_topic(tkey, author_external_user_id, "author")

    for reply in replies_payload:
        if not isinstance(reply, dict):
            continue
        external_content_id = _sqlite_normalize(reply.get("twitter_reply_id"))
        author_external_user_id = _sqlite_normalize(reply.get("twitter_author_id"))
        parent_external_content_id = _sqlite_normalize(reply.get("parent_external_content_id"))
        if not parent_external_content_id:
            parent_external_content_id = _sqlite_normalize(reply.get("twitter_post_id"))
        root_external_content_id = _sqlite_normalize(reply.get("root_external_content_id"))
        if not root_external_content_id:
            root_external_content_id = parent_external_content_id
        if not external_content_id:
            continue

        contents_rows.append(
            (
                platform,
                row_type,
                external_content_id,
                "reply",
                author_external_user_id or None,
                parent_external_content_id or None,
                root_external_content_id or None,
                _sqlite_normalize(reply.get("content")) or None,
                _sqlite_normalize(reply.get("language")) or None,
                _sqlite_normalize(reply.get("createdAt")) or None,
                reply.get("like_count"),
                reply.get("reply_count"),
                reply.get("share_count"),
                reply.get("view_count"),
                _sqlite_json_text(reply),
            )
        )

        for topic_label in reply.get("source_topics", []) or []:
            if not isinstance(topic_label, str):
                continue
            tkey = ensure_topic(topic_label)
            if not tkey:
                continue
            content_topic_rows.append((platform, row_type, external_content_id, tkey, 1.0))
            topic_reply_count[tkey] = topic_reply_count.get(tkey, 0) + 1
            track_user_topic(tkey, author_external_user_id, "replier")

    users_rows: List[Tuple[Any, ...]] = []
    for user in users_payload:
        if not isinstance(user, dict):
            continue
        external_user_id = _sqlite_normalize(user.get("twitter_user_id"))
        if not external_user_id:
            continue
        users_rows.append(
            (
                platform,
                row_type,
                external_user_id,
                _sqlite_normalize(user.get("user_name")) or None,
                _sqlite_normalize(user.get("name")) or None,
                _sqlite_normalize(user.get("description")) or None,
                _sqlite_normalize(user.get("location")) or None,
                1 if bool(user.get("verified")) else 0,
                user.get("followers_count"),
                user.get("following_count"),
                user.get("tweet_count"),
                _sqlite_normalize(user.get("user_type")) or None,
                _sqlite_json_text(user.get("profile")),
                _sqlite_json_text(user),
            )
        )

    user_topic_rows: List[Tuple[Any, ...]] = []
    for (topic_key, external_user_id), stat in user_topic_stats.items():
        roles = stat["roles"]
        role = "both" if {"author", "replier"}.issubset(roles) else next(iter(roles), "author")
        news_ext_ut = topic_key_to_news_id.get(topic_key) or None
        user_topic_rows.append(
            (
                platform,
                row_type,
                topic_key,
                external_user_id,
                role,
                int(stat["content_count"]),
                news_ext_ut,
            )
        )

    topics_rows: List[Tuple[Any, ...]] = []
    for topic_key, topic_label in topic_labels.items():
        news_ext = topic_key_to_news_id.get(topic_key)
        topics_rows.append(
            (
                platform,
                row_type,
                topic_key,
                topic_label,
                "trend",
                trend_order.get(topic_key),
                int(topic_post_count.get(topic_key, 0)),
                int(topic_reply_count.get(topic_key, 0)),
                len(topic_users.get(topic_key, set())),
                collected_at,
                collected_at,
                news_ext,
                _sqlite_json_text(
                    {
                        "fetch_options": fetch_options,
                        "trends_processed": trends_payload or [],
                        "news_external_id": news_ext,
                    }
                ),
            )
        )

    conn = sqlite3.connect(str(db_path))
    ins_topics = ins_users = ins_contents = ins_ct = ins_ut = 0
    skip_topics = skip_users = skip_contents = skip_ct = skip_ut = 0
    try:
        _sqlite_ensure_schema(conn)
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN")

        if topics_rows:
            for row in topics_rows:
                (
                    pl,
                    rt,
                    topic_key,
                    topic_label,
                    topic_type,
                    tr,
                    pc,
                    rc,
                    uc,
                    fa,
                    la,
                    news_ext,
                    raw,
                ) = row
                if news_ext:
                    dup = conn.execute(
                        'SELECT 1 FROM topics WHERE platform = ? AND "type" = ? AND news_external_id = ?',
                        (pl, rt, news_ext),
                    ).fetchone()
                else:
                    dup = conn.execute(
                        'SELECT 1 FROM topics WHERE platform = ? AND "type" = ? AND topic_key = ?',
                        (pl, rt, topic_key),
                    ).fetchone()
                if dup:
                    skip_topics += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO topics (
                        platform, "type", topic_key, topic_label, topic_type, trend_rank,
                        post_count, reply_count, user_count, first_seen_at, last_seen_at,
                        news_external_id, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                ins_topics += 1

        if users_rows:
            for row in users_rows:
                pl, rt, uid = row[0], row[1], row[2]
                if conn.execute(
                    'SELECT 1 FROM users WHERE platform = ? AND "type" = ? AND external_user_id = ?',
                    (pl, rt, uid),
                ).fetchone():
                    skip_users += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO users (
                        platform, "type", external_user_id, username, display_name, bio, location,
                        verified, follower_count, following_count, tweet_count, user_type,
                        profile_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                ins_users += 1

        if contents_rows:
            for row in contents_rows:
                pl, rt, cid = row[0], row[1], row[2]
                if conn.execute(
                    'SELECT 1 FROM contents WHERE platform = ? AND "type" = ? AND external_content_id = ?',
                    (pl, rt, cid),
                ).fetchone():
                    skip_contents += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO contents (
                        platform, "type", external_content_id, content_type, author_external_user_id,
                        parent_external_content_id, root_external_content_id, text, language,
                        created_at, like_count, reply_count, share_count, view_count, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                ins_contents += 1

        if content_topic_rows:
            for row in content_topic_rows:
                pl, rt, cid, tk, _score = row[0], row[1], row[2], row[3], row[4]
                if conn.execute(
                    """
                    SELECT 1 FROM content_topics
                    WHERE platform = ? AND "type" = ? AND external_content_id = ? AND topic_key = ?
                    """,
                    (pl, rt, cid, tk),
                ).fetchone():
                    skip_ct += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO content_topics (
                        platform, "type", external_content_id, topic_key, relevance_score
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    row,
                )
                ins_ct += 1

        if user_topic_rows:
            for row in user_topic_rows:
                pl, rt, tk, uid, role, _ccnt, news_ext_ut = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                if news_ext_ut:
                    dup = conn.execute(
                        """
                        SELECT 1 FROM user_topics
                        WHERE platform = ? AND "type" = ? AND external_user_id = ? AND news_external_id = ?
                        """,
                        (pl, rt, uid, news_ext_ut),
                    ).fetchone()
                else:
                    dup = conn.execute(
                        """
                        SELECT 1 FROM user_topics
                        WHERE platform = ? AND "type" = ? AND topic_key = ? AND external_user_id = ?
                        AND (news_external_id IS NULL OR news_external_id = '')
                        """,
                        (pl, rt, tk, uid),
                    ).fetchone()
                if dup:
                    skip_ut += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO user_topics (
                        platform, "type", topic_key, external_user_id, role, content_count, news_external_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                ins_ut += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "success",
        "platform": platform,
        "db_path": str(db_path),
        "mode": "merge_skip_duplicates",
        "imported": {
            "topics": ins_topics,
            "users": ins_users,
            "contents": ins_contents,
            "content_topics": ins_ct,
            "user_topics": ins_ut,
            "posts": len(posts_payload),
            "replies": len(replies_payload),
        },
        "skipped_duplicates": {
            "topics": skip_topics,
            "users": skip_users,
            "contents": skip_contents,
            "content_topics": skip_ct,
            "user_topics": skip_ut,
        },
        "attempted": {
            "topics": len(topics_rows),
            "users": len(users_rows),
            "contents": len(contents_rows),
            "content_topics": len(content_topic_rows),
            "user_topics": len(user_topic_rows),
        },
        "counts": payload.get("meta", {}).get("counts", {}),
    }


# Pay-per-result Reddit Scraper（与商店 README / Input Schema 一致）
DEFAULT_ACTOR_ID = "harshmaur/reddit-scraper"

DEFAULT_START_URL = (
    "https://www.reddit.com/r/pasta/comments/vwi6jx/"
    "pasta_peperoni_and_ricotta_cheese_how_to_make/"
)

# /subreddits/popular 常触发 Reddit 对 *.json 返回 403（见 Actor 日志）；默认改用 /r/popular 帖流。
DEFAULT_POPULAR_FEED_URL = "https://www.reddit.com/r/popular/"
# 仍想尝试目录页时可：--browse-url https://www.reddit.com/subreddits/popular/
SUBREDDITS_DIRECTORY_URL = "https://www.reddit.com/subreddits/popular/"

DEFAULT_SEARCH_TERMS_COMMUNITIES = ["technology", "gaming", "science", "news", "worldnews"]

# communities-hot：未传 --community 时使用（可直接改列表）
DEFAULT_COMMUNITIES_HOT = [
  "worldnews",
  "ArtificialInteligence",
  "technology",
  "science",
  "entertainment",
  "politics",
  "business",
  "health",
  "education",
  "environment",
  "sports",
  "music",
  "art",
  "literature",
  "history",
  "religion",
  "culture",
  "travel",
  "fashion",
  "beauty"
]



def normalize_subreddit_slug(name: str) -> str:
    """接受 gaming、r/gaming、/r/gaming。"""
    n = (name or "").strip()
    if n.lower().startswith("/r/"):
        n = n[3:]
    elif n.lower().startswith("r/"):
        n = n[2:]
    return n.strip().strip("/")


def subreddit_feed_url(slug: str, feed: str) -> str:
    """feed: hot | new | top-day | top-week | top-month"""
    base = f"https://www.reddit.com/r/{slug}"
    if feed == "hot":
        return f"{base}/hot/"
    if feed == "new":
        return f"{base}/new/"
    if feed == "top-day":
        return f"{base}/top/?t=day"
    if feed == "top-week":
        return f"{base}/top/?t=week"
    if feed == "top-month":
        return f"{base}/top/?t=month"
    return f"{base}/hot/"


def _proxy() -> Dict[str, Any]:
    return {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}


def _apify_token() -> str:
    """优先从 .env 读取 APIFY_REDDIT_KEY，再读进程环境变量。"""
    if _ENV_FILE.is_file():
        raw = (dotenv_values(_ENV_FILE).get("APIFY_REDDIT_KEY") or "").strip()
        if raw:
            return raw
    return (os.getenv("APIFY_REDDIT_KEY") or "").strip()


def build_run_input_post(
    start_url: str,
    *,
    max_posts: int,
    max_comments_per_post: int,
    max_comments_total: int,
    crawl_comments_per_post: bool,
    fast_mode: bool,
    include_nsfw: bool,
    max_communities_count: int,
) -> Dict[str, Any]:
    """harshmaur/reddit-scraper：URL 入口（帖 / 版 / 用户 / 搜索页等）。"""
    return {
        "startUrls": [{"url": start_url}],
        "crawlCommentsPerPost": crawl_comments_per_post,
        "maxPostsCount": max(0, max_posts),
        "maxCommentsPerPost": max(0, max_comments_per_post),
        "maxCommentsCount": max(0, max_comments_total),
        "maxCommunitiesCount": max(0, max_communities_count),
        "includeNSFW": include_nsfw,
        "fastMode": fast_mode,
        "proxy": _proxy(),
    }


def build_run_input_popular_subreddits(
    limit: int,
    browse_url: str,
    *,
    feed_posts: int,
) -> Dict[str, Any]:
    """热门聚合：默认 r/popular 帖流；maxPostsCount>0 才有数据。/subreddits/popular 常 403。"""
    lim = max(1, min(int(limit), 500))
    posts = max(0, min(int(feed_posts), 500))
    # 搜索页、r/popular 可走 Fast Mode；目录 /subreddits/* 保持 false，减少异常。
    fast = "/search/" in browse_url or "/r/popular" in browse_url
    return {
        "startUrls": [{"url": browse_url}],
        "crawlCommentsPerPost": False,
        "maxPostsCount": posts,
        "maxCommentsCount": 0,
        "maxCommentsPerPost": 0,
        "maxCommunitiesCount": lim,
        "includeNSFW": False,
        "fastMode": fast,
        "proxy": _proxy(),
    }


def build_run_input_communities_hot(
    communities: List[str],
    *,
    feed: str,
    posts_per_community: int,
    max_comments_per_post: int,
    max_comments_total: int,
    crawl_comments_per_post: bool,
    include_nsfw: bool,
) -> Dict[str, Any]:
    """多版区列表 URL（各版 /hot 等）+ 帖与评论限额；见 harshmaur README 多 startUrls 示例。"""
    slugs: List[str] = []
    for raw in communities:
        s = normalize_subreddit_slug(raw)
        if s:
            slugs.append(s)
    if not slugs:
        raise ValueError("No valid community names after normalization.")
    ppc = max(1, min(int(posts_per_community), 500))
    n = len(slugs)
    # 总帖上限：按「每版希望条数 × 版数」给 Actor 预算（若 Actor 按全局 cap 则略偏大，可调小）
    max_posts_cap = min(5000, ppc * n)
    start_urls = [{"url": subreddit_feed_url(slug, feed)} for slug in slugs]
    return {
        "startUrls": start_urls,
        "crawlCommentsPerPost": crawl_comments_per_post,
        "maxPostsCount": max_posts_cap,
        "maxCommentsPerPost": max(0, max_comments_per_post),
        "maxCommentsCount": max(0, max_comments_total),
        "maxCommunitiesCount": max(n, 2),
        "includeNSFW": include_nsfw,
        "fastMode": False,
        "proxy": _proxy(),
    }


def build_run_input_search_communities(terms: List[str], limit: int) -> Dict[str, Any]:
    """关键词搜索「版块」类型，避开 /subreddits/popular/.json 的 403。每个词有独立配额（见 Actor 文档）。"""
    lim = max(1, min(int(limit), 500))
    cleaned = [t.strip() for t in terms if t and t.strip()]
    if not cleaned:
        cleaned = list(DEFAULT_SEARCH_TERMS_COMMUNITIES)
    return {
        "searchTerms": cleaned,
        "searchCommunities": True,
        "searchPosts": False,
        "searchComments": False,
        "searchSort": "hot",
        "searchTime": "all",
        "includeNSFW": False,
        "maxCommunitiesCount": lim,
        "maxPostsCount": 0,
        "maxCommentsCount": 0,
        "maxCommentsPerPost": 0,
        "crawlCommentsPerPost": False,
        "fastMode": True,
        "proxy": _proxy(),
    }


def run_actor_and_collect_items(token: str, run_input: Dict[str, Any], actor_id: str) -> List[Dict[str, Any]]:
    client = ApifyClient(token)
    run = client.actor(actor_id).call(run_input=run_input)
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError(f"Actor run has no defaultDatasetId: {run}")
    out: List[Dict[str, Any]] = []
    for item in client.dataset(dataset_id).iterate_items():
        out.append(item)
    return out


_SKIP_AUTHOR_NAMES = {"", "[deleted]", "deleted", "automoderator"}


def _skip_post_author_name(name: str) -> bool:
    n = (name or "").strip()
    return not n or n.lower() in _SKIP_AUTHOR_NAMES


def unique_post_author_names(posts: List[Dict[str, Any]]) -> List[str]:
    """仅从帖子对象收集发帖人用户名（不去 comments），去重并保持大致顺序。"""
    seen: set = set()
    out: List[str] = []
    for p in posts:
        name = str(p.get("authorName") or "").strip()
        if _skip_post_author_name(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def build_run_input_post_author_profiles(
    usernames: List[str],
    *,
    max_posts_per_user: int,
) -> Dict[str, Any]:
    """对每个用户名一条 https://www.reddit.com/user/{name}/（见 harshmaur README 用户页示例）。"""
    start_urls: List[Dict[str, str]] = []
    for raw in usernames:
        u = str(raw).strip().strip("/")
        if _skip_post_author_name(u):
            continue
        seg = quote(u, safe="-_.")
        start_urls.append({"url": f"https://www.reddit.com/user/{seg}/"})
    n_urls = len(start_urls)
    cap_posts = max(0, min(int(max_posts_per_user), 900))
    return {
        "startUrls": start_urls,
        "crawlCommentsPerPost": False,
        "maxPostsCount": cap_posts,
        "maxCommentsCount": 0,
        "maxCommentsPerPost": 0,
        "maxCommunitiesCount": max(n_urls, 2),
        "includeNSFW": False,
        "fastMode": False,
        "proxy": _proxy(),
    }


def _profile_username_from_item(it: Dict[str, Any]) -> str:
    dt = str(it.get("dataType") or "").lower()
    if dt == "user":
        for key in ("authorName", "name"):
            v = str(it.get(key) or "").strip()
            if v:
                return v
    url = str(it.get("url") or it.get("profileUrl") or "")
    m = re.search(r"/user/([^/?#]+)", url, re.I)
    if m:
        return unquote(m.group(1))
    return str(it.get("authorName") or "").strip()


def index_profile_items(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """扁平 Actor 输出 → 每条用户合并为一条代表记录（优先 dataType=user，其次字段最多）。

    同一 Reddit 用户按不区分大小写合并；结果表 `out` 在「原样用户名、小写、URL 解码变体」等键上
    都指向同一对象，便于 attach 时先按帖里的 authorName 原样查，不必先转小写。
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        key = _profile_username_from_item(it).strip()
        if not key:
            continue
        buckets.setdefault(key.lower(), []).append(it)

    out: Dict[str, Dict[str, Any]] = {}
    for lk, lst in buckets.items():
        prefer_user = [x for x in lst if str(x.get("dataType") or "").lower() == "user"]
        pool = prefer_user if prefer_user else lst
        best = max(pool, key=lambda d: len(d))
        variants: set = set()
        for it in lst:
            k = _profile_username_from_item(it).strip()
            if k:
                variants.add(k)
        for fld in ("authorName", "name"):
            v = str(best.get(fld) or "").strip()
            if v:
                variants.add(v)
        variants.add(lk)
        for v in variants:
            out[v] = best
    return out


def fetch_post_author_profiles(
    token: str,
    usernames: List[str],
    actor_id: str,
    *,
    max_posts_per_user: int,
    chunk_size: int,
) -> Dict[str, Dict[str, Any]]:
    """对用户名列表分块调用 Actor，合并 profile 索引。"""
    if not usernames:
        return {}
    cs = max(1, min(int(chunk_size), 500))
    merged: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(usernames), cs):
        chunk = usernames[i : i + cs]
        run_input = build_run_input_post_author_profiles(
            chunk,
            max_posts_per_user=max_posts_per_user,
        )
        if not run_input.get("startUrls"):
            continue
        chunk_items = run_actor_and_collect_items(token, run_input, actor_id)
        merged.update(index_profile_items(chunk_items))
    return merged


def attach_author_profiles_to_posts(
    posts: List[Dict[str, Any]],
    profiles_by_name: Dict[str, Dict[str, Any]],
) -> None:
    for p in posts:
        name = str(p.get("authorName") or "").strip()
        if _skip_post_author_name(name):
            continue
        prof = profiles_by_name.get(name)
        if prof is None:
            prof = profiles_by_name.get(name.lower())
        if prof:
            p["authorProfile"] = prof


def _comment_full_id(row: Dict[str, Any]) -> str:
    """与 Reddit parentId（t1_xxx）对齐。"""
    cid = str(row.get("id") or "")
    if cid.startswith(("t1_", "t3_")):
        return cid
    return f"t1_{cid}"


def _post_full_id(row: Dict[str, Any]) -> str:
    pid = str(row.get("id") or "")
    if pid.startswith("t3_"):
        return pid
    parsed = row.get("parsedId")
    if parsed:
        return f"t3_{parsed}"
    return pid


def nest_comment_threads(rows: List[Dict[str, Any]], post_id_full: str) -> List[Dict[str, Any]]:
    """同一帖下的评论列表 → 顶层评论 + replies 嵌套。"""
    nodes: Dict[str, Dict[str, Any]] = {}
    for raw in rows:
        fid = _comment_full_id(raw)
        nodes[fid] = {**raw, "replies": []}

    roots: List[Dict[str, Any]] = []
    orphans: List[Dict[str, Any]] = []
    for raw in rows:
        fid = _comment_full_id(raw)
        node = nodes[fid]
        pid = str(raw.get("parentId") or "")
        if pid == post_id_full:
            roots.append(node)
        elif pid in nodes:
            nodes[pid]["replies"].append(node)
        else:
            orphans.append(node)

    def sort_tree(ns: List[Dict[str, Any]]) -> None:
        ns.sort(key=_reddit_comment_ts_key)
        for n in ns:
            if n.get("replies"):
                sort_tree(n["replies"])

    sort_tree(roots)
    roots.extend(orphans)
    return roots


def first_level_comments_limited(
    rows: List[Dict[str, Any]],
    post_id_full: str,
    max_n: int,
) -> List[Dict[str, Any]]:
    """只保留直接回复帖子（parentId == 帖子 id）的一级评论，按时间排序后截断前 max_n 条；不含 replies。"""
    cap = max(0, min(int(max_n), 500))
    roots: List[Dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("parentId") or "") != post_id_full:
            continue
        roots.append({**raw})

    roots.sort(key=_reddit_comment_ts_key)
    return roots[:cap]


def _post_title_and_body_both_empty(p: Dict[str, Any]) -> bool:
    """去首尾空白后 title、body 皆空则视为丢弃。"""
    title = str(p.get("title") or "").strip()
    body = str(p.get("body") or "").strip()
    return title == "" and body == ""


def filter_items_drop_empty_title_body_posts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """扁平导出：去掉 title+body 皆空的帖及隶属评论；其它 dataType 原样保留。"""
    kept_ids: set = set()
    for it in items:
        if str(it.get("dataType") or "").lower() != "post":
            continue
        if not _post_title_and_body_both_empty(it):
            kept_ids.add(_post_full_id(it))
    out: List[Dict[str, Any]] = []
    for it in items:
        dt = str(it.get("dataType") or "").lower()
        if dt == "post":
            if not _post_title_and_body_both_empty(it):
                out.append(it)
        elif dt == "comment":
            pk = str(it.get("postId") or "")
            if not pk and it.get("parsedPostId"):
                pk = f"t3_{it['parsedPostId']}"
            if pk in kept_ids:
                out.append(it)
        else:
            out.append(it)
    return out


def reshape_posts_with_comments(
    items: List[Dict[str, Any]],
    *,
    comment_depth: str = "top",
    top_comments_limit: int = 5,
) -> Dict[str, Any]:
    """Actor 扁平列表 → posts[].comments；其余类型进 other。

    丢弃 title 与 body 均为空的帖子及其评论。
    comment_depth=top：仅一级评论（parentId=帖子），每条最多保留 top_comments_limit 条。
    comment_depth=nested：树形 replies（仍受 Apify 抓取上限约束）。
    """
    posts_raw: List[Dict[str, Any]] = []
    comments_raw: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for it in items:
        dt = str(it.get("dataType") or "").lower()
        if dt == "post":
            posts_raw.append(it)
        elif dt == "comment":
            comments_raw.append(it)
        else:
            other.append(it)

    posts_raw = [p for p in posts_raw if not _post_title_and_body_both_empty(p)]

    kept_post_ids = {_post_full_id(p) for p in posts_raw}
    filtered_comments: List[Dict[str, Any]] = []
    for c in comments_raw:
        pk = str(c.get("postId") or "")
        if not pk and c.get("parsedPostId"):
            pk = f"t3_{c['parsedPostId']}"
        if pk in kept_post_ids:
            filtered_comments.append(c)
    comments_raw = filtered_comments

    by_post: Dict[str, List[Dict[str, Any]]] = {}
    for c in comments_raw:
        pk = str(c.get("postId") or "")
        if not pk and c.get("parsedPostId"):
            pk = f"t3_{c['parsedPostId']}"
        if pk not in by_post:
            by_post[pk] = []
        by_post[pk].append(c)

    posts_out: List[Dict[str, Any]] = []
    for p in posts_raw:
        pid = _post_full_id(p)
        comm_rows = by_post.pop(pid, [])
        if comment_depth == "nested":
            comments_out = nest_comment_threads(comm_rows, pid)
        else:
            comments_out = first_level_comments_limited(comm_rows, pid, top_comments_limit)
        posts_out.append({**p, "comments": comments_out})

    orphan_comments: List[Dict[str, Any]] = []
    for _pk, lst in by_post.items():
        orphan_comments.extend(lst)
    if orphan_comments:
        other.append({"dataType": "orphan_comments", "items": orphan_comments})

    return {"posts": posts_out, "other": other}


def reddit_external_user_id(author_id: Any, author_name: str) -> str:
    """发帖人多为 t2_*；评论里 authorId 常为错误的 t1_*，退回 reddit_u_<用户名>。"""
    aid = str(author_id or "").strip()
    an = str(author_name or "").strip()
    if aid.startswith("t2_"):
        return aid
    if aid.startswith("t1_"):
        aid = ""
    if _skip_post_author_name(an):
        return ""
    safe = re.sub(r"[^\w\-.]", "_", an, flags=re.UNICODE)[:200].strip("_")
    if not safe:
        return ""
    return f"reddit_u_{safe.lower()}"


def _reddit_post_text(p: Dict[str, Any]) -> str:
    title = str(p.get("title") or "").strip()
    body = str(p.get("body") or "").strip()
    if title and body:
        return f"{title}\n\n{body}"
    return title or body


def _subreddit_topic_label(p: Dict[str, Any]) -> str:
    s = str(p.get("parsedCommunityName") or p.get("subredditName") or "").strip()
    return s or "reddit"


def _reddit_profile_bio(prof: Optional[Dict[str, Any]]) -> str:
    """Apify 用户页常见字段：bio（简介）、description 等。"""
    if not isinstance(prof, dict) or not prof:
        return ""
    for key in ("bio", "description", "publicDescription", "about"):
        v = prof.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _reddit_total_karma(prof: Dict[str, Any]) -> int:
    try:
        return int(prof.get("totalKarma") or 0)
    except (TypeError, ValueError):
        try:
            return int(prof.get("linkKarma") or 0) + int(prof.get("commentKarma") or 0)
        except (TypeError, ValueError):
            return 0


def _reddit_int_metric(prof: Dict[str, Any], key: str, default: int = 0) -> int:
    """从 authorProfile 取整数字段；缺失或非法则用 default。"""
    if not isinstance(prof, dict):
        return default
    if key not in prof:
        return default
    try:
        return int(prof[key])
    except (TypeError, ValueError):
        return default


def _reddit_pick_longer_bio(prev: str, new: str) -> str:
    a = (prev or "").strip()
    b = (new or "").strip()
    return b if len(b) > len(a) else a


def _merge_reddit_user(
    users: Dict[str, Dict[str, Any]],
    external_id: str,
    author_name: str,
    author_profile: Optional[Dict[str, Any]],
    primary_sub: str,
) -> None:
    if not external_id:
        return
    name = (author_name or "").strip() or external_id[:24]
    prof = author_profile if isinstance(author_profile, dict) else {}
    desc = _reddit_profile_bio(prof)
    total_k = _reddit_total_karma(prof)
    ut = "kol" if total_k > REDDIT_KOL_MIN_TOTAL_KARMA else "normal"
    tlist = [primary_sub] if primary_sub else []
    ex = users.get(external_id)
    if ex is None:
        users[external_id] = {
            "agent_id": None,
            "user_name": str(prof.get("username") or name),
            "name": str(prof.get("name") or prof.get("username") or name),
            "description": desc,
            "profile": {
                "other_info": {
                    "topics": list(tlist),
                    "reddit_profile": prof,
                }
            },
            "recsys_type": "reddit",
            "user_type": ut,
            "twitter_user_id": external_id,
            "followers_count": _reddit_int_metric(prof, "followersCount", 0),
            "following_count": _reddit_int_metric(prof, "followingCount", 0),
            "tweet_count": 0,
            "verified": bool(prof.get("verified")),
            "verified_followers_count": None,
            "location": prof.get("location") if isinstance(prof.get("location"), str) else None,
            "source_topics": list(tlist),
            "_max_karma": total_k,
        }
        return

    ex["user_name"] = ex.get("user_name") or str(prof.get("username") or name)
    ex["name"] = ex.get("name") or str(prof.get("name") or prof.get("username") or name)
    ex["description"] = _reddit_pick_longer_bio(str(ex.get("description") or ""), desc)
    oi = ex.setdefault("profile", {}).setdefault("other_info", {})
    if prof:
        prev = oi.get("reddit_profile")
        if not isinstance(prev, dict) or len(prof.keys()) >= len(prev.keys()):
            oi["reddit_profile"] = prof
    prev_k = int(ex.get("_max_karma") or -1)
    if total_k > prev_k:
        ex["_max_karma"] = total_k
        ex["user_type"] = ut
    if prof:
        ex["verified"] = bool(ex.get("verified")) or bool(prof.get("verified"))
        if "followersCount" in prof:
            ex["followers_count"] = _reddit_int_metric(prof, "followersCount", 0)
        if "followingCount" in prof:
            ex["following_count"] = _reddit_int_metric(prof, "followingCount", 0)
        ex["tweet_count"] = 0
    ot = oi.setdefault("topics", [])
    oi["topics"] = list(dict.fromkeys(list(ot) + tlist))
    ex["source_topics"] = list(dict.fromkeys((ex.get("source_topics") or []) + tlist))


def _collect_reply_rows(
    comments: Any,
    post_full_id: str,
    topic_labels: List[str],
    users: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    primary_sub = topic_labels[0] if topic_labels else ""

    def visit(node: Dict[str, Any], parent_id: str) -> None:
        cid = _comment_full_id(node)
        an = str(node.get("authorName") or "")
        aid = reddit_external_user_id(node.get("authorId"), an)
        if aid:
            _merge_reddit_user(users, aid, an, None, primary_sub)
        body = str(node.get("body") or "").strip()
        rows.append(
            {
                "twitter_reply_id": cid,
                "twitter_author_id": aid,
                "twitter_post_id": post_full_id,
                "parent_external_content_id": parent_id,
                "root_external_content_id": post_full_id,
                "content": body,
                "createdAt": str(node.get("commentCreatedAt") or node.get("createdAt") or ""),
                "language": None,
                "like_count": node.get("commentUpVotes"),
                "reply_count": None,
                "share_count": None,
                "view_count": None,
                "source_topics": topic_labels,
            }
        )
        for ch in node.get("replies") or []:
            if isinstance(ch, dict):
                visit(ch, cid)

    if not isinstance(comments, list):
        return rows
    for node in comments:
        if isinstance(node, dict):
            visit(node, post_full_id)
    return rows


def build_sqlite_payload_from_nested(
    nested: Dict[str, Any],
    *,
    fetch_options: Dict[str, Any],
) -> Dict[str, Any]:
    """把 nested posts+comments 转成 import_payload_to_sqlite 所需的 topics/users/posts/replies。"""
    posts_in = nested.get("posts") or []
    users_acc: Dict[str, Dict[str, Any]] = {}
    posts_sql: List[Dict[str, Any]] = []
    replies_sql: List[Dict[str, Any]] = []
    topic_labels_order: List[str] = []

    for p in posts_in:
        if not isinstance(p, dict):
            continue
        pid = _post_full_id(p)
        sub = _subreddit_topic_label(p)
        if sub not in topic_labels_order:
            topic_labels_order.append(sub)
        tlab = [sub]
        aid = reddit_external_user_id(p.get("authorId"), str(p.get("authorName") or ""))
        if aid:
            _merge_reddit_user(
                users_acc,
                aid,
                str(p.get("authorName") or ""),
                p.get("authorProfile") if isinstance(p.get("authorProfile"), dict) else None,
                sub,
            )

        posts_sql.append(
            {
                "twitter_post_id": pid,
                "twitter_author_id": aid,
                "twitter_conversation_id": pid,
                "content": _reddit_post_text(p),
                "createdAt": str(p.get("createdAt") or ""),
                "language": None,
                "like_count": p.get("upVotes"),
                "reply_count": p.get("commentsCount"),
                "share_count": None,
                "view_count": None,
                "source_topics": tlab,
            }
        )

        replies_sql.extend(
            _collect_reply_rows(p.get("comments") or [], pid, tlab, users_acc),
        )

    topics_dedup = list(dict.fromkeys(topic_labels_order))

    users_list: List[Dict[str, Any]] = []
    for doc in users_acc.values():
        d = dict(doc)
        d.pop("_max_karma", None)
        users_list.append(d)

    return {
        "topics": topics_dedup,
        "users": users_list,
        "posts": posts_sql,
        "replies": replies_sql,
        "meta": {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "topics": len(topics_dedup),
                "users": len(users_list),
                "posts": len(posts_sql),
                "replies": len(replies_sql),
            },
            "trends_processed": [],
            "news_rows": [],
            "fetch_options": fetch_options,
        },
    }


def _build_cli_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "抓取 Reddit 数据（Apify harshmaur/reddit-scraper）并写入统一 SQLite；"
            "默认写入数据库并在 stdout 打印入库摘要 JSON；"
            "--preview 只抓取并打印帖子 JSON（与 fetch_twitter_data 一致）。"
        ),
    )
    p.add_argument(
        "--mode",
        choices=["post", "popular-subreddits", "search-communities", "communities-hot"],
        default="post",
        help="post=单 URL；popular-subreddits=r/popular 帖流；search-communities=关键词搜版块；"
        "communities-hot=多版区热门帖+可选评论",
    )
    p.add_argument(
        "--start-url",
        default=DEFAULT_START_URL,
        help="仅 mode=post：入口 URL",
    )
    p.add_argument(
        "--browse-url",
        default=DEFAULT_POPULAR_FEED_URL,
        help="popular-subreddits：入口 URL（默认 /r/popular；避免 /subreddits/popular 易 403）",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="popular-subreddits / search-communities：上限（映射 maxCommunitiesCount，默认 50）",
    )
    p.add_argument(
        "--search-term",
        dest="search_terms",
        action="append",
        default=None,
        help='search-communities：关键词（可重复传）；不传则用内置一组泛词',
    )
    p.add_argument(
        "--popular-feed-posts",
        type=int,
        default=10,
        help="popular-subreddits：maxPostsCount（默认 10；全 0 可能无数据）",
    )
    p.add_argument(
        "--max-posts",
        type=int,
        default=10,
        help="mode=post：maxPostsCount（默认 10）",
    )
    p.add_argument(
        "--max-comments-per-post",
        type=int,
        default=100,
        help="传给 Apify 的 maxCommentsPerPost：含一级+楼中楼；宜明显大于导出条数，否则一级评论很少（默认 100）",
    )
    p.add_argument(
        "--max-comments-total",
        type=int,
        default=5000,
        help="post / communities-hot：Apify 全站评论总条数上限（默认 5000；多帖时勿过小）",
    )
    p.add_argument(
        "--max-communities",
        type=int,
        default=2,
        help="mode=post：maxCommunitiesCount（默认 2；纯爬帖时可保持较小）",
    )
    p.add_argument(
        "--skip-comments",
        action="store_true",
        help="post / communities-hot：不沿帖爬评论",
    )
    p.add_argument(
        "--fast-mode",
        action="store_true",
        help="mode=post：fastMode（适合 Reddit /search/ 类 startUrl；普通帖页一般不必开）",
    )
    p.add_argument(
        "--include-nsfw",
        action="store_true",
        help="包含 NSFW（默认 false）",
    )
    p.add_argument(
        "--community",
        dest="communities",
        action="append",
        default=None,
        help="communities-hot：子版名称（可多次传）；不传则用脚本内 DEFAULT_COMMUNITIES_HOT；支持 r/name",
    )
    p.add_argument(
        "--feed",
        choices=["hot", "new", "top-day", "top-week", "top-month"],
        default="hot",
        help="communities-hot：每个版的列表排序（默认 hot）",
    )
    p.add_argument(
        "--posts-per-community",
        type=int,
        default=10,
        help="communities-hot：每个版期望拉取的帖子预算（用于估算 maxPostsCount，默认 10）",
    )
    p.add_argument(
        "--actor",
        default=DEFAULT_ACTOR_ID,
        help="Apify Actor ID 或 username~name（默认 harshmaur/reddit-scraper）",
    )
    p.add_argument(
        "--out",
        default="",
        help="可选：抓取结果另存为该路径（stderr 提示）；默认运行 stdout 只为入库摘要，不占满大屏 JSON",
    )
    p.add_argument(
        "--format",
        choices=["nested", "flat"],
        default="nested",
        help="nested=帖内嵌 comments；flat=Actor 原始扁平列表",
    )
    p.add_argument(
        "--comment-depth",
        choices=["top", "nested"],
        default="top",
        help="top=仅一级评论；nested=replies 嵌套树",
    )
    p.add_argument(
        "--top-comments-limit",
        type=int,
        default=5,
        help="comment-depth=top 时每帖导出的一级评论上限（默认 5）；与 Apify --max-comments-per-post 分离",
    )
    p.add_argument(
        "--fetch-post-author-profiles",
        action="store_true",
        help="nested：再跑 Actor，仅抓取发帖人用户页并写入每帖 authorProfile（不抓评论者；额外计费）",
    )
    p.add_argument(
        "--author-profile-max-posts-per-user",
        type=int,
        default=0,
        help="发帖人资料抓取时传给 Actor 的 maxPostsCount（默认 0；若无用户行可试 1）",
    )
    p.add_argument(
        "--author-profile-chunk-size",
        type=int,
        default=80,
        help="每轮合并多少个用户 startUrl（默认 80）",
    )
    p.add_argument(
        "--preview",
        action="store_true",
        help="只输出抓取结果 JSON 到 stdout，不写入 SQLite（与 fetch_twitter_data --preview 一致）",
    )
    p.add_argument(
        "--db-path",
        default=str(DEFAULT_SQLITE_PATH),
        help=(
            f"SQLite 数据库路径，默认 {DEFAULT_SQLITE_PATH}。也可通过环境变量覆盖："
            + ", ".join(_DEFAULT_SQLITE_PATH_ENV_KEYS)
        ),
    )
    return p


def _reddit_fetch_options(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "mode": args.mode,
        "feed": args.feed,
        "actor": args.actor.strip(),
        "format": args.format,
        "comment_depth": args.comment_depth,
        "fetch_post_author_profiles": args.fetch_post_author_profiles,
    }


def run_reddit_pipeline(args: argparse.Namespace) -> Tuple[Any, Dict[str, Any], List[Dict[str, Any]]]:
    """执行 Apify 抓取与整形；返回 (payload, fetch_options, raw_items)。"""
    token = _apify_token()
    if not token:
        raise RuntimeError(
            "Missing APIFY_REDDIT_KEY. Set it in backend/.env or the environment."
        )

    if args.mode == "post":
        run_input = build_run_input_post(
            args.start_url,
            max_posts=args.max_posts,
            max_comments_per_post=args.max_comments_per_post,
            max_comments_total=args.max_comments_total,
            crawl_comments_per_post=not args.skip_comments,
            fast_mode=args.fast_mode,
            include_nsfw=args.include_nsfw,
            max_communities_count=args.max_communities,
        )
    elif args.mode == "search-communities":
        terms = args.search_terms if args.search_terms else DEFAULT_SEARCH_TERMS_COMMUNITIES
        run_input = build_run_input_search_communities(terms, args.limit)
    elif args.mode == "communities-hot":
        comms: List[str] = (
            list(args.communities)
            if args.communities
            else list(DEFAULT_COMMUNITIES_HOT)
        )
        if not comms:
            raise ValueError(
                "No communities: pass --community and/or edit DEFAULT_COMMUNITIES_HOT in the script."
            )
        run_input = build_run_input_communities_hot(
            comms,
            feed=args.feed,
            posts_per_community=args.posts_per_community,
            max_comments_per_post=args.max_comments_per_post,
            max_comments_total=args.max_comments_total,
            crawl_comments_per_post=not args.skip_comments,
            include_nsfw=args.include_nsfw,
        )
    else:
        run_input = build_run_input_popular_subreddits(
            args.limit,
            args.browse_url.strip(),
            feed_posts=args.popular_feed_posts,
        )

    items = run_actor_and_collect_items(token, run_input, args.actor.strip())

    if not items:
        print(
            "WARN: Dataset is empty. If logs show 403 on https://www.reddit.com/subreddits/.../*.json — "
            "Reddit blocked that JSON; use default --browse-url (r/popular) or "
            "--mode search-communities. Also try higher --popular-feed-posts or see Apify run logs.",
            file=sys.stderr,
        )

    n_posts_raw = sum(1 for x in items if str(x.get("dataType") or "").lower() == "post")
    n_empty_tb = sum(
        1
        for x in items
        if str(x.get("dataType") or "").lower() == "post"
        and _post_title_and_body_both_empty(x)
    )
    if n_posts_raw and n_empty_tb:
        print(
            f"Note: excluding {n_empty_tb}/{n_posts_raw} posts with empty title and body.",
            file=sys.stderr,
        )

    if (
        args.format == "nested"
        and args.comment_depth == "top"
        and args.max_comments_per_post < args.top_comments_limit * 3
    ):
        print(
            "Tip: Apify --max-comments-per-post counts nested replies. Set it well above "
            "--top-comments-limit (e.g. 100 vs 5) or you may get very few top-level comments per post.",
            file=sys.stderr,
        )

    if args.format == "nested":
        payload: Any = reshape_posts_with_comments(
            items,
            comment_depth=args.comment_depth,
            top_comments_limit=args.top_comments_limit,
        )
    else:
        payload = filter_items_drop_empty_title_body_posts(items)

    if args.format == "nested" and args.fetch_post_author_profiles:
        posts_list = list(payload.get("posts") or [])
        op_names = unique_post_author_names(posts_list)
        if op_names:
            print(
                f"Fetching post-author profiles ({len(op_names)} unique OPs, comments authors excluded)…",
                file=sys.stderr,
            )
            prof_map = fetch_post_author_profiles(
                token,
                op_names,
                args.actor.strip(),
                max_posts_per_user=args.author_profile_max_posts_per_user,
                chunk_size=args.author_profile_chunk_size,
            )
            attach_author_profiles_to_posts(posts_list, prof_map)
            attached = sum(1 for p in posts_list if p.get("authorProfile"))
            print(
                f"authorProfile attached to {attached}/{len(posts_list)} posts "
                f"({len(prof_map)} unique profiles).",
                file=sys.stderr,
            )

    return payload, _reddit_fetch_options(args), items


def _maybe_write_payload_file(
    payload: Any,
    args: argparse.Namespace,
    items: List[Dict[str, Any]],
) -> None:
    if not (args.out or "").strip():
        return
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if args.format == "nested" and isinstance(payload, dict):
        nop = len(payload.get("posts") or [])
        noo = len(payload.get("other") or [])
        print(
            f"Saved {nop} posts to {out_path}" + (f", other={noo}" if noo else ""),
            file=sys.stderr,
            flush=True,
        )
    else:
        ln = len(payload) if isinstance(payload, list) else len(items)
        print(f"Saved {ln} items to {out_path}", file=sys.stderr, flush=True)


def _run_cli(argv: List[str]) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    try:
        payload, fetch_opts, items = run_reddit_pipeline(args)
    except ValueError as e:
        err = {"error": str(e), "type": "ValueError"}
        print(json.dumps(err, ensure_ascii=False), flush=True)
        return 1
    except RuntimeError as e:
        err = {"error": str(e), "type": "RuntimeError"}
        print(json.dumps(err, ensure_ascii=False), flush=True)
        return 1
    except Exception as e:
        err = {"error": str(e), "type": type(e).__name__}
        print(json.dumps(err, ensure_ascii=False), flush=True)
        return 2

    try:
        if args.preview:
            print(json.dumps(payload, ensure_ascii=False), flush=True)
            _maybe_write_payload_file(payload, args, items)
            return 0

        _maybe_write_payload_file(payload, args, items)

        if args.format != "nested":
            skip = {
                "status": "skipped",
                "reason": "SQLite import requires --format nested",
                "format": args.format,
                "platform": REDDIT_PLATFORM,
                "fetch_options": fetch_opts,
            }
            print(json.dumps(skip, ensure_ascii=False), flush=True)
            return 0

        sqlite_payload = build_sqlite_payload_from_nested(
            payload if isinstance(payload, dict) else {"posts": []},
            fetch_options=fetch_opts,
        )
        db_path = Path(args.db_path).expanduser().resolve()
        if db_path.exists() and db_path.is_dir():
            raise RuntimeError(f"--db-path 指向目录而非文件: {db_path}")
        result = import_reddit_payload_to_sqlite(sqlite_payload, fetch_opts, db_path)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as e:
        err = {
            "status": "error",
            "status_code": 500,
            "type": type(e).__name__,
            "message": str(e),
        }
        print(json.dumps(err, ensure_ascii=False), flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(_run_cli(sys.argv[1:]))
