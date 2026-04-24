"""
Instagram 数据集写库工具。
"""

import json
from pathlib import Path
from typing import Any

try:
    from instagram.instagram_fetcher import normalize_topic_key, now_iso
    from utils.db_utils import DatasetDB
except ModuleNotFoundError:
    from backend.scripts.datasets.instagram.instagram_fetcher import normalize_topic_key, now_iso
    from backend.scripts.datasets.utils.db_utils import DatasetDB

PLATFORM = "instagram"
ROW_TYPE = "instagram"


def _normalize_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _topic_key(topic_label: str) -> str:
    return normalize_topic_key(topic_label)


def _topic_label(topic_value: str) -> str:
    key = _topic_key(topic_value)
    return f"#{key}" if key else ""


class InstagramDatasetWriter:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @staticmethod
    def _count_platform_rows(conn, platform: str) -> dict[str, int]:
        stats: dict[str, int] = {}
        for table in ["users", "contents", "topics", "content_topics", "user_topics"]:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE platform = ?", (platform,))
            stats[table] = int(cursor.fetchone()[0] or 0)
        return stats

    @staticmethod
    def _clear_platform_rows(conn, platform: str) -> None:
        conn.execute("DELETE FROM user_topics WHERE platform = ?", (platform,))
        conn.execute("DELETE FROM content_topics WHERE platform = ?", (platform,))
        conn.execute("DELETE FROM contents WHERE platform = ?", (platform,))
        conn.execute("DELETE FROM topics WHERE platform = ?", (platform,))
        conn.execute("DELETE FROM users WHERE platform = ?", (platform,))

    def write_payload(
        self,
        payload: dict[str, Any],
        fetch_options: dict[str, Any],
        platform: str = PLATFORM,
    ) -> dict[str, Any]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        row_type = ROW_TYPE

        meta_obj = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        collected_at = _normalize_string(meta_obj.get("collected_at")) or now_iso()
        topic_rows_meta = meta_obj.get("topic_rows") if isinstance(meta_obj.get("topic_rows"), list) else []

        topics_payload = payload.get("topics") if isinstance(payload.get("topics"), list) else []
        users_payload = payload.get("users") if isinstance(payload.get("users"), list) else []
        posts_payload = payload.get("posts") if isinstance(payload.get("posts"), list) else []
        replies_payload = payload.get("replies") if isinstance(payload.get("replies"), list) else []

        topic_order = {
            _topic_key(str(row.get("topic_key") or row.get("topic_label") or "")): idx + 1
            for idx, row in enumerate(topic_rows_meta)
            if isinstance(row, dict) and _topic_key(str(row.get("topic_key") or row.get("topic_label") or ""))
        }
        topic_meta_by_key = {
            _topic_key(str(row.get("topic_key") or row.get("topic_label") or "")): row
            for row in topic_rows_meta
            if isinstance(row, dict) and _topic_key(str(row.get("topic_key") or row.get("topic_label") or ""))
        }

        topic_labels: dict[str, str] = {}
        topic_post_count: dict[str, int] = {}
        topic_reply_count: dict[str, int] = {}
        topic_users: dict[str, set[str]] = {}
        user_topic_stats: dict[tuple[str, str], dict[str, Any]] = {}

        def ensure_topic(topic_label: str) -> str | None:
            topic_key = _topic_key(topic_label)
            if not topic_key:
                return None
            if topic_key not in topic_labels:
                topic_labels[topic_key] = _topic_label(topic_label) or topic_label
                topic_post_count[topic_key] = 0
                topic_reply_count[topic_key] = 0
                topic_users[topic_key] = set()
            return topic_key

        for topic_label in topics_payload:
            if isinstance(topic_label, str):
                ensure_topic(topic_label)

        contents_rows: list[tuple[Any, ...]] = []
        content_topic_rows: list[tuple[Any, ...]] = []

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
            external_content_id = _normalize_string(post.get("external_content_id"))
            author_external_user_id = _normalize_string(post.get("author_external_user_id"))
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
                    _normalize_string(post.get("root_external_content_id")) or external_content_id,
                    _normalize_string(post.get("text")) or None,
                    _normalize_string(post.get("language")) or None,
                    _normalize_string(post.get("created_at")) or None,
                    post.get("like_count"),
                    post.get("reply_count"),
                    post.get("share_count"),
                    post.get("view_count"),
                    post.get("raw_json"),
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
            external_content_id = _normalize_string(reply.get("external_content_id"))
            author_external_user_id = _normalize_string(reply.get("author_external_user_id"))
            parent_external_content_id = _normalize_string(reply.get("parent_external_content_id"))
            root_external_content_id = _normalize_string(reply.get("root_external_content_id"))
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
                    root_external_content_id or parent_external_content_id or None,
                    _normalize_string(reply.get("text")) or None,
                    _normalize_string(reply.get("language")) or None,
                    _normalize_string(reply.get("created_at")) or None,
                    reply.get("like_count"),
                    reply.get("reply_count"),
                    reply.get("share_count"),
                    reply.get("view_count"),
                    reply.get("raw_json"),
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

        users_rows: list[tuple[Any, ...]] = []
        for user in users_payload:
            if not isinstance(user, dict):
                continue
            external_user_id = _normalize_string(user.get("external_user_id"))
            if not external_user_id:
                continue
            users_rows.append(
                (
                    platform,
                    row_type,
                    external_user_id,
                    _normalize_string(user.get("username")) or None,
                    _normalize_string(user.get("display_name")) or None,
                    _normalize_string(user.get("bio")) or None,
                    _normalize_string(user.get("location")) or None,
                    1 if bool(user.get("verified")) else 0,
                    user.get("follower_count"),
                    user.get("following_count"),
                    user.get("tweet_count"),
                    user.get("post_count"),
                    _normalize_string(user.get("user_type")) or None,
                    user.get("profile_json"),
                    user.get("raw_json"),
                )
            )

        user_topic_rows: list[tuple[Any, ...]] = []
        for (topic_key, external_user_id), stat in user_topic_stats.items():
            roles = stat["roles"]
            role = "both" if {"author", "replier"}.issubset(roles) else next(iter(roles), "author")
            user_topic_rows.append(
                (
                    platform,
                    row_type,
                    topic_key,
                    external_user_id,
                    role,
                    int(stat["content_count"]),
                    None,
                )
            )

        topics_rows: list[tuple[Any, ...]] = []
        for topic_key, topic_label in topic_labels.items():
            topic_meta = topic_meta_by_key.get(topic_key, {})
            topics_rows.append(
                (
                    platform,
                    row_type,
                    topic_key,
                    topic_label,
                    "hashtag",
                    topic_order.get(topic_key),
                    int(topic_post_count.get(topic_key, 0)),
                    int(topic_reply_count.get(topic_key, 0)),
                    len(topic_users.get(topic_key, set())),
                    collected_at,
                    collected_at,
                    None,
                    _json_text(
                        {
                            "fetch_options": fetch_options,
                            "topic_meta": topic_meta,
                            "actors": meta_obj.get("actors"),
                            "only_posts_newer_than": meta_obj.get("only_posts_newer_than"),
                        }
                    ),
                )
            )

        ins_topics = ins_users = ins_contents = ins_ct = ins_ut = 0

        with DatasetDB(self.db_path) as db:
            db.ensure_schema()
            conn = db.conn
            if conn.in_transaction:
                conn.commit()
            cleared_counts = self._count_platform_rows(conn, platform)

            try:
                conn.execute("BEGIN")
                self._clear_platform_rows(conn, platform)

                for row in topics_rows:
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

                for row in users_rows:
                    conn.execute(
                        """
                        INSERT INTO users (
                            platform, "type", external_user_id, username, display_name, bio, location,
                            verified, follower_count, following_count, tweet_count, post_count, user_type,
                            profile_json, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        row,
                    )
                    ins_users += 1

                for row in contents_rows:
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

                for row in content_topic_rows:
                    conn.execute(
                        """
                        INSERT INTO content_topics (
                            platform, "type", external_content_id, topic_key, relevance_score
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        row,
                    )
                    ins_ct += 1

                for row in user_topic_rows:
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

        return {
            "status": "success",
            "platform": platform,
            "db_path": str(self.db_path),
            "mode": "replace_platform_data",
            "cleared": cleared_counts,
            "imported": {
                "topics": ins_topics,
                "users": ins_users,
                "contents": ins_contents,
                "content_topics": ins_ct,
                "user_topics": ins_ut,
                "posts": len(posts_payload),
                "replies": len(replies_payload),
            },
            "attempted": {
                "topics": len(topics_rows),
                "users": len(users_rows),
                "contents": len(contents_rows),
                "content_topics": len(content_topic_rows),
                "user_topics": len(user_topic_rows),
            },
            "counts": meta_obj.get("counts", {}),
        }


def import_instagram_payload_to_sqlite(
    payload: dict[str, Any],
    fetch_options: dict[str, Any],
    db_path: Path,
    platform: str = PLATFORM,
) -> dict[str, Any]:
    writer = InstagramDatasetWriter(db_path)
    return writer.write_payload(payload=payload, fetch_options=fetch_options, platform=platform)
