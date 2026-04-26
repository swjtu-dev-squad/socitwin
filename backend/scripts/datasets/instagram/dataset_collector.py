"""
Instagram 议题数据采集流程。
"""

import json
import time
from collections import defaultdict
from typing import Any

try:
    from instagram.instagram_fetcher import (
        InstagramFetcher,
        clean_str,
        get_apify_key,
        log,
        media_code_from_record,
        media_code_from_url,
        normalize_topic_key,
        now_iso,
    )
except ModuleNotFoundError:
    from backend.scripts.datasets.instagram.instagram_fetcher import (
        InstagramFetcher,
        clean_str,
        get_apify_key,
        log,
        media_code_from_record,
        media_code_from_url,
        normalize_topic_key,
        now_iso,
    )

PLATFORM = "instagram"
DEFAULT_TOPICS = [
    "climatechange",
    "artificialintelligence",
    "aiethics",
    "remotework",
    "cryptocurrency",
    "housingcrisis",
    "mentalhealth",
    "publichealth",
    "renewableenergy",
    "spaceexploration",
]
DEFAULT_MAX_TOPICS = 6
DEFAULT_MAX_POSTS = 10
DEFAULT_MAX_REPLIES_PER_POST = 0
DEFAULT_COMMENT_BATCH_SIZE = 8
DEFAULT_PROFILE_BATCH_SIZE = 20
DEFAULT_MAX_PROFILE_DETAILS_USERS = 60
DEFAULT_ONLY_POSTS_NEWER_THAN = "30 days"
DEFAULT_REQUEST_SLEEP_SECONDS = 0.5
KOL_FOLLOWER_THRESHOLD = 20000


def _normalize_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _merge_topics(existing_topics: list[str], new_topics: list[str]) -> list[str]:
    merged = list(existing_topics)
    for topic in new_topics:
        if topic and topic not in merged:
            merged.append(topic)
    return merged


def _topic_key(topic_label: str) -> str:
    return normalize_topic_key(topic_label)


def _user_lookup_key(value: Any) -> str:
    return _normalize_string(value).lstrip("@").lower()


