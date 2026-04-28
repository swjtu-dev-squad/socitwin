"""
Twitter 数据采集脚本
默认行为：X News 搜索 → 新闻详情 cluster post_id → GET /2/tweets → recent 回复 → 结构化数据 → 写入统一 SQLite。
（原「泰国 WOEID 趋势 + search/all」拉取已由 News 链路替代；结构化与入库逻辑不变。）
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import dotenv_values, load_dotenv

# 脚本所在目录 = backend/scripts/datasets
# 后端根目录 = 向上两级
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"

# override=True：避免父进程传入空的 TWITTER_BEARER_TOKEN 时挡住 .env 里的值
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=True)

PLATFORM = "twitter"
# SQLite 各表 `type` 列统一写入该值（与 platform 一致，均为 twitter）
DB_ROW_TYPE = "twitter"
DEFAULT_SQLITE_PATH = _PROJECT_ROOT / "data" / "datasets" / "oasis_datasets.db"


def _twitter_bearer_token() -> str:
    """优先从 .env 文件读取，再读环境变量；避免 spawn 继承空变量导致读不到 token。"""
    if _ENV_FILE.is_file():
        raw = (dotenv_values(_ENV_FILE).get("TWITTER_BEARER_TOKEN") or "").strip()
        if raw:
            return raw
    return (os.getenv("TWITTER_BEARER_TOKEN") or "").strip()

# ============== 可配置区域 ==============
API_BASE_V2 = "https://api.x.com/2"
WOEID = 23424960  # 保留：News 链路不再使用 WOEID 趋势

# --- X News 拉取规模：命令行不传 --max-* 时用这里的值（只改本段即可）---
# MAX_TRENDS            → --max-trends：政治/经济/社会各调一次 News search 的 max_results
# MAX_NEWS_AGE_HOURS   → --max-age-hours：News 搜索的 max_age_hours（1–720）
# MAX_POSTS            → --max-posts：每条新闻故事下参与采集的主帖数量上限
# MAX_REPLIES_PER_POST → --max-replies-per-post：每条主帖用 recent 搜索拉取的回复条数上限
MAX_TRENDS = 10
MAX_NEWS_AGE_HOURS = 168
MAX_POSTS = 10
MAX_REPLIES_PER_POST = 15

# 排序方式
SORT_ORDER = "relevancy"

# 字段与扩展
EXPANSIONS = [
    "author_id",
    "referenced_tweets.id",
    "referenced_tweets.id.author_id",
]
TWEET_FIELDS = [
    "id",
    "text",
    "author_id",
    "in_reply_to_user_id",
    "conversation_id",
    "created_at",
    "lang",
    "public_metrics",
    "article",
    "community_id",
]
USER_FIELDS = [
    "id",
    "name",
    "username",
    "location",
    "description",
    "entities",
    "affiliation",
    "subscription",
    "subscription_type",
    "verified_followers_count",
    "verified",
    "created_at",
    "public_metrics",
    "protected",
]
PLACE_FIELDS = [
    "id",
    "full_name",
    "name",
    "country",
    "place_type",
]

# 基础过滤
BASE_QUERY_FILTERS = "-is:retweet -is:quote"

# URL 正则
URL_REGEX = re.compile(r"https?://\S+")
# =======================================

_session: Optional[requests.Session] = None


def _log(msg: str) -> None:
    """进度日志打到 stderr，便于 --preview 时 stdout 仅输出一行 JSON。"""
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _topic_key(topic_label: str) -> str:
    if not isinstance(topic_label, str):
        return ""
    return " ".join(topic_label.strip().lower().split())


def _topic_key_to_news_id_map(news_rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """规范化后的新闻标题 topic_key → X News id（news_rows 去重顺序中后者覆盖前者同 key 时极少见）。"""
    m: Dict[str, str] = {}
    for r in news_rows:
        if not isinstance(r, dict):
            continue
        label = str(r.get("name") or "").strip()
        nid = str(r.get("news_id") or "").strip()
        if label and nid:
            m[_topic_key(label)] = nid
    return m


def _json_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
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
    _migrate_topics_news_external_id(conn)
    _migrate_user_topics_news_external_id(conn)
    for _tbl in ("topics", "users", "contents", "content_topics", "user_topics"):
        _migrate_table_row_type(conn, _tbl)
    # DDL/迁移后可能仍处于隐式事务中，若不提交，后续 execute("BEGIN") 会报「事务中不能再开事务」
    conn.commit()


def _migrate_table_row_type(conn: sqlite3.Connection, table: str) -> None:
    """旧表无 type 列时添加，并统一为 twitter。"""
    cur = conn.execute(f"PRAGMA table_info({table})")
    col_names = {row[1] for row in cur.fetchall()}
    if not col_names or "type" in col_names:
        return
    # SQLite ALTER … DEFAULT 不支持占位符，此处表名来自白名单元组
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "type" TEXT DEFAULT \'{DB_ROW_TYPE}\'')
    conn.execute(f'UPDATE "{table}" SET "type" = ? WHERE "type" IS NULL', (DB_ROW_TYPE,))


def _migrate_user_topics_news_external_id(conn: sqlite3.Connection) -> None:
    """旧库 user_topics 表无 news_external_id 时补齐列。"""
    cur = conn.execute("PRAGMA table_info(user_topics)")
    col_names = {row[1] for row in cur.fetchall()}
    if col_names and "news_external_id" not in col_names:
        conn.execute("ALTER TABLE user_topics ADD COLUMN news_external_id TEXT")


def _migrate_topics_news_external_id(conn: sqlite3.Connection) -> None:
    """旧库 topics 表无 news_external_id 时补齐列。"""
    cur = conn.execute("PRAGMA table_info(topics)")
    col_names = {row[1] for row in cur.fetchall()}
    if col_names and "news_external_id" not in col_names:
        conn.execute("ALTER TABLE topics ADD COLUMN news_external_id TEXT")


def import_payload_to_sqlite(
    payload: Dict[str, Any],
    fetch_options: Dict[str, Any],
    db_path: Path,
    platform: str = PLATFORM,
) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    row_type = DB_ROW_TYPE

    collected_at = _normalize_string(payload.get("meta", {}).get("collected_at")) or _now_iso()
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
    topic_key_to_news_id = _topic_key_to_news_id_map([x for x in news_rows_meta if isinstance(x, dict)])

    trend_order = {
        _topic_key(clean_query_to_topic(str(topic))): idx + 1
        for idx, topic in enumerate(trends_payload or [])
        if _topic_key(clean_query_to_topic(str(topic)))
    }

    topic_labels: Dict[str, str] = {}
    topic_post_count: Dict[str, int] = {}
    topic_reply_count: Dict[str, int] = {}
    topic_users: Dict[str, set[str]] = {}
    user_topic_stats: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def ensure_topic(topic_label: str) -> Optional[str]:
        topic_key = _topic_key(topic_label)
        if not topic_key:
            return None
        if topic_key not in topic_labels:
            topic_labels[topic_key] = topic_label
            topic_post_count[topic_key] = 0
            topic_reply_count[topic_key] = 0
            topic_users[topic_key] = set()
        return topic_key

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
        external_content_id = _normalize_string(post.get("twitter_post_id"))
        author_external_user_id = _normalize_string(post.get("twitter_author_id"))
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
                _normalize_string(post.get("twitter_conversation_id")) or external_content_id,
                _normalize_string(post.get("content")) or None,
                _normalize_string(post.get("language")) or None,
                _normalize_string(post.get("createdAt")) or None,
                post.get("like_count"),
                post.get("reply_count"),
                post.get("share_count"),
                post.get("view_count"),
                _json_text(post),
            )
        )

        for topic_label in post.get("source_topics", []) or []:
            if not isinstance(topic_label, str):
                continue
            topic_key = ensure_topic(topic_label)
            if not topic_key:
                continue
            content_topic_rows.append((platform, row_type, external_content_id, topic_key, 1.0))
            topic_post_count[topic_key] = topic_post_count.get(topic_key, 0) + 1
            track_user_topic(topic_key, author_external_user_id, "author")

    for reply in replies_payload:
        if not isinstance(reply, dict):
            continue
        external_content_id = _normalize_string(reply.get("twitter_reply_id"))
        author_external_user_id = _normalize_string(reply.get("twitter_author_id"))
        parent_external_content_id = _normalize_string(reply.get("twitter_post_id"))
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
                parent_external_content_id or None,
                _normalize_string(reply.get("content")) or None,
                _normalize_string(reply.get("language")) or None,
                _normalize_string(reply.get("createdAt")) or None,
                reply.get("like_count"),
                reply.get("reply_count"),
                reply.get("share_count"),
                reply.get("view_count"),
                _json_text(reply),
            )
        )

        for topic_label in reply.get("source_topics", []) or []:
            if not isinstance(topic_label, str):
                continue
            topic_key = ensure_topic(topic_label)
            if not topic_key:
                continue
            content_topic_rows.append((platform, row_type, external_content_id, topic_key, 1.0))
            topic_reply_count[topic_key] = topic_reply_count.get(topic_key, 0) + 1
            track_user_topic(topic_key, author_external_user_id, "replier")

    users_rows: List[Tuple[Any, ...]] = []
    for user in users_payload:
        if not isinstance(user, dict):
            continue
        external_user_id = _normalize_string(user.get("twitter_user_id"))
        if not external_user_id:
            continue
        users_rows.append(
            (
                platform,
                row_type,
                external_user_id,
                _normalize_string(user.get("user_name")) or None,
                _normalize_string(user.get("name")) or None,
                _normalize_string(user.get("description")) or None,
                _normalize_string(user.get("location")) or None,
                1 if bool(user.get("verified")) else 0,
                user.get("followers_count"),
                user.get("following_count"),
                user.get("tweet_count"),
                _normalize_string(user.get("user_type")) or None,
                _json_text(user.get("profile")),
                _json_text(user),
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
                _json_text(
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
        _ensure_sqlite_schema(conn)
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN")

        # 按 id 去重：库中已存在则跳过插入（不再整表 DELETE）
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


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        token = _twitter_bearer_token()
        if not token:
            hint = f"（已查找: {_ENV_FILE}）" if _ENV_FILE.is_file() else f"（未找到文件: {_ENV_FILE}，请把 .env 放在项目根目录）"
            raise RuntimeError(
                "缺少 TWITTER_BEARER_TOKEN：请在项目根目录 .env 中设置 TWITTER_BEARER_TOKEN=你的token " + hint
            )
        _session = requests.Session()
        _session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
    return _session


@dataclass
class APIError(Exception):
    status_code: int
    detail: str


def _request(method: str, url: str, **kwargs) -> Dict[str, Any]:
    resp = _get_session().request(method, url, timeout=60, **kwargs)
    if not resp.ok:
        raw_file = f"error_raw_{int(time.time())}.json"
        try:
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(resp.text)
        except Exception:
            pass
        raise APIError(resp.status_code, f"HTTP {resp.status_code}, raw saved to {raw_file}: {resp.text[:500]}")
    try:
        return resp.json()
    except ValueError:
        raw_file = f"error_nonjson_{int(time.time())}.txt"
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(resp.text)
        raise APIError(resp.status_code, f"响应非 JSON，已保存到 {raw_file}")


def _join(vals: List[str]) -> str:
    uniq = sorted({v for v in vals if v and v.strip()})
    return ",".join(uniq)


# ============== X 数据：News → cluster post_id → tweets / recent replies ==============
NEWS_AXIS_QUERIES: List[Tuple[str, str]] = [
    ("politics", "politics government election policy legislature diplomacy"),
    ("economy", "economy finance business market inflation trade employment"),
    ("society", "society social public health education justice immigration community"),
]
EXPANSIONS_TWEET_NEWS = "author_id,referenced_tweets.id"


def _news_rest_id(item: Dict[str, Any]) -> str:
    return str(item.get("id") or item.get("rest_id") or "").strip()


def _is_retweet_tweet(tweet: Dict[str, Any]) -> bool:
    refs = tweet.get("referenced_tweets")
    if isinstance(refs, list):
        for ref in refs:
            if isinstance(ref, dict) and ref.get("type") == "retweeted":
                return True
    text = (tweet.get("text") or "").lstrip()
    if text.startswith("RT @"):
        return True
    return False


def search_news_api(query: str, max_results: int, max_age_hours: int) -> List[Dict[str, Any]]:
    url = f"{API_BASE_V2}/news/search"
    params = {
        "query": query,
        "max_results": max(1, min(100, max_results)),
        "max_age_hours": max(1, min(720, max_age_hours)),
        "news.fields": "id,name,summary,category",
    }
    data = _request("GET", url, params=params)
    rows = data.get("data")
    if not isinstance(rows, list):
        return []
    return [x for x in rows if isinstance(x, dict)]


def get_news_by_id_api(news_id: str) -> Dict[str, Any]:
    url = f"{API_BASE_V2}/news/{news_id}"
    params = {"news.fields": "id,name,cluster_posts_results,summary,category"}
    data = _request("GET", url, params=params)
    d = data.get("data")
    if not isinstance(d, dict):
        raise APIError(422, f"news/{news_id} 无 data")
    return d


def get_tweets_batch_news(ids: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    if not ids:
        return [], {}
    url = f"{API_BASE_V2}/tweets"
    chunk: List[Dict[str, Any]] = []
    users: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(ids), 100):
        part = ids[i : i + 100]
        params = {
            "ids": ",".join(part),
            "tweet.fields": _join(TWEET_FIELDS),
            "expansions": EXPANSIONS_TWEET_NEWS,
            "user.fields": _join(USER_FIELDS),
        }
        data = _request("GET", url, params=params)
        for t in data.get("data") or []:
            if isinstance(t, dict):
                chunk.append(t)
        inc = data.get("includes") or {}
        for u in inc.get("users") or []:
            if isinstance(u, dict) and u.get("id"):
                users[str(u["id"])] = u
        time.sleep(0.05)
    return chunk, users


def search_recent_replies_news(root_tweet_id: str, max_results: int) -> List[Dict[str, Any]]:
    url = f"{API_BASE_V2}/tweets/search/recent"
    q = f"conversation_id:{root_tweet_id} -is:retweet"
    params = {
        "query": q,
        "max_results": min(100, max(10, max_results + 5)),
        "tweet.fields": _join(
            [
                "id",
                "text",
                "author_id",
                "created_at",
                "conversation_id",
                "referenced_tweets",
                "lang",
                "public_metrics",
            ]
        ),
    }
    try:
        data = _request("GET", url, params=params)
    except APIError:
        return []
    out: List[Dict[str, Any]] = []
    for t in data.get("data") or []:
        if not isinstance(t, dict):
            continue
        if str(t.get("id")) == str(root_tweet_id):
            continue
        if _is_retweet_tweet(t):
            continue
        out.append(t)
        if len(out) >= max_results:
            break
    time.sleep(0.12)
    return out


def get_users_batch_news(user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not user_ids:
        return {}
    url = f"{API_BASE_V2}/users"
    users: Dict[str, Dict[str, Any]] = {}
    uniq = list(dict.fromkeys(user_ids))
    for i in range(0, len(uniq), 100):
        part = uniq[i : i + 100]
        params = {"ids": ",".join(part), "user.fields": _join(USER_FIELDS)}
        data = _request("GET", url, params=params)
        for u in data.get("data") or []:
            if isinstance(u, dict) and u.get("id"):
                users[str(u["id"])] = u
        time.sleep(0.05)
    return users


def fetch_trending_news_topic_rows(
    *,
    max_news_per_axis: Optional[int] = None,
    max_age_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    仅从 X API GET /2/news/search 拉取热点话题列表（政治 / 经济 / 社会三轴），
    与 run_fetch_pipeline 里 meta.trends_processed / news_rows 同源；按 news_id 去重。
    不请求 cluster、tweets、回复，不入库。
    """
    _get_session()
    mna = MAX_TRENDS if max_news_per_axis is None else max_news_per_axis
    mah = MAX_NEWS_AGE_HOURS if max_age_hours is None else max_age_hours

    news_rows: List[Dict[str, Any]] = []
    for axis, q in NEWS_AXIS_QUERIES:
        try:
            items = search_news_api(q, max_results=mna, max_age_hours=mah)
        except APIError as e:
            _log(f"[News] 轴 {axis} 搜索失败: {e.status_code} {e.detail}")
            items = []
        for it in items:
            nid = _news_rest_id(it)
            name = str(it.get("name") or "").strip()
            if not (nid and name):
                continue
            row: Dict[str, Any] = {
                "news_id": nid,
                "name": name,
                "axis": axis,
                "search_query": q,
            }
            summ = str(it.get("summary") or "").strip()
            if summ:
                row["summary"] = summ
            cat = it.get("category")
            if cat is not None and cat != "":
                row["category"] = cat if isinstance(cat, str) else json.dumps(cat, ensure_ascii=False)
            news_rows.append(row)
        time.sleep(0.15)

    seen_nid: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for row in news_rows:
        k = row["news_id"]
        if k in seen_nid:
            continue
        seen_nid.add(k)
        deduped.append(row)

    for idx, row in enumerate(deduped, start=1):
        row["trend_rank"] = idx

    return deduped


