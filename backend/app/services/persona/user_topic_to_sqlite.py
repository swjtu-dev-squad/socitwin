from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _int0(v: Any) -> int:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0
        return int(v)
    except (TypeError, ValueError):
        return 0


def _build_profile_json(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    prof = user_doc.get("profile") if isinstance(user_doc.get("profile"), dict) else {}
    oi = prof.get("other_info") if isinstance(prof.get("other_info"), dict) else {}

    topics_raw = oi.get("topics")
    topics_list = (
        [str(x).strip() for x in topics_raw if x is not None and str(x).strip()]
        if isinstance(topics_raw, list)
        else []
    )
    if not topics_list:
        st = user_doc.get("source_topics")
        if isinstance(st, list):
            topics_list = [str(x).strip() for x in st if x is not None and str(x).strip()]

    reddit_profile = oi.get("reddit_profile")
    if not isinstance(reddit_profile, dict):
        reddit_profile = {}

    return {"other_info": {"topics": topics_list, "reddit_profile": reddit_profile}}


def persist_topics_users_to_sqlite(
    *,
    db_path: str | Path,
    platform: str,
    dataset_id: str,
    topics: List[Dict[str, Any]],
    users: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    将 LLM 生成的 topics/users/user_topics 写入 oasis_datasets.db。

    约定：
    - 写入平台：platform 参数应由调用方传入，例如 f"{selected_platform}_llm"。
    - type 列固定写 "llm"（与真实采集数据区分）。
    - profile_json/raw_json 按调用方给定的用户文档结构写入（raw_json 直接存整条 user 文档）。
    """
    plat = _norm(platform).lower()
    if not plat:
        raise ValueError("platform 不能为空")
    now = _utc_iso_now()

    topics_list = [x for x in topics if isinstance(x, dict)]
    users_list = [x for x in users if isinstance(x, dict)]

    def topic_key_for(dataset_id_val: str, idx: int) -> str:
        return f"llm_t_{dataset_id_val[:20]}_{idx}"[:64]

    # title -> topic_key
    title_to_topic_key: Dict[str, str] = {}
    for i, t in enumerate(topics_list):
        title = _norm(t.get("title") or t.get("name"))
        if title:
            title_to_topic_key[title] = topic_key_for(dataset_id, i)

    inserted = {"topics": 0, "users": 0, "user_topics": 0}
    skipped = {"topics": 0, "users": 0, "user_topics": 0}

    p = Path(db_path).expanduser().resolve()
    if p.exists() and p.is_dir():
        raise ValueError(f"db_path 指向目录: {p}")

    conn = sqlite3.connect(str(p))
    try:
        conn.execute("BEGIN")

        # topics(platform, topic_key) PK
        for i, t in enumerate(topics_list):
            title = _norm(t.get("title") or t.get("name"))
            if not title:
                continue
            tk = title_to_topic_key.get(title) or topic_key_for(dataset_id, i)
            if conn.execute(
                "SELECT 1 FROM topics WHERE platform = ? AND topic_key = ?",
                (plat, tk),
            ).fetchone():
                skipped["topics"] += 1
                continue
            conn.execute(
                """
                INSERT INTO topics (
                    platform, topic_key, topic_label, topic_type, trend_rank,
                    post_count, reply_count, user_count, first_seen_at, last_seen_at,
                    news_external_id, raw_json, type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plat,
                    tk,
                    title[:300],
                    "trend",
                    None,
                    0,
                    0,
                    0,
                    now,
                    now,
                    None,
                    None,
                    "llm",
                ),
            )
            inserted["topics"] += 1

        # users(platform, external_user_id) PK
        for u in users_list:
            ext_id = _norm(u.get("twitter_user_id") or u.get("external_user_id"))
            if not ext_id:
                continue
            if conn.execute(
                "SELECT 1 FROM users WHERE platform = ? AND external_user_id = ?",
                (plat, ext_id),
            ).fetchone():
                skipped["users"] += 1
                continue
            profile_json = _build_profile_json(u)
            conn.execute(
                """
                INSERT INTO users (
                    platform, external_user_id, username, display_name, bio, location,
                    verified, follower_count, following_count, tweet_count, user_type,
                    profile_json, raw_json, type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plat,
                    ext_id,
                    (_norm(u.get("user_name") or u.get("username")) or None),
                    (_norm(u.get("name")) or None),
                    (_norm(u.get("description")) or None),
                    (_norm(u.get("location")) or None),
                    1 if bool(u.get("verified")) else 0,
                    _int0(u.get("followers_count")),
                    _int0(u.get("following_count")),
                    _int0(u.get("tweet_count")),
                    (_norm(u.get("user_type")) or "normal"),
                    json.dumps(profile_json, ensure_ascii=False),
                    json.dumps(u, ensure_ascii=False),
                    "llm",
                ),
            )
            inserted["users"] += 1

        # user_topics(platform, topic_key, external_user_id) PK
        for u in users_list:
            ext_id = _norm(u.get("twitter_user_id") or u.get("external_user_id"))
            if not ext_id:
                continue
            prof_json = _build_profile_json(u)
            oi = prof_json.get("other_info") if isinstance(prof_json.get("other_info"), dict) else {}
            topics_arr = oi.get("topics") if isinstance(oi.get("topics"), list) else []
            for raw_title in topics_arr:
                title = _norm(raw_title)
                if not title:
                    continue
                tk = title_to_topic_key.get(title)
                if not tk:
                    continue
                if conn.execute(
                    """
                    SELECT 1 FROM user_topics
                    WHERE platform = ? AND topic_key = ? AND external_user_id = ?
                    """,
                    (plat, tk, ext_id),
                ).fetchone():
                    skipped["user_topics"] += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO user_topics (
                        platform, topic_key, external_user_id, role, content_count, news_external_id, type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (plat, tk, ext_id, "llm_interest", 1, None, "llm"),
                )
                inserted["user_topics"] += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "ok": True,
        "platform": plat,
        "dataset_id": dataset_id,
        "inserted": inserted,
        "skipped": skipped,
        "attempted": {"topics": len(topics_list), "users": len(users_list)},
    }

