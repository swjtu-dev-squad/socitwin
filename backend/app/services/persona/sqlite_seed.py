"""
SQLite 话题列表与多话题种子抽样（从旧 oasis-dashboard twitterDatasetSqliteServer.ts 移植）。
仅依赖 oasis_datasets.db 与 topics/contents/users 表结构。
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

PLATFORM = "twitter"


def _shuffle_in_place(arr: List[Any]) -> None:
    for i in range(len(arr) - 1, 0, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]


def _random_sample(arr: List[str], n: int) -> List[str]:
    if n <= 0 or not arr:
        return []
    copy = list(arr)
    _shuffle_in_place(copy)
    return copy[: min(n, len(copy))]


def load_user_types(conn: sqlite3.Connection, ids: List[str]) -> Dict[str, str]:
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    cur = conn.execute(
        f"""SELECT external_user_id AS id,
                   lower(trim(COALESCE(user_type, 'normal'))) AS ut
            FROM users
            WHERE platform = ? AND external_user_id IN ({ph})""",
        (PLATFORM, *ids),
    )
    out: Dict[str, str] = {}
    for row in cur.fetchall():
        ut = str(row["ut"] or "normal").strip()
        out[str(row["id"])] = "kol" if ut == "kol" else "normal"
    return out


def relax_kol_normal_in_set(chosen: List[str], types: Dict[str, str], pool: List[str], mandatory: Set[str]) -> List[str]:
    def count_kol(ids: Iterable[str]) -> int:
        return sum(1 for i in ids if types.get(i, "normal") == "kol")

    def count_normal(ids: Iterable[str]) -> int:
        return sum(1 for i in ids if types.get(i, "normal") != "kol")

    cur = list(chosen)
    guard = 0
    while guard < 5000:
        guard += 1
        k = count_kol(cur)
        n = count_normal(cur)
        if k == 0 or n >= 10 * k:
            break
        victim = next((x for x in cur if types.get(x, "normal") == "kol" and x not in mandatory), None)
        if victim is None:
            break
        cur_set = set(cur)
        replacement = next((x for x in pool if x not in cur_set and types.get(x, "normal") != "kol"), None)
        if replacement is None:
            break
        idx = cur.index(victim)
        cur[idx] = replacement
    return cur


def list_recent_topics_ordered(conn: sqlite3.Connection, recent_pool: int) -> List[Dict[str, Any]]:
    n = max(1, min(5000, int(recent_pool)))
    cur = conn.execute(
        """
        SELECT topic_key, topic_label, last_seen_at, post_count, reply_count
        FROM topics
        WHERE platform = ?
        ORDER BY COALESCE(last_seen_at, first_seen_at, '') DESC
        LIMIT ?
        """,
        (PLATFORM, n),
    )
    return [dict(row) for row in cur.fetchall()]


def compute_multi_topic_seed_sample(conn: sqlite3.Connection, topic_keys_in: List[str], user_limit: int) -> Dict[str, Any]:
    n = max(1, min(2000, int(user_limit)))
    topic_keys = list(dict.fromkeys(str(k).strip() for k in topic_keys_in if str(k).strip()))
    if not topic_keys:
        return {"topic_key": "", "user_limit_requested": n, "users_selected": 0, "kol_selected": 0, "normal_selected": 0, "counts": {"users": 0, "posts": 0, "replies": 0, "topics": 0}, "external_user_ids": []}

    tk_ph = ",".join("?" * len(topic_keys))
    post_rows = conn.execute(
        f"""
        SELECT DISTINCT c.external_content_id AS pid, c.author_external_user_id AS aid
        FROM contents c
        INNER JOIN content_topics ct
          ON ct.platform = c.platform AND ct.external_content_id = c.external_content_id
        INNER JOIN users u
          ON u.platform = c.platform AND u.external_user_id = c.author_external_user_id
        WHERE c.platform = ? AND c.content_type = 'post'
          AND ct.topic_key IN ({tk_ph})
          AND c.author_external_user_id IS NOT NULL
          AND TRIM(c.author_external_user_id) != ''
        """,
        (PLATFORM, *topic_keys),
    ).fetchall()

    post_ids = list({str(r["pid"]) for r in post_rows if r["pid"]})
    post_author_list: List[str] = []
    seen_a: Set[str] = set()
    for r in post_rows:
        aid = str(r["aid"] or "")
        if aid and aid not in seen_a:
            seen_a.add(aid)
            post_author_list.append(aid)
    post_count = len(post_ids)

    reply_count = 0
    reply_author_set: Set[str] = set()
    if post_ids:
        p_ph = ",".join("?" * len(post_ids))
        params = (PLATFORM, *post_ids, *post_ids)
        rc = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM contents c
            WHERE c.platform = ? AND c.content_type = 'reply'
              AND (
                (c.root_external_content_id IS NOT NULL AND c.root_external_content_id IN ({p_ph}))
                OR (c.parent_external_content_id IS NOT NULL AND c.parent_external_content_id IN ({p_ph}))
              )
            """,
            params,
        ).fetchone()
        reply_count = int(rc["c"] or 0) if rc else 0

        ra_rows = conn.execute(
            f"""
            SELECT DISTINCT c.author_external_user_id AS aid
            FROM contents c
            INNER JOIN users u
              ON u.platform = c.platform AND u.external_user_id = c.author_external_user_id
            WHERE c.platform = ? AND c.content_type = 'reply'
              AND (
                (c.root_external_content_id IS NOT NULL AND c.root_external_content_id IN ({p_ph}))
                OR (c.parent_external_content_id IS NOT NULL AND c.parent_external_content_id IN ({p_ph}))
              )
              AND c.author_external_user_id IS NOT NULL
              AND TRIM(c.author_external_user_id) != ''
            """,
            params,
        ).fetchall()
        for r in ra_rows:
            if r["aid"]:
                reply_author_set.add(str(r["aid"]))

    post_author_set = set(post_author_list)
    reply_only_authors = [a for a in reply_author_set if a not in post_author_set]

    candidate_pool = list(dict.fromkeys([*post_author_list, *reply_only_authors]))
    types = load_user_types(conn, candidate_pool)
    p_list = [x for x in post_author_list if x in types]
    r_list = [x for x in reply_only_authors if x in types]

    chosen: List[str] = []
    mandatory: Set[str] = set()
    if post_count == 0:
        chosen = []
    elif n < post_count:
        chosen = _random_sample(p_list, min(n, len(p_list)))
    else:
        if len(p_list) >= n:
            chosen = _random_sample(p_list, n)
            mandatory = set(chosen)
        else:
            chosen = [*p_list, *_random_sample(r_list, min(n - len(p_list), len(r_list)))]
            mandatory = set(p_list)

    pool_for_ratio = list(dict.fromkeys([*p_list, *r_list]))
    chosen = relax_kol_normal_in_set(chosen, types, pool_for_ratio, mandatory)
    kol_sel = sum(1 for i in chosen if types.get(i, "normal") == "kol")
    normal_sel = len(chosen) - kol_sel

    return {
        "topic_key": topic_keys[0] if len(topic_keys) == 1 else "\t".join(topic_keys),
        "user_limit_requested": n,
        "users_selected": len(chosen),
        "kol_selected": kol_sel,
        "normal_selected": normal_sel,
        "counts": {"users": len(chosen), "posts": post_count, "replies": reply_count, "topics": len(topic_keys)},
        "external_user_ids": chosen,
    }