def fetch_news_raw_bundle(
    *,
    max_news_per_axis: int,
    max_age_hours: int,
    max_replies_per_post: int,
) -> Dict[str, Any]:
    """News 搜索 → 详情 cluster → GET /2/tweets → recent 回复；供下游拼成旧 posts_data。"""
    news_rows: List[Dict[str, Any]] = []
    for axis, q in NEWS_AXIS_QUERIES:
        try:
            items = search_news_api(q, max_results=max_news_per_axis, max_age_hours=max_age_hours)
        except APIError as e:
            _log(f"[News] 轴 {axis} 搜索失败: {e.status_code} {e.detail}")
            items = []
        for it in items:
            nid = _news_rest_id(it)
            name = str(it.get("name") or "").strip()
            if nid and name:
                news_rows.append({"news_id": nid, "name": name, "axis": axis, "search_query": q})
        time.sleep(0.15)

    seen_nid: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for row in news_rows:
        k = row["news_id"]
        if k in seen_nid:
            continue
        seen_nid.add(k)
        deduped.append(row)
    news_rows = deduped

    post_to_news_names: Dict[str, Set[str]] = {}
    post_order: List[str] = []

    for row in news_rows:
        nid = row["news_id"]
        nm = row["name"]
        try:
            detail = get_news_by_id_api(nid)
        except APIError as e:
            _log(f"[News] 详情失败 news_id={nid}: {e.status_code} {e.detail}")
            time.sleep(0.2)
            continue
        cpr = detail.get("cluster_posts_results")
        if not isinstance(cpr, list):
            time.sleep(0.1)
            continue
        for cell in cpr:
            if not isinstance(cell, dict):
                continue
            pid = str(cell.get("post_id") or "").strip()
            if not pid:
                continue
            if pid not in post_to_news_names:
                post_to_news_names[pid] = set()
                post_order.append(pid)
            post_to_news_names[pid].add(nm)
        time.sleep(0.12)

    if not post_order:
        return {
            "news_rows": news_rows,
            "kept_posts": [],
            "root_to_reply_rows": {},
            "user_by_id": {},
        }

    tweets, tw_users = get_tweets_batch_news(post_order)
    tid_to_tweet = {str(t.get("id")): t for t in tweets if t.get("id")}

    kept_posts: List[Dict[str, Any]] = []
    for pid in post_order:
        t = tid_to_tweet.get(pid)
        if not t:
            continue
        if _is_retweet_tweet(t):
            continue
        kept_posts.append(
            {
                "tweet": t,
                "post_id_str": pid,
                "news_names": sorted(post_to_news_names.get(pid, set())),
            }
        )

    root_to_reply_rows: Dict[str, List[Dict[str, Any]]] = {}
    for kp in kept_posts:
        root_id = str(kp["tweet"].get("id"))
        rel = search_recent_replies_news(root_id, max_results=max_replies_per_post)
        root_to_reply_rows[root_id] = rel

    author_ids: List[str] = []
    reply_author_ids: List[str] = []
    for kp in kept_posts:
        aid = str(kp["tweet"].get("author_id") or "").strip()
        if aid:
            author_ids.append(aid)
    for rel in root_to_reply_rows.values():
        for rt in rel:
            ra = str(rt.get("author_id") or "").strip()
            if ra:
                reply_author_ids.append(ra)

    user_by_id = get_users_batch_news(list(dict.fromkeys(author_ids + reply_author_ids)))
    for uid, u in tw_users.items():
        if uid not in user_by_id:
            user_by_id[uid] = u

    return {
        "news_rows": news_rows,
        "kept_posts": kept_posts,
        "root_to_reply_rows": root_to_reply_rows,
        "user_by_id": user_by_id,
    }