class InstagramDatasetCollector:
    def __init__(
        self,
        fetcher: InstagramFetcher,
        max_posts: int = DEFAULT_MAX_POSTS,
        max_replies_per_post: int = DEFAULT_MAX_REPLIES_PER_POST,
        comment_batch_size: int = DEFAULT_COMMENT_BATCH_SIZE,
        profile_batch_size: int = DEFAULT_PROFILE_BATCH_SIZE,
        max_profile_details_users: int = DEFAULT_MAX_PROFILE_DETAILS_USERS,
        request_sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
        only_posts_newer_than: str | None = DEFAULT_ONLY_POSTS_NEWER_THAN,
    ) -> None:
        self.fetcher = fetcher
        self.max_posts = max_posts
        self.max_replies_per_post = max_replies_per_post
        self.comment_batch_size = max(1, comment_batch_size)
        self.profile_batch_size = max(1, profile_batch_size)
        self.max_profile_details_users = max(0, max_profile_details_users)
        self.request_sleep_seconds = request_sleep_seconds
        self.only_posts_newer_than = (
            only_posts_newer_than.strip()
            if isinstance(only_posts_newer_than, str) and only_posts_newer_than.strip()
            else None
        )

        self.users_map: dict[str, dict[str, Any]] = {}
        self.posts_map: dict[str, dict[str, Any]] = {}
        self.replies_map: dict[str, dict[str, Any]] = {}
        self.comment_tasks_by_post: dict[str, dict[str, Any]] = {}

    def collect(self, topics: list[str] | None = None, max_topics: int = DEFAULT_MAX_TOPICS) -> dict[str, Any]:
        topic_specs = self._resolve_topics(topics, max_topics)
        if not topic_specs:
            raise RuntimeError("没有可抓取的 Instagram topics")

        topic_rows_meta: list[dict[str, Any]] = []

        for idx, topic_spec in enumerate(topic_specs, start=1):
            topic_label = topic_spec["topic_label"]
            search_term = topic_spec["search_term"]
            log(f"[topic {idx}/{len(topic_specs)}] {topic_label}")
            started_at = time.monotonic()

            raw_posts = self.fetcher.fetch_topic_posts(
                search_term,
                self.max_posts,
                only_newer_than=self.only_posts_newer_than,
            )
            topic_rows_meta.append(
                {
                    "topic_key": topic_spec["topic_key"],
                    "topic_label": topic_label,
                    "search_term": search_term,
                    "results_count": len(raw_posts),
                }
            )

            for raw_post in raw_posts:
                self._collect_post(raw_post, topic_label)

            elapsed = time.monotonic() - started_at
            log(f"  完成 {topic_label}: {len(raw_posts)} 条帖子，耗时 {elapsed:.1f}s")
            if idx < len(topic_specs):
                time.sleep(self.request_sleep_seconds)

        self._collect_comments()
        self._enrich_user_profiles()

        users_out = list(self.users_map.values())
        posts_out = list(self.posts_map.values())
        replies_out = list(self.replies_map.values())

        topic_post_count = defaultdict(int)
        topic_reply_count = defaultdict(int)
        for post in posts_out:
            for topic in post.get("source_topics", []):
                topic_post_count[topic] += 1
        for reply in replies_out:
            for topic in reply.get("source_topics", []):
                topic_reply_count[topic] += 1

        for row in topic_rows_meta:
            topic_label = row["topic_label"]
            row["post_count"] = topic_post_count.get(topic_label, 0)
            row["reply_count"] = topic_reply_count.get(topic_label, 0)

        posts_texts = [post.get("text", "") for post in posts_out if post.get("text")]
        replies_texts = [reply.get("text", "") for reply in replies_out if reply.get("text")]

        payload = {
            "topics": [topic_spec["topic_label"] for topic_spec in topic_specs],
            "topics_document": {
                "instagram_hashtags": [topic_spec["topic_label"] for topic_spec in topic_specs],
            },
            "users": users_out,
            "posts": posts_out,
            "replies": replies_out,
            "posts_texts": posts_texts,
            "replies_texts": replies_texts,
            "meta": {
                "actors": {
                    "posts": "apify/instagram-hashtag-scraper",
                    "profiles": "apify/instagram-scraper",
                    "comments": "apify/instagram-scraper",
                },
                "topic_rows": topic_rows_meta,
                "collected_at": now_iso(),
                "only_posts_newer_than": self.only_posts_newer_than,
                "counts": {
                    "topics": len(topic_specs),
                    "users": len(users_out),
                    "posts": len(posts_out),
                    "replies": len(replies_out),
                    "posts_texts": len(posts_texts),
                    "replies_texts": len(replies_texts),
                },
            },
        }
        log(
            "完成: "
            f"{payload['meta']['counts']['topics']} 个话题, "
            f"{payload['meta']['counts']['users']} 个用户, "
            f"{payload['meta']['counts']['posts']} 条帖子, "
            f"{payload['meta']['counts']['replies']} 条回复",
        )
        return payload

    def _resolve_topics(self, raw_topics: list[str] | None, max_topics: int) -> list[dict[str, str]]:
        seed_topics = raw_topics if raw_topics else DEFAULT_TOPICS[:max_topics]
        resolved: list[dict[str, str]] = []
        seen: set[str] = set()

        for raw_topic in seed_topics:
            key = _topic_key(raw_topic)
            if not key or key in seen:
                continue
            seen.add(key)
            resolved.append(
                {
                    "topic_key": key,
                    "topic_label": f"#{key}",
                    "search_term": f"#{key}",
                }
            )

        return resolved

    def _refresh_user_type(self, user_doc: dict[str, Any]) -> None:
        follower_count = _safe_int(user_doc.get("follower_count"))
        user_doc["user_type"] = (
            "kol"
            if follower_count is not None and follower_count > KOL_FOLLOWER_THRESHOLD
            else "normal"
        )

    def _merge_user_doc(self, user_doc: dict[str, Any] | None, source_topics: list[str]) -> str:
        if not user_doc:
            return ""

        external_user_id = _normalize_string(
            user_doc.get("external_user_id") or user_doc.get("username"),
        )
        if not external_user_id:
            return ""

        existing = self.users_map.get(external_user_id)
        if existing is None:
            merged = dict(user_doc)
            merged["source_topics"] = list(dict.fromkeys(source_topics))
            self._refresh_user_type(merged)
            self.users_map[external_user_id] = merged
            return external_user_id

        for field in ("platform", "type", "username", "display_name", "bio", "location"):
            if not existing.get(field) and user_doc.get(field):
                existing[field] = user_doc[field]
        if user_doc.get("raw_json") and (not existing.get("raw_json") or self._is_profile_detail(user_doc)):
            existing["raw_json"] = user_doc["raw_json"]

        existing["verified"] = 1 if int(existing.get("verified") or 0) or int(user_doc.get("verified") or 0) else 0

        for metric in ("follower_count", "following_count", "tweet_count", "post_count"):
            old_value = _safe_int(existing.get(metric))
            new_value = _safe_int(user_doc.get(metric))
            if old_value is None:
                existing[metric] = new_value
            elif new_value is not None:
                existing[metric] = max(old_value, new_value)

        profile = _parse_json_object(existing.get("profile_json"))
        profile.update(_parse_json_object(user_doc.get("profile_json")))
        existing["profile_json"] = _json_text(profile)
        existing["source_topics"] = _merge_topics(existing.get("source_topics", []), source_topics)
        self._refresh_user_type(existing)
        return external_user_id

    def _is_profile_detail(self, user_doc: dict[str, Any]) -> bool:
        return any(
            user_doc.get(field) not in (None, "")
            for field in ("bio", "location", "follower_count", "following_count", "tweet_count", "post_count")
        )

    def _merge_content_doc(self, contents_map: dict[str, dict[str, Any]], content_doc: dict[str, Any] | None, source_topics: list[str]) -> str:
        if not content_doc:
            return ""

        external_content_id = _normalize_string(content_doc.get("external_content_id"))
        if not external_content_id:
            return ""

        existing = contents_map.get(external_content_id)
        if existing is None:
            merged = dict(content_doc)
            merged["source_topics"] = list(dict.fromkeys(source_topics))
            contents_map[external_content_id] = merged
            return external_content_id

        for field in (
            "platform",
            "type",
            "content_type",
            "author_external_user_id",
            "parent_external_content_id",
            "root_external_content_id",
            "text",
            "language",
            "created_at",
            "raw_json",
        ):
            if not existing.get(field) and content_doc.get(field):
                existing[field] = content_doc[field]

        for metric in ("like_count", "reply_count", "share_count", "view_count"):
            old_value = _safe_int(existing.get(metric))
            new_value = _safe_int(content_doc.get(metric))
            if old_value is None:
                existing[metric] = new_value
            elif new_value is not None:
                existing[metric] = max(old_value, new_value)

        existing["source_topics"] = _merge_topics(existing.get("source_topics", []), source_topics)
        return external_content_id

    def _enrich_user_profiles(self) -> None:
        if self.max_profile_details_users <= 0:
            return

        candidates: list[tuple[str, str]] = []
        seen: set[str] = set()

        for external_user_id, user_doc in self.users_map.items():
            username = _normalize_string(user_doc.get("username") or external_user_id).lstrip("@")
            lookup_key = _user_lookup_key(username)
            if (
                not lookup_key
                or lookup_key in seen
                or lookup_key.startswith("instagram_user_")
                or "/" in lookup_key
                or " " in lookup_key
            ):
                continue
            seen.add(lookup_key)
            candidates.append((external_user_id, username))
            if len(candidates) >= self.max_profile_details_users:
                break

        if not candidates:
            return

        log(f"补齐用户主页详情: {len(candidates)} 个用户")
        external_id_by_lookup = {
            _user_lookup_key(username): external_user_id
            for external_user_id, username in candidates
        }

        batches = self._chunked([username for _, username in candidates], self.profile_batch_size)
        for batch_idx, username_batch in enumerate(batches, start=1):
            log(f"[profiles {batch_idx}/{len(batches)}] {len(username_batch)} 个用户")
            profiles = self.fetcher.fetch_user_profiles(username_batch)
            for profile_username, raw_profile in profiles.items():
                lookup_key = _user_lookup_key(profile_username)
                external_user_id = external_id_by_lookup.get(lookup_key, profile_username)
                existing_user = self.users_map.get(external_user_id, {})
                profile_doc = self.fetcher.extract_user(raw_profile)
                if not profile_doc:
                    continue
                profile_doc["external_user_id"] = external_user_id
                self._merge_user_doc(profile_doc, existing_user.get("source_topics", []))
            time.sleep(self.request_sleep_seconds)

    def _collect_post(self, raw_post: dict[str, Any], topic_label: str) -> None:
        author_doc = self.fetcher.extract_user(raw_post)
        author_id = self._merge_user_doc(author_doc, [topic_label])

        post_doc = self.fetcher.extract_post(raw_post, author_id)
        post_doc["content_type"] = "post"
        self._merge_content_doc(self.posts_map, post_doc, [topic_label])

        embedded_comments = self._iter_embedded_comments(raw_post)
        if embedded_comments:
            self.comment_tasks_by_post.pop(post_doc["external_content_id"], None)
            for raw_comment in embedded_comments:
                self._collect_reply_records(raw_comment, post_doc, [topic_label])
            return

        if self.max_replies_per_post <= 0:
            return

        task = self._build_comment_task(raw_post, post_doc, [topic_label])
        if not task:
            return

        existing_task = self.comment_tasks_by_post.get(task["external_content_id"])
        if existing_task is None:
            self.comment_tasks_by_post[task["external_content_id"]] = task
            return

        existing_task["source_topics"] = _merge_topics(
            existing_task.get("source_topics", []),
            task["source_topics"],
        )

    def _collect_comments(self) -> None:
        comment_tasks = list(self.comment_tasks_by_post.values())
        if not comment_tasks or self.max_replies_per_post <= 0:
            return

        batches = self._chunked(comment_tasks, self.comment_batch_size)
        for batch_idx, task_batch in enumerate(batches, start=1):
            log(f"[comments {batch_idx}/{len(batches)}] {len(task_batch)} 条帖子")
            comments_by_code = self.fetcher.fetch_posts_comments(
                [task["url"] for task in task_batch],
                self.max_replies_per_post,
            )

            missing_tasks = [
                task for task in task_batch if task["media_code"] not in comments_by_code
            ]
            if missing_tasks and len(task_batch) > 1:
                log(f"  批量评论未命中 {len(missing_tasks)} 条帖子，跳过这些帖子")

            for task in task_batch:
                comments = comments_by_code.get(task["media_code"], [])
                for raw_comment in comments[:self.max_replies_per_post]:
                    self._collect_reply_records(raw_comment, task["post_doc"], task["source_topics"])
            time.sleep(self.request_sleep_seconds)

    def _collect_reply_records(self, raw_comment: dict[str, Any], post_doc: dict[str, Any], source_topics: list[str]) -> None:
        comment_user = self.fetcher.extract_comment_user(raw_comment)
        self._merge_user_doc(comment_user, source_topics)

        reply_doc = self.fetcher.extract_comment(
            raw_comment,
            parent_content_id=post_doc["external_content_id"],
            root_content_id=post_doc["external_content_id"],
        )
        reply_doc["content_type"] = "reply"
        self._merge_content_doc(self.replies_map, reply_doc, source_topics)

        nested_replies = raw_comment.get("replies")
        if not isinstance(nested_replies, list):
            return

        for nested in nested_replies:
            if not isinstance(nested, dict):
                continue
            nested_user = self.fetcher.extract_comment_user(nested)
            self._merge_user_doc(nested_user, source_topics)

            nested_reply_doc = self.fetcher.extract_comment(
                nested,
                parent_content_id=reply_doc["external_content_id"],
                root_content_id=post_doc["external_content_id"],
            )
            nested_reply_doc["content_type"] = "reply"
            self._merge_content_doc(self.replies_map, nested_reply_doc, source_topics)

    def _iter_embedded_comments(self, raw_post: dict[str, Any]) -> list[dict[str, Any]]:
        if self.max_replies_per_post <= 0:
            return []

        embedded: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for key in ("topComments", "latestComments", "comments"):
            items = raw_post.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                comment_id = clean_str(item.get("id") or item.get("commentId"))
                if comment_id and comment_id in seen_ids:
                    continue
                if comment_id:
                    seen_ids.add(comment_id)
                embedded.append(item)
                if len(embedded) >= self.max_replies_per_post:
                    return embedded

        return embedded

    def _build_comment_task(self, raw_post: dict[str, Any], post_doc: dict[str, Any], source_topics: list[str]) -> dict[str, Any] | None:
        post_url = self.fetcher.post_url(raw_post)
        media_code = media_code_from_record(raw_post) or media_code_from_url(post_url)
        if not post_url and media_code:
            post_url = f"https://www.instagram.com/p/{media_code}/"
        if not post_url or not media_code:
            return None

        return {
            "external_content_id": post_doc["external_content_id"],
            "url": post_url,
            "media_code": media_code,
            "post_doc": post_doc,
            "source_topics": list(dict.fromkeys(source_topics)),
        }

    @staticmethod
    def _chunked(items: list[Any], size: int) -> list[list[Any]]:
        return [items[idx: idx + size] for idx in range(0, len(items), size)]


