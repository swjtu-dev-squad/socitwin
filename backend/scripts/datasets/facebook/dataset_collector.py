"""
Facebook 议题数据采集流程。
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from facebook.facebook_fetcher import (
        FacebookFetcher,
        clean_str,
        facebook_url_id,
        log,
        normalize_facebook_url,
        normalize_topic_key,
        now_iso,
        profile_id_from_url,
        raw_profile_url,
    )
except ModuleNotFoundError:
    from backend.scripts.datasets.facebook.facebook_fetcher import (
        FacebookFetcher,
        clean_str,
        facebook_url_id,
        log,
        normalize_facebook_url,
        normalize_topic_key,
        now_iso,
        profile_id_from_url,
        raw_profile_url,
    )

try:
    from utils.apify_utils import get_apify_key
except ModuleNotFoundError:
    from datasets.utils.apify_utils import get_apify_key

DEFAULT_TOPICS = [
    "climate change",
    "artificial intelligence",
    "AI ethics",
    "remote work",
    "cryptocurrency",
    "housing crisis",
    "mental health",
    "public health",
    "renewable energy",
    "space exploration",
    "education policy",
    "urban planning",
]
DEFAULT_TOPIC_PAGE_URLS = {
    "climate_change": [
        "https://www.facebook.com/UNclimatechange",
        "https://www.facebook.com/nasaearth",
    ],
    "artificial_intelligence": [
        "https://www.facebook.com/openai",
        "https://www.facebook.com/MITCSAIL",
    ],
    "ai_ethics": [
        "https://www.facebook.com/PartnershiponAI",
        "https://www.facebook.com/AIforGood",
    ],
    "remote_work": [
        "https://www.facebook.com/bufferapp",
        "https://www.facebook.com/remote.co",
    ],
    "cryptocurrency": [
        "https://www.facebook.com/Coinbase",
        "https://www.facebook.com/binance",
    ],
    "housing_crisis": [
        "https://www.facebook.com/NLIHC",
        "https://www.facebook.com/Habitat",
    ],
    "mental_health": [
        "https://www.facebook.com/NAMI",
        "https://www.facebook.com/mentalhealthamerica",
    ],
    "public_health": [
        "https://www.facebook.com/CDC",
        "https://www.facebook.com/WHO",
    ],
    "renewable_energy": [
        "https://www.facebook.com/irena.org",
        "https://www.facebook.com/RenewableEnergyWorld",
    ],
    "space_exploration": [
        "https://www.facebook.com/NASA",
        "https://www.facebook.com/EuropeanSpaceAgency",
    ],
    "education_policy": [
        "https://www.facebook.com/usedgov",
        "https://www.facebook.com/UNESCO",
    ],
    "urban_planning": [
        "https://www.facebook.com/planetizen",
        "https://www.facebook.com/SmartGrowthAmerica",
    ],
}
DEFAULT_MAX_TOPICS = 8
DEFAULT_MAX_POSTS = 12
DEFAULT_MAX_REPLIES_PER_POST = 0
DEFAULT_COMMENT_BATCH_SIZE = 5
DEFAULT_PROFILE_BATCH_SIZE = 4
DEFAULT_MAX_PROFILE_DETAILS_USERS = 80
DEFAULT_SEARCH_TYPE = "latest"
DEFAULT_DAYS_BACK = 0
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


class FacebookDatasetCollector:
    def __init__(
        self,
        fetcher: FacebookFetcher,
        max_posts: int = DEFAULT_MAX_POSTS,
        max_replies_per_post: int = DEFAULT_MAX_REPLIES_PER_POST,
        comment_batch_size: int = DEFAULT_COMMENT_BATCH_SIZE,
        profile_batch_size: int = DEFAULT_PROFILE_BATCH_SIZE,
        max_profile_details_users: int = DEFAULT_MAX_PROFILE_DETAILS_USERS,
        search_type: str = DEFAULT_SEARCH_TYPE,
        start_date: str | None = None,
        end_date: str | None = None,
        request_sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
    ) -> None:
        self.fetcher = fetcher
        self.max_posts = max_posts
        self.max_replies_per_post = max_replies_per_post
        self.comment_batch_size = max(1, comment_batch_size)
        self.profile_batch_size = max(1, profile_batch_size)
        self.max_profile_details_users = max(0, max_profile_details_users)
        self.search_type = search_type
        self.start_date = start_date.strip() if isinstance(start_date, str) and start_date.strip() else None
        self.end_date = end_date.strip() if isinstance(end_date, str) and end_date.strip() else None
        self.request_sleep_seconds = request_sleep_seconds

        self.users_map: dict[str, dict[str, Any]] = {}
        self.profile_urls_by_user: dict[str, str] = {}
        self.posts_map: dict[str, dict[str, Any]] = {}
        self.replies_map: dict[str, dict[str, Any]] = {}
        self.comment_tasks_by_post: dict[str, dict[str, Any]] = {}

    def collect(self, topics: list[str] | None = None, max_topics: int = DEFAULT_MAX_TOPICS) -> dict[str, Any]:
        topic_specs = self._resolve_topics(topics, max_topics)
        if not topic_specs:
            raise RuntimeError("没有可抓取的 Facebook topics")

        topic_rows_meta: list[dict[str, Any]] = []
        for idx, topic_spec in enumerate(topic_specs, start=1):
            topic_label = topic_spec["topic_label"]
            search_term = topic_spec["search_term"]
            log(f"[topic {idx}/{len(topic_specs)}] {topic_label}")
            started_at = time.monotonic()

            raw_posts = self.fetcher.fetch_topic_posts(
                search_term,
                self.max_posts,
                search_type=self.search_type,
                start_date=self.start_date,
                end_date=self.end_date,
            )
            page_posts = self._collect_page_seed_posts(topic_spec, len(raw_posts))
            raw_posts = self._dedupe_posts(raw_posts + page_posts)[:self.max_posts]
            topic_rows_meta.append(
                {
                    "topic_key": topic_spec["topic_key"],
                    "topic_label": topic_label,
                    "search_term": search_term,
                    "results_count": len(raw_posts),
                    "page_urls": topic_spec.get("page_urls", []),
                }
            )

            for raw_post in raw_posts:
                self._collect_post(raw_post, topic_label)

            log(f"  完成 {topic_label}: {len(raw_posts)} 条帖子，耗时 {time.monotonic() - started_at:.1f}s")
            if idx < len(topic_specs):
                time.sleep(self.request_sleep_seconds)

        self._collect_comments()
        self._enrich_user_profiles()
        self._ensure_profile_quality()
        return self._build_payload(topic_specs, topic_rows_meta)

    def _resolve_topics(self, raw_topics: list[str] | None, max_topics: int) -> list[dict[str, str]]:
        seed_topics = raw_topics if raw_topics else DEFAULT_TOPICS[:max_topics]
        resolved: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw_topic in seed_topics:
            key = _topic_key(raw_topic)
            if not key or key in seen:
                continue
            seen.add(key)
            label = clean_str(raw_topic)
            resolved.append(
                {
                    "topic_key": key,
                    "topic_label": label,
                    "search_term": label,
                    "page_urls": DEFAULT_TOPIC_PAGE_URLS.get(key, []),
                }
            )
        return resolved

    def _collect_page_seed_posts(self, topic_spec: dict[str, Any], existing_count: int) -> list[dict[str, Any]]:
        page_urls = topic_spec.get("page_urls") if isinstance(topic_spec.get("page_urls"), list) else []
        if not page_urls or existing_count >= self.max_posts:
            return []
        remaining = self.max_posts - existing_count
        limit_per_page = max(1, (remaining + len(page_urls) - 1) // len(page_urls))
        return self.fetcher.fetch_page_posts(page_urls, limit_per_page)

    @staticmethod
    def _dedupe_posts(raw_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_post in raw_posts:
            post_key = _normalize_string(
                raw_post.get("postId")
                or raw_post.get("post_id")
                or raw_post.get("id")
                or facebook_url_id(raw_post.get("url"))
                or facebook_url_id(raw_post.get("postUrl"))
            )
            if not post_key:
                post_key = _normalize_string(raw_post.get("url") or raw_post.get("postUrl") or raw_post.get("postText"))
            if post_key and post_key in seen:
                continue
            if post_key:
                seen.add(post_key)
            deduped.append(raw_post)
        return deduped

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
        external_user_id = _normalize_string(user_doc.get("external_user_id") or user_doc.get("username"))
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

    def _merge_content_doc(
        self,
        contents_map: dict[str, dict[str, Any]],
        content_doc: dict[str, Any] | None,
        source_topics: list[str],
    ) -> str:
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
            "url",
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

    def _collect_post(self, raw_post: dict[str, Any], topic_label: str) -> None:
        author_id = self._merge_user_doc(self.fetcher.extract_user(raw_post), [topic_label])
        profile_url = raw_profile_url(raw_post)
        if author_id and profile_url:
            self.profile_urls_by_user.setdefault(author_id, profile_url)
        post_doc = self.fetcher.extract_post(raw_post, author_id)
        self._merge_content_doc(self.posts_map, post_doc, [topic_label])

        if self.max_replies_per_post <= 0:
            return
        post_url = _normalize_string(post_doc.get("url"))
        post_key = facebook_url_id(post_url) or post_url
        if not post_url or not post_key:
            return
        self.comment_tasks_by_post[post_doc["external_content_id"]] = {
            "post_doc": post_doc,
            "url": post_url,
            "post_key": post_key,
            "source_topics": [topic_label],
        }

    def _collect_comments(self) -> None:
        tasks = list(self.comment_tasks_by_post.values())
        if not tasks or self.max_replies_per_post <= 0:
            return
        batches = self._chunked(tasks, self.comment_batch_size)
        for batch_idx, task_batch in enumerate(batches, start=1):
            log(f"[comments {batch_idx}/{len(batches)}] {len(task_batch)} 条帖子")
            comments_by_post = self.fetcher.fetch_posts_comments(
                [task["url"] for task in task_batch],
                self.max_replies_per_post,
            )
            for task in task_batch:
                comments = comments_by_post.get(task["post_key"], [])
                for raw_comment in comments[:self.max_replies_per_post]:
                    self._collect_reply_records(raw_comment, task["post_doc"], task["source_topics"])
            time.sleep(self.request_sleep_seconds)

    def _enrich_user_profiles(self) -> None:
        if self.max_profile_details_users <= 0:
            return

        candidates: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for external_user_id, profile_url in self.profile_urls_by_user.items():
            normalized_url = normalize_facebook_url(profile_url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            candidates.append((external_user_id, profile_url))
            if len(candidates) >= self.max_profile_details_users:
                break

        if not candidates:
            return

        log(f"补齐 Facebook 主页详情: {len(candidates)} 个用户")
        external_id_by_key: dict[str, str] = {}
        for external_user_id, profile_url in candidates:
            keys = {
                external_user_id,
                profile_id_from_url(profile_url),
                normalize_facebook_url(profile_url),
            }
            for key in keys:
                if key:
                    external_id_by_key[key] = external_user_id

        batches = self._chunked([profile_url for _, profile_url in candidates], self.profile_batch_size)
        for batch_idx, profile_urls in enumerate(batches, start=1):
            log(f"[profiles {batch_idx}/{len(batches)}] {len(profile_urls)} 个主页")
            profiles = self.fetcher.fetch_page_profiles(profile_urls)
            if not profiles:
                profiles = self.fetcher.fetch_page_profiles_by_search(profile_urls)
            for profile_key, raw_profile in profiles.items():
                external_user_id = external_id_by_key.get(profile_key)
                if not external_user_id:
                    page_url = raw_profile_url(raw_profile)
                    external_user_id = external_id_by_key.get(profile_id_from_url(page_url))
                    external_user_id = external_user_id or external_id_by_key.get(normalize_facebook_url(page_url))
                if not external_user_id:
                    continue
                existing_user = self.users_map.get(external_user_id, {})
                profile_doc = self.fetcher.extract_user(raw_profile)
                if not profile_doc:
                    continue
                profile_doc["external_user_id"] = external_user_id
                self._merge_user_doc(profile_doc, existing_user.get("source_topics", []))
            time.sleep(self.request_sleep_seconds)

    def _ensure_profile_quality(self) -> None:
        if not self.users_map:
            return
        if any(self._is_profile_detail(user_doc) for user_doc in self.users_map.values()):
            return
        raise RuntimeError(
            "Facebook 用户主页详情未抓到，已停止写库。请稍后重试，避免把只有最小作者字段的数据写入数据库。"
        )

    def _collect_reply_records(
        self,
        raw_comment: dict[str, Any],
        post_doc: dict[str, Any],
        source_topics: list[str],
    ) -> None:
        self._merge_user_doc(self.fetcher.extract_comment_user(raw_comment), source_topics)
        reply_doc = self.fetcher.extract_comment(
            raw_comment,
            parent_content_id=post_doc["external_content_id"],
            root_content_id=post_doc["external_content_id"],
        )
        self._merge_content_doc(self.replies_map, reply_doc, source_topics)

    def _build_payload(
        self,
        topic_specs: list[dict[str, str]],
        topic_rows_meta: list[dict[str, Any]],
    ) -> dict[str, Any]:
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
            "topics_document": {"facebook_queries": [topic_spec["topic_label"] for topic_spec in topic_specs]},
            "users": users_out,
            "posts": posts_out,
            "replies": replies_out,
            "posts_texts": posts_texts,
            "replies_texts": replies_texts,
            "meta": {
                "actors": {
                    "posts": "scraper_one/facebook-posts-search",
                    "page_posts": "apify/facebook-posts-scraper",
                    "profiles": "apify/facebook-pages-scraper",
                    "profile_search": "apify/facebook-search-scraper",
                    "comments": "scraper_one/facebook-comments-scraper",
                },
                "topic_rows": topic_rows_meta,
                "collected_at": now_iso(),
                "search_type": self.search_type,
                "start_date": self.start_date,
                "end_date": self.end_date,
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
            f"{payload['meta']['counts']['replies']} 条回复"
        )
        return payload

    @staticmethod
    def _chunked(items: list[Any], size: int) -> list[list[Any]]:
        return [items[idx: idx + size] for idx in range(0, len(items), size)]


def run_fetch_pipeline(
    topics: list[str] | None = None,
    max_topics: int = DEFAULT_MAX_TOPICS,
    max_posts: int = DEFAULT_MAX_POSTS,
    max_replies_per_post: int = DEFAULT_MAX_REPLIES_PER_POST,
    search_type: str = DEFAULT_SEARCH_TYPE,
    start_date: str | None = None,
    end_date: str | None = None,
    days_back: int = DEFAULT_DAYS_BACK,
    request_sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
    comment_batch_size: int = DEFAULT_COMMENT_BATCH_SIZE,
) -> dict[str, Any]:
    token = get_apify_key()
    if not token:
        raise RuntimeError("缺少 APIFY_KEY：请在 backend/.env 中设置 APIFY_KEY")

    if not start_date and days_back > 0:
        start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).date().isoformat()
    if not end_date and start_date:
        end_date = datetime.now(timezone.utc).date().isoformat()

    collector = FacebookDatasetCollector(
        fetcher=FacebookFetcher(token, request_sleep_seconds),
        max_posts=max_posts,
        max_replies_per_post=max_replies_per_post,
        comment_batch_size=comment_batch_size,
        profile_batch_size=DEFAULT_PROFILE_BATCH_SIZE,
        max_profile_details_users=DEFAULT_MAX_PROFILE_DETAILS_USERS,
        search_type=search_type,
        start_date=start_date,
        end_date=end_date,
        request_sleep_seconds=request_sleep_seconds,
    )
    return collector.collect(topics=topics, max_topics=max_topics)