def build_posts_data_for_news_label(
    news_label: str,
    *,
    bundle: Dict[str, Any],
    max_posts_per_story: int,
) -> Dict[str, Any]:
    """与旧 fetch_trend_posts 相同的外层结构，供 collect_structured_entities 使用。"""
    kept_posts: List[Dict[str, Any]] = bundle.get("kept_posts") or []
    root_to_reply_rows: Dict[str, List[Dict[str, Any]]] = bundle.get("root_to_reply_rows") or {}
    user_by_id: Dict[str, Dict[str, Any]] = bundle.get("user_by_id") or {}

    main_query = f"{news_label} {BASE_QUERY_FILTERS}".strip()
    items: List[Dict[str, Any]] = []
    used = 0
    for kp in kept_posts:
        if news_label not in (kp.get("news_names") or []):
            continue
        if max_posts_per_story > 0 and used >= max_posts_per_story:
            break
        used += 1
        t = kp["tweet"]
        aid = str(t.get("author_id") or "")
        author = user_by_id.get(aid) or {}
        root_id = str(t.get("id"))
        rel = list(root_to_reply_rows.get(root_id, []))
        reply_authors = [user_by_id.get(str(rt.get("author_id") or "")) or {} for rt in rel]
        items.append(
            {
                "post": t,
                "author": author,
                "replies": rel,
                "reply_authors": reply_authors,
                "reply_error": None,
            }
        )

    um: Dict[str, Dict[str, Any]] = {}
    for it in items:
        a = it.get("author") or {}
        if a.get("id"):
            um[str(a["id"])] = a
        for ra in it.get("reply_authors") or []:
            if isinstance(ra, dict) and ra.get("id"):
                um[str(ra["id"])] = ra

    return {
        "query": main_query,
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "results": items,
        "users": list(um.values()),
        "stats": {"posts": len(items), "unique_users": len(um)},
    }