def run_fetch_pipeline(
    topics: list[str] | None = None,
    max_topics: int = DEFAULT_MAX_TOPICS,
    max_posts: int = DEFAULT_MAX_POSTS,
    max_replies_per_post: int = DEFAULT_MAX_REPLIES_PER_POST,
    only_posts_newer_than: str | None = DEFAULT_ONLY_POSTS_NEWER_THAN,
    request_sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
    comment_batch_size: int = DEFAULT_COMMENT_BATCH_SIZE,
) -> dict[str, Any]:
    token = get_apify_key()
    if not token:
        raise RuntimeError("缺少 APIFY_KEY：请在 backend/.env 中设置 APIFY_KEY")

    fetcher = InstagramFetcher(token, request_sleep_seconds)
    collector = InstagramDatasetCollector(
        fetcher=fetcher,
        max_posts=max_posts,
        max_replies_per_post=max_replies_per_post,
        comment_batch_size=comment_batch_size,
        profile_batch_size=DEFAULT_PROFILE_BATCH_SIZE,
        max_profile_details_users=DEFAULT_MAX_PROFILE_DETAILS_USERS,
        request_sleep_seconds=request_sleep_seconds,
        only_posts_newer_than=only_posts_newer_than,
    )
    return collector.collect(topics=topics, max_topics=max_topics)