def fetch_content_fallback_for_author(conn: sqlite3.Connection, author_id: str, max_posts: int, max_replies: int, max_total_chars: int) -> str:
    post_rows = conn.execute(
        """
        SELECT COALESCE(text, '') AS t
        FROM contents
        WHERE platform = ? AND author_external_user_id = ? AND content_type = 'post'
          AND text IS NOT NULL AND TRIM(text) != ''
        ORDER BY datetime(COALESCE(created_at, '')) DESC
        LIMIT ?
        """,
        (PLATFORM, author_id, max_posts),
    ).fetchall()
    reply_rows = conn.execute(
        """
        SELECT COALESCE(text, '') AS t
        FROM contents
        WHERE platform = ? AND author_external_user_id = ? AND content_type = 'reply'
          AND text IS NOT NULL AND TRIM(text) != ''
        ORDER BY datetime(COALESCE(created_at, '')) DESC
        LIMIT ?
        """,
        (PLATFORM, author_id, max_replies),
    ).fetchall()
    parts: List[str] = []
    post_texts = [str(r["t"] or "").strip() for r in post_rows if str(r["t"] or "").strip()]
    if post_texts:
        parts.append("【发帖摘录】")
        parts.extend(post_texts)
    reply_texts = [str(r["t"] or "").strip() for r in reply_rows if str(r["t"] or "").strip()]
    if reply_texts:
        parts.append("【评论摘录】")
        parts.extend(reply_texts)
    return "\n".join(parts).strip()[:max_total_chars]


def get_topic_labels_for_keys(conn: sqlite3.Connection, topic_keys: List[str]) -> List[Dict[str, str]]:
    keys = list(dict.fromkeys(str(k).strip() for k in topic_keys if str(k).strip()))
    if not keys:
        return []
    ph = ",".join("?" * len(keys))
    rows = conn.execute(f"SELECT topic_key, topic_label FROM topics WHERE platform = ? AND topic_key IN ({ph})", (PLATFORM, *keys)).fetchall()
    by_key = {str(r["topic_key"]): str(r["topic_label"] or r["topic_key"]) for r in rows}
    return [{"topic_key": k, "topic_label": by_key.get(k, k)} for k in keys]


def build_seed_users_for_llm_from_sqlite(conn: sqlite3.Connection, external_user_ids: List[str]) -> List[Dict[str, Any]]:
    ids = list(dict.fromkeys(str(x).strip() for x in external_user_ids if str(x).strip()))
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT external_user_id, username, display_name, bio,
               lower(trim(COALESCE(user_type, 'normal'))) AS ut
        FROM users
        WHERE platform = ? AND external_user_id IN ({ph})
        """,
        (PLATFORM, *ids),
    ).fetchall()
    seeds: List[Dict[str, Any]] = []
    for row in rows:
        bio = str(row["bio"] or "").strip()
        uname = str(row["username"] or "").strip() or f"user_{row['external_user_id']}"
        display = str(row["display_name"] or "").strip() or uname
        ut = "kol" if str(row["ut"] or "").strip() == "kol" else "normal"
        description = bio or fetch_content_fallback_for_author(conn, str(row["external_user_id"]), 8, 8, 2400)
        seeds.append(
            {
                "twitter_user_id": row["external_user_id"],
                "username": uname,
                "user_name": uname,
                "name": display,
                "bio": bio or "",
                "description": (description or display)[:4000],
                "user_type": ut,
            }
        )
    return seeds


def open_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