# ============== Step 3: 提取用户和帖子信息 ==============
def clean_query_to_topic(query: str) -> str:
    """从 query 字段生成主话题"""
    if not isinstance(query, str):
        return ""
    topic = query.replace(" -is:retweet", "").replace(" -is:quote", "").strip()
    topic = " ".join(topic.split())
    return topic


def followers_to_user_type(followers_count: int) -> str:
    return "kol" if followers_count is not None and followers_count > 20000 else "normal"


def parse_followers(pm: Any) -> Optional[int]:
    if not isinstance(pm, dict):
        return None
    fc = pm.get("followers_count")
    if isinstance(fc, int):
        return fc
    try:
        return int(fc)
    except Exception:
        return None


def parse_created_at(ts: Any) -> str:
    """解析创建时间"""
    if not ts:
        return ""
    if isinstance(ts, str):
        txt = ts.strip()
        try:
            if txt.endswith("Z"):
                dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(txt)
            return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds")
        except Exception:
            return txt
    return str(ts)


def parse_metric(payload: Any, key: str) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return None


def strip_urls(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return URL_REGEX.sub("", text).strip()


def _merge_topics(existing_topics: List[str], topics: List[str]) -> List[str]:
    merged = list(existing_topics)
    for topic in topics:
        if topic and topic not in merged:
            merged.append(topic)
    return merged


def _merge_user_record(users_map: Dict[str, Dict[str, Any]], user_id: str, author: Dict[str, Any], topic: str) -> None:
    if not user_id:
        return

    username = author.get("username") or f"twitter_user_{user_id}"
    name = author.get("name") or username
    description = author.get("description") or ""
    followers_count = parse_followers(author.get("public_metrics")) or 0
    following_count = None
    tweet_count = None
    if isinstance(author.get("public_metrics"), dict):
        following_count = author["public_metrics"].get("following_count")
        tweet_count = author["public_metrics"].get("tweet_count")

    existing = users_map.get(user_id)
    topic_list = [topic] if topic else []

    if existing is None:
        users_map[user_id] = {
            "agent_id": None,
            "user_name": username,
            "name": name,
            "description": description,
            "profile": {
                "other_info": {
                    "topics": topic_list,
                    "gender": None,
                    "age": None,
                    "mbti": None,
                    "country": author.get("location") or None,
                }
            },
            "recsys_type": "twitter",
            "user_type": followers_to_user_type(followers_count),
            "twitter_user_id": user_id,
            "followers_count": followers_count,
            "following_count": following_count,
            "tweet_count": tweet_count,
            "verified": bool(author.get("verified")),
            "verified_followers_count": author.get("verified_followers_count"),
            "location": author.get("location"),
            "source_topics": topic_list,
        }
        return

    existing["user_name"] = existing.get("user_name") or username
    existing["name"] = existing.get("name") or name
    existing["description"] = existing.get("description") or description
    existing["followers_count"] = max(int(existing.get("followers_count") or 0), followers_count)
    existing["following_count"] = existing.get("following_count") or following_count
    existing["tweet_count"] = existing.get("tweet_count") or tweet_count
    existing["verified"] = bool(existing.get("verified")) or bool(author.get("verified"))
    existing["verified_followers_count"] = existing.get("verified_followers_count") or author.get("verified_followers_count")
    existing["location"] = existing.get("location") or author.get("location")
    existing["user_type"] = followers_to_user_type(int(existing.get("followers_count") or 0))

    other_info = existing.setdefault("profile", {}).setdefault("other_info", {})
    other_info["topics"] = _merge_topics(other_info.get("topics", []), topic_list)
    if not other_info.get("country") and author.get("location"):
        other_info["country"] = author.get("location")
    existing["source_topics"] = _merge_topics(existing.get("source_topics", []), topic_list)


def collect_structured_entities(
    posts_payload: Dict[str, Any],
) -> Tuple[List[str], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """提取并规范化用户、帖子、回复，使用 Twitter 原始 ID 去重"""
    primary_topic = clean_query_to_topic(posts_payload.get("query", ""))
    results = posts_payload.get("results", [])

    users_map: Dict[str, Dict[str, Any]] = {}
    posts_map: Dict[str, Dict[str, Any]] = {}
    replies_map: Dict[str, Dict[str, Any]] = {}

    for item in results:
        post = item.get("post", {}) or {}
        author = item.get("author", {}) or {}
        twitter_author_id = str(author.get("id") or post.get("author_id") or "").strip()
        twitter_post_id = str(post.get("id") or "").strip()

        if not twitter_author_id or not twitter_post_id:
            continue

        _merge_user_record(users_map, twitter_author_id, author, primary_topic)

        existing_post = posts_map.get(twitter_post_id)
        post_topics = [primary_topic] if primary_topic else []
        if existing_post is None:
            posts_map[twitter_post_id] = {
                "post_id": None,
                "post_user": author.get("username") or f"twitter_user_{twitter_author_id}",
                "agent_id": None,
                "content": strip_urls(post.get("text")),
                "createdAt": parse_created_at(post.get("created_at")),
                "twitter_post_id": twitter_post_id,
                "twitter_author_id": twitter_author_id,
                "twitter_conversation_id": str(post.get("conversation_id") or post.get("id") or ""),
                "language": post.get("lang"),
                "like_count": parse_metric(post.get("public_metrics"), "like_count"),
                "reply_count": parse_metric(post.get("public_metrics"), "reply_count"),
                "share_count": parse_metric(post.get("public_metrics"), "retweet_count"),
                "view_count": parse_metric(post.get("public_metrics"), "impression_count"),
                "source_topics": post_topics,
            }
        else:
            existing_post["source_topics"] = _merge_topics(existing_post.get("source_topics", []), post_topics)

        replies = item.get("replies", []) or []
        reply_authors = item.get("reply_authors", []) or []
        for idx, reply in enumerate(replies):
            if not isinstance(reply, dict):
                continue
            reply_author = reply_authors[idx] if idx < len(reply_authors) and isinstance(reply_authors[idx], dict) else {}
            twitter_reply_id = str(reply.get("id") or "").strip()
            twitter_reply_author_id = str(reply_author.get("id") or reply.get("author_id") or "").strip()
            if not twitter_reply_id or not twitter_reply_author_id:
                continue

            _merge_user_record(users_map, twitter_reply_author_id, reply_author, primary_topic)

            existing_reply = replies_map.get(twitter_reply_id)
            if existing_reply is None:
                replies_map[twitter_reply_id] = {
                    "reply_id": None,
                    "reply_user": reply_author.get("username") or f"twitter_user_{twitter_reply_author_id}",
                    "re_agent_id": None,
                    "post_id": None,
                    "post_user": author.get("username") or f"twitter_user_{twitter_author_id}",
                    "content": strip_urls(reply.get("text")),
                    "createdAt": parse_created_at(reply.get("created_at")),
                    "twitter_reply_id": twitter_reply_id,
                    "twitter_post_id": twitter_post_id,
                    "twitter_author_id": twitter_reply_author_id,
                    "twitter_reply_to_user_id": twitter_author_id,
                    "language": reply.get("lang"),
                    "like_count": parse_metric(reply.get("public_metrics"), "like_count"),
                    "reply_count": parse_metric(reply.get("public_metrics"), "reply_count"),
                    "share_count": parse_metric(reply.get("public_metrics"), "retweet_count"),
                    "view_count": parse_metric(reply.get("public_metrics"), "impression_count"),
                    "source_topics": post_topics,
                }
            else:
                existing_reply["source_topics"] = _merge_topics(existing_reply.get("source_topics", []), post_topics)

    _log(
        f"[Step 3] 提取到: 话题='{primary_topic}', {len(users_map)} 个用户, "
        f"{len(posts_map)} 条帖子, {len(replies_map)} 条回复"
    )
    return [primary_topic] if primary_topic else [], users_map, posts_map, replies_map


def finalize_entities(
    all_topics: List[str],
    all_users_map: Dict[str, Dict[str, Any]],
    all_posts_map: Dict[str, Dict[str, Any]],
    all_replies_map: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    topics_dedup = list(dict.fromkeys(all_topics))

    users_out: List[Dict[str, Any]] = []
    uid_to_agent: Dict[str, int] = {}

    for idx, (twitter_user_id, user_doc) in enumerate(all_users_map.items()):
        user_copy = json.loads(json.dumps(user_doc))
        user_copy["agent_id"] = idx
        other_info = user_copy.setdefault("profile", {}).setdefault("other_info", {})
        other_info["topics"] = list(dict.fromkeys(other_info.get("topics", [])))
        user_copy["source_topics"] = list(dict.fromkeys(user_copy.get("source_topics", [])))
        uid_to_agent[twitter_user_id] = idx
        users_out.append(user_copy)

    posts_out: List[Dict[str, Any]] = []
    post_id_by_twitter: Dict[str, int] = {}
    for idx, post_doc in enumerate(all_posts_map.values()):
        post_copy = json.loads(json.dumps(post_doc))
        post_copy["post_id"] = idx
        post_copy["agent_id"] = (
            str(uid_to_agent[post_copy["twitter_author_id"]])
            if post_copy.get("twitter_author_id") in uid_to_agent
            else None
        )
        post_copy["source_topics"] = list(dict.fromkeys(post_copy.get("source_topics", [])))
        post_id_by_twitter[post_copy["twitter_post_id"]] = idx
        posts_out.append(post_copy)

    replies_out: List[Dict[str, Any]] = []
    for reply_doc in all_replies_map.values():
        twitter_post_id = reply_doc.get("twitter_post_id")
        if twitter_post_id not in post_id_by_twitter:
            continue
        reply_copy = json.loads(json.dumps(reply_doc))
        reply_copy["reply_id"] = len(replies_out)
        reply_copy["post_id"] = post_id_by_twitter[twitter_post_id]
        reply_copy["re_agent_id"] = (
            str(uid_to_agent[reply_copy["twitter_author_id"]])
            if reply_copy.get("twitter_author_id") in uid_to_agent
            else None
        )
        reply_copy["source_topics"] = list(dict.fromkeys(reply_copy.get("source_topics", [])))
        replies_out.append(reply_copy)

    return topics_dedup, users_out, posts_out, replies_out


def run_fetch_pipeline(
    max_trends: Optional[int] = None,
    max_posts: Optional[int] = None,
    max_replies_per_post: Optional[int] = None,
    sort_order: Optional[str] = None,
    max_age_hours: Optional[int] = None,
) -> Dict[str, Any]:
    """
    执行完整采集流程，返回可 JSON 序列化的结果（供 HTTP 接口或 --preview 使用）。
    首次请求前会检查 TWITTER_BEARER_TOKEN。
    X 数据拉取为 News → cluster → /2/tweets → search/recent；sort_order 参数保留兼容，不参与 News 请求。
    """
    _ = sort_order  # 保留签名；News 链路不使用 search/all 的 sort_order
    _get_session()

    mt = MAX_TRENDS if max_trends is None else max_trends
    mp = MAX_POSTS if max_posts is None else max_posts
    mr = MAX_REPLIES_PER_POST if max_replies_per_post is None else max_replies_per_post
    mah = MAX_NEWS_AGE_HOURS if max_age_hours is None else max_age_hours

    _log(f"[News] 拉取 bundle（每轴 max_results={mt}, max_age_hours={mah}, 每帖回复≤{mr}）…")
    try:
        bundle = fetch_news_raw_bundle(
            max_news_per_axis=mt,
            max_age_hours=mah,
            max_replies_per_post=mr,
        )
    except APIError as e:
        raise RuntimeError(f"[News] 拉取失败: HTTP {e.status_code} {e.detail}") from e

    news_rows: List[Dict[str, Any]] = bundle.get("news_rows") or []
    if not news_rows and not (bundle.get("kept_posts") or []):
        raise RuntimeError("[News] 未获取到任何新闻或帖子")

    trends = [row["name"] for row in news_rows]

    all_topics: List[str] = []
    all_users_map: Dict[str, Dict[str, Any]] = {}
    all_posts_map: Dict[str, Dict[str, Any]] = {}
    all_replies_map: Dict[str, Dict[str, Any]] = {}
    all_raw_posts: List[Dict[str, Any]] = []

    for i, row in enumerate(news_rows):
        trend_name = row["name"]
        _log(f"\n--- 处理新闻 {i + 1}/{len(news_rows)}: {trend_name} ---")

        posts_data = build_posts_data_for_news_label(
            trend_name,
            bundle=bundle,
            max_posts_per_story=mp,
        )

        if not posts_data.get("results"):
            _log(f"[News] 新闻 '{trend_name}' 无帖子数据，跳过")
            continue

        topics, users_map, posts_map, replies_map = collect_structured_entities(posts_data)

        all_topics.extend(topics)
        for uid, user_doc in users_map.items():
            if uid in all_users_map:
                _merge_user_record(
                    all_users_map,
                    uid,
                    {
                        "username": user_doc.get("user_name"),
                        "name": user_doc.get("name"),
                        "description": user_doc.get("description"),
                        "location": user_doc.get("location"),
                        "verified": user_doc.get("verified"),
                        "verified_followers_count": user_doc.get("verified_followers_count"),
                        "public_metrics": {
                            "followers_count": user_doc.get("followers_count"),
                            "following_count": user_doc.get("following_count"),
                            "tweet_count": user_doc.get("tweet_count"),
                        },
                    },
                    topics[0] if topics else "",
                )
            else:
                all_users_map[uid] = user_doc

        for twitter_post_id, post_doc in posts_map.items():
            if twitter_post_id in all_posts_map:
                all_posts_map[twitter_post_id]["source_topics"] = _merge_topics(
                    all_posts_map[twitter_post_id].get("source_topics", []),
                    post_doc.get("source_topics", []),
                )
            else:
                all_posts_map[twitter_post_id] = post_doc

        for twitter_reply_id, reply_doc in replies_map.items():
            if twitter_reply_id in all_replies_map:
                all_replies_map[twitter_reply_id]["source_topics"] = _merge_topics(
                    all_replies_map[twitter_reply_id].get("source_topics", []),
                    reply_doc.get("source_topics", []),
                )
            else:
                all_replies_map[twitter_reply_id] = reply_doc

        all_raw_posts.append(
            {
                "trend_name": trend_name,
                "news_id": row.get("news_id"),
                "axis": row.get("axis"),
                "query": posts_data.get("query"),
                "stats": posts_data.get("stats"),
                "results_count": len(posts_data.get("results", [])),
            }
        )

        if i < len(news_rows) - 1:
            time.sleep(1)

    topics_dedup, all_users, all_posts, all_replies = finalize_entities(
        all_topics,
        all_users_map,
        all_posts_map,
        all_replies_map,
    )
    all_posts_texts = [post.get("content", "") for post in all_posts if post.get("content")]
    all_replies_texts = [reply.get("content", "") for reply in all_replies if reply.get("content")]

    meta_news_rows_out: List[Dict[str, Any]] = [
        {
            "news_id": str(r.get("news_id") or ""),
            "name": r.get("name"),
            "axis": r.get("axis"),
            "search_query": r.get("search_query", ""),
        }
        for r in news_rows
        if isinstance(r, dict)
    ]
    tk_to_nid = _topic_key_to_news_id_map(news_rows)
    news_topics_meta: List[Dict[str, Any]] = []
    for t in topics_dedup:
        tk = _topic_key(clean_query_to_topic(str(t)))
        news_topics_meta.append({"name": t, "news_id": tk_to_nid.get(tk), "topic_key": tk})

    return {
        "topics": topics_dedup,
        "topics_document": {
            "twitter_trends": topics_dedup,
            "news_topics": news_topics_meta,
        },
        "users": all_users,
        "posts": all_posts,
        "replies": all_replies,
        "posts_texts": all_posts_texts,
        "replies_texts": all_replies_texts,
        "meta": {
            "trends_processed": trends,
            "news_rows": meta_news_rows_out,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "trends_data": all_raw_posts,
            "counts": {
                "topics": len(topics_dedup),
                "users": len(all_users),
                "posts": len(all_posts),
                "replies": len(all_replies),
                "posts_texts": len(all_posts_texts),
                "replies_texts": len(all_replies_texts),
            },
        },
    }


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "抓取 X / Twitter 数据并写入统一 SQLite 数据库。"
            "默认会重建数据库里的 twitter 平台数据；--preview 只抓取不写库。"
        )
    )
    parser.add_argument("--preview", action="store_true", help="只输出抓取结果 JSON，不写入 SQLite")
    parser.add_argument(
        "--max-trends",
        type=int,
        default=MAX_TRENDS,
        help=f"每轴 News 的 max_results（见文件顶部 MAX_TRENDS），默认 {MAX_TRENDS}",
    )
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=MAX_NEWS_AGE_HOURS,
        help=f"News 的 max_age_hours（1–720，见 MAX_NEWS_AGE_HOURS），默认 {MAX_NEWS_AGE_HOURS}",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=MAX_POSTS,
        help=f"每条新闻下主帖数量上限（见文件顶部 MAX_POSTS），默认 {MAX_POSTS}",
    )
    parser.add_argument(
        "--max-replies-per-post",
        type=int,
        default=MAX_REPLIES_PER_POST,
        help=f"每条主帖回复数上限（见 MAX_REPLIES_PER_POST），默认 {MAX_REPLIES_PER_POST}",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_SQLITE_PATH),
        help=f"SQLite 数据库路径，默认 {DEFAULT_SQLITE_PATH}",
    )
    return parser


def _run_cli(argv: List[str]) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    fetch_options = {
        "max_trends": args.max_trends,
        "max_posts": args.max_posts,
        "max_replies_per_post": args.max_replies_per_post,
        "max_age_hours": args.max_age_hours,
    }

    try:
        payload = run_fetch_pipeline(**fetch_options)
        if args.preview:
            print(json.dumps(payload, ensure_ascii=False), flush=True)
        else:
            result = import_payload_to_sqlite(
                payload=payload,
                fetch_options=fetch_options,
                db_path=Path(args.db_path).expanduser().resolve(),
            )
            print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except APIError as e:
        error_payload = {
            "error": e.detail,
            "status_code": e.status_code,
            "type": "APIError",
        } if args.preview else {
            "status": "error",
            "status_code": e.status_code,
            "type": "APIError",
            "message": e.detail,
        }
        print(json.dumps(error_payload, ensure_ascii=False), flush=True)
        return 1
    except Exception as e:
        error_payload = {
            "error": str(e),
            "type": type(e).__name__,
        } if args.preview else {
            "status": "error",
            "status_code": 500,
            "type": type(e).__name__,
            "message": str(e),
        }
        print(json.dumps(error_payload, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(_run_cli(sys.argv[1:]))
