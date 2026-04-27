"""
Instagram 爬取工具类

负责调用 Apify API、数据提取等。
"""

import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from utils.apify_utils import run_apify_actor
except ModuleNotFoundError:
    from datasets.utils.apify_utils import run_apify_actor

# 配置
PLATFORM = "instagram"
ACTOR = "apify/instagram-scraper"
HASHTAG_ACTOR = "apify/instagram-hashtag-scraper"
KOL_FOLLOWER_THRESHOLD = 20000

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def clean_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def to_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        v = v.replace(",", "").strip()
        return int(v) if v.isdigit() else None
    return None


def to_json(v: Any) -> str | None:
    return json.dumps(v, ensure_ascii=False) if v is not None else None


def location_from_profile(raw: dict, owner: dict, user: dict) -> str:
    direct_location = clean_str(
        first_present(
            raw.get("location"),
            raw.get("businessCityName"),
            raw.get("cityName"),
            raw.get("city"),
            owner.get("location"),
            user.get("location"),
        )
    )
    if direct_location:
        return direct_location

    address = raw.get("businessAddressJson") or raw.get("business_address_json")
    if isinstance(address, str) and address.strip():
        try:
            address = json.loads(address)
        except json.JSONDecodeError:
            return address.strip()
    if not isinstance(address, dict):
        return ""

    parts = [
        clean_str(address.get("street_address")),
        clean_str(address.get("city_name") or address.get("city")),
        clean_str(address.get("zip_code")),
        clean_str(address.get("country_code")),
    ]
    return ", ".join(part for part in parts if part)


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode()).hexdigest()[:16]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_instagram_timestamp(value: Any) -> str | None:
    """把 Apify/Instagram 常见 timestamp 格式归一为 ISO UTC 字符串。"""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        normalized = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return raw
    return None


def parse_cutoff_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return None

    raw = value.strip().lower()
    if not raw:
        return None

    match = re.fullmatch(r"(\d+)\s+(day|days|week|weeks|month|months|year|years)", raw)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        days_by_unit = {
            "day": 1,
            "days": 1,
            "week": 7,
            "weeks": 7,
            "month": 30,
            "months": 30,
            "year": 365,
            "years": 365,
        }
        return datetime.now(timezone.utc) - timedelta(days=amount * days_by_unit[unit])

    try:
        dt = datetime.fromisoformat(raw.replace("z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def record_created_at(raw: dict) -> datetime | None:
    parsed = parse_instagram_timestamp(
        first_present(raw.get("timestamp"), raw.get("takenAtTimestamp"), raw.get("createdAt"))
    )
    if not parsed:
        return None
    try:
        dt = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_topic_key(value: Any) -> str:
    text = clean_str(value).lstrip("#").lower()
    return re.sub(r"\s+", "_", text)


def media_code_from_url(value: Any) -> str:
    text = clean_str(value)
    if not text:
        return ""
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#]+)", text)
    return match.group(1) if match else ""


def media_code_from_record(raw: dict) -> str:
    for key in (
        "shortCode",
        "shortcode",
        "code",
        "postShortCode",
        "postShortcode",
        "postCode",
    ):
        value = clean_str(raw.get(key))
        if value:
            return value
    for key in ("url", "postUrl", "postURL", "inputUrl", "displayUrl", "permalink", "post_url"):
        value = media_code_from_url(raw.get(key))
        if value:
            return value
    return ""


def is_post_record(raw: dict) -> bool:
    """过滤掉 Apify hashtag/search 元数据，只保留真实帖子记录。"""
    if media_code_from_record(raw):
        return True
    if clean_str(raw.get("ownerUsername") or raw.get("caption") or raw.get("captionText")):
        return True
    if raw.get("timestamp") or raw.get("takenAtTimestamp") or raw.get("createdAt"):
        return True
    return False


def engagement_score(raw: dict) -> int:
    likes = to_int(first_present(raw.get("likesCount"), raw.get("like_count"), raw.get("likes"))) or 0
    comments = to_int(first_present(raw.get("commentsCount"), raw.get("comment_count"), raw.get("comments"))) or 0
    views = to_int(
        first_present(
            raw.get("videoViewCount"),
            raw.get("videoPlayCount"),
            raw.get("viewsCount"),
            raw.get("view_count"),
            raw.get("play_count"),
        )
    ) or 0
    return likes + comments * 3 + views // 100


class InstagramFetcher:
    """Instagram 数据爬取器"""

    def __init__(self, token: str, sleep: float = 0.5):
        self.token = token
        self.sleep = sleep

    def extract_user(self, raw: dict) -> dict | None:
        """提取用户信息，兼容 profile 和 post-owner 两种数据格式"""
        owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        username = clean_str(
            raw.get("username")
            or raw.get("ownerUsername")
            or owner.get("username")
            or user.get("username")
            or raw.get("userName")
            or raw.get("owner_username")
            or raw.get("author_username")
            or raw.get("screen_name")
            or owner.get("screen_name")
            or user.get("screen_name")
            or ""
        )
        instagram_user_id = clean_str(
            raw.get("ownerId")
            or raw.get("owner_id")
            or owner.get("id")
            or user.get("id")
            or user.get("pk")
            or ""
        )
        external_user_id = username or (f"instagram_user_{instagram_user_id}" if instagram_user_id else "")
        if not external_user_id:
            return None

        follower_count = to_int(
            first_present(
                raw.get("followersCount"),
                raw.get("ownerFollowersCount"),
                raw.get("ownerFollowers"),
                raw.get("followers"),
                raw.get("follower_count"),
                raw.get("followers_count"),
                owner.get("followers_count"),
                owner.get("followers"),
                user.get("followers_count"),
                user.get("followers"),
            )
        )
        following_count = to_int(
            first_present(
                raw.get("followsCount"),
                raw.get("ownerFollowsCount"),
                raw.get("following"),
                raw.get("following_count"),
                raw.get("followingsCount"),
                owner.get("following_count"),
                owner.get("following"),
                user.get("following_count"),
                user.get("following"),
            )
        )
        post_count = to_int(
            first_present(
                raw.get("postsCount"),
                raw.get("ownerPostsCount"),
                raw.get("posts"),
                raw.get("media_count"),
                raw.get("mediaCount"),
                owner.get("media_count"),
                owner.get("posts"),
                user.get("media_count"),
                user.get("posts"),
            )
        )

        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_user_id": external_user_id,
            "username": username or external_user_id,
            "display_name": clean_str(
                raw.get("fullName")
                or raw.get("ownerFullName")
                or raw.get("full_name")
                or owner.get("full_name")
                or user.get("full_name")
                or raw.get("name")
            ),
            "bio": clean_str(first_present(raw.get("biography"), raw.get("bio"))),
            "location": location_from_profile(raw, owner, user),
            "verified": 1 if (
                raw.get("isVerified")
                or raw.get("verified")
                or owner.get("is_verified")
                or user.get("is_verified")
            ) else 0,
            "follower_count": follower_count,
            "following_count": following_count,
            "tweet_count": post_count,
            "post_count": post_count,
            "user_type": (
                "kol"
                if follower_count is not None and follower_count > KOL_FOLLOWER_THRESHOLD
                else "normal"
            ),
            "profile_json": to_json({
                "instagram_user_id": instagram_user_id or raw.get("id"),
                "profile_pic_url": (
                    first_present(
                        raw.get("profilePicUrl"),
                        raw.get("profile_pic_url"),
                        raw.get("profilePicUrlHD"),
                        owner.get("profile_pic_url"),
                        user.get("profile_pic_url"),
                    )
                ),
                "external_url": first_present(raw.get("externalUrl"), raw.get("external_url")),
                "business_category": first_present(raw.get("businessCategoryName"), raw.get("category")),
                "is_private": first_present(raw.get("private"), raw.get("isPrivate"), owner.get("is_private")),
                "is_business": first_present(raw.get("isBusinessAccount"), raw.get("is_business")),
            }),
            "raw_json": to_json(raw),
        }

    def extract_post(self, raw: dict, author_id: str) -> dict:
        """提取帖子信息"""
        post_id = clean_str(raw.get("id") or raw.get("pk") or raw.get("shortCode") or raw.get("shortcode") or "")
        if not post_id:
            post_id = stable_id("ig_post", author_id, raw.get("caption", ""), raw.get("timestamp", ""))

        owner_username = clean_str(raw.get("ownerUsername") or author_id)

        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_content_id": post_id,
            "content_type": "post",
            "author_external_user_id": owner_username,
            "parent_external_content_id": None,
            "root_external_content_id": post_id,
            "text": clean_str(raw.get("caption") or raw.get("captionText") or ""),
            "language": None,
            "created_at": parse_instagram_timestamp(
                first_present(raw.get("timestamp"), raw.get("takenAtTimestamp"), raw.get("createdAt"))
            ) or now_iso(),
            "like_count": to_int(first_present(raw.get("likesCount"), raw.get("like_count"), raw.get("likes"))),
            "reply_count": to_int(first_present(raw.get("commentsCount"), raw.get("comment_count"), raw.get("comments"))),
            "share_count": to_int(first_present(raw.get("sharesCount"), raw.get("shares"))),
            "view_count": to_int(
                first_present(
                    raw.get("videoViewCount"),
                    raw.get("videoPlayCount"),
                    raw.get("viewsCount"),
                    raw.get("view_count"),
                    raw.get("play_count"),
                )
            ),
            "raw_json": to_json(raw),
        }

    def extract_comment_user(self, raw: dict) -> dict | None:
        """从评论记录中提取评论者的最小用户信息。"""
        owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
        username = clean_str(raw.get("ownerUsername") or owner.get("username"))
        owner_id = clean_str(raw.get("ownerId") or owner.get("id"))
        external_user_id = username or (f"instagram_user_{owner_id}" if owner_id else "")
        if not external_user_id:
            return None
        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_user_id": external_user_id,
            "username": username or external_user_id,
            "display_name": clean_str(raw.get("ownerFullName") or owner.get("full_name")),
            "bio": None,
            "location": None,
            "verified": 1 if (raw.get("ownerIsVerified") or owner.get("is_verified")) else 0,
            "profile_json": to_json({
                "instagram_user_id": raw.get("ownerId") or owner.get("id"),
                "profile_pic_url": raw.get("ownerProfilePicUrl") or owner.get("profile_pic_url"),
                "is_private": owner.get("is_private"),
            }),
            "raw_json": to_json(owner or raw),
        }

    def extract_comment(self, raw: dict, parent_content_id: str, root_content_id: str) -> dict:
        """提取评论/回复信息。"""
        owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
        comment_id = clean_str(raw.get("id") or raw.get("commentId") or "")
        if not comment_id:
            comment_id = stable_id("ig_comment", parent_content_id, raw.get("text", ""), raw.get("timestamp", ""))
        username = clean_str(raw.get("ownerUsername") or owner.get("username"))
        owner_id = clean_str(raw.get("ownerId") or owner.get("id"))
        author_id = username or (f"instagram_user_{owner_id}" if owner_id else "")

        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_content_id": comment_id,
            "content_type": "reply",
            "author_external_user_id": author_id,
            "parent_external_content_id": parent_content_id,
            "root_external_content_id": root_content_id,
            "text": clean_str(raw.get("text") or raw.get("comment") or ""),
            "language": None,
            "created_at": parse_instagram_timestamp(first_present(raw.get("timestamp"), raw.get("created_at"))) or now_iso(),
            "like_count": to_int(first_present(raw.get("likesCount"), raw.get("likeCount"))),
            "reply_count": to_int(raw.get("repliesCount")),
            "share_count": None,
            "view_count": None,
            "raw_json": to_json(raw),
        }

    def post_url(self, raw: dict) -> str:
        """从帖子记录中提取或构造 URL，用于后续评论抓取。"""
        url = clean_str(
            raw.get("url")
            or raw.get("postUrl")
            or raw.get("postURL")
            or raw.get("permalink")
            or raw.get("post_url")
            or raw.get("inputUrl")
        )
        if url:
            return url
        shortcode = clean_str(
            raw.get("shortCode")
            or raw.get("shortcode")
            or raw.get("code")
        )
        return f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""

    def fetch_topic_posts(
        self,
        topic_label: str,
        limit: int,
        only_newer_than: str | None = None,
    ) -> list[dict]:
        """通过 hashtag 页面抓取公开帖子。"""
        normalized_topic = clean_str(topic_label).lstrip("#")
        if not normalized_topic or limit <= 0:
            return []

        log(f"  搜索 topic: #{normalized_topic}")
        posts: list[dict] = []
        seen: set[str] = set()
        cutoff = parse_cutoff_time(only_newer_than)

        def append_results(results: list[dict]) -> None:
            for item in results:
                if not is_post_record(item):
                    continue
                if cutoff:
                    created_at = record_created_at(item)
                    if created_at and created_at < cutoff:
                        continue
                post_key = clean_str(
                    item.get("id") or item.get("pk") or media_code_from_record(item)
                )
                if post_key and post_key not in seen:
                    seen.add(post_key)
                    item["_source_topic_label"] = normalized_topic
                    posts.append(item)

        started_at = time.monotonic()
        try:
            payload = {
                "hashtags": [normalized_topic],
                "resultsType": "posts",
                "resultsLimit": min(50, max(1, limit * 2)),
            }
            results = run_apify_actor(self.token, HASHTAG_ACTOR, payload, timeout=35)
            append_results(results)
        except Exception as e:
            log(f"  警告: hashtag 帖子抓取失败 '#{normalized_topic}' - {e}")

        elapsed = time.monotonic() - started_at
        posts.sort(key=engagement_score, reverse=True)
        log(f"  topic 返回 {len(posts)} 条公开帖子，耗时 {elapsed:.1f}s")
        return posts[:limit]

    def fetch_user_profiles(self, usernames: list[str]) -> dict[str, dict]:
        """批量获取已出现作者的主页详情。"""
        clean_usernames = []
        seen = set()
        for username in usernames:
            normalized = clean_str(username).lstrip("@")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            clean_usernames.append(normalized)

        if not clean_usernames:
            return {}

        try:
            results = run_apify_actor(
                self.token,
                ACTOR,
                {
                    "directUrls": [f"https://www.instagram.com/{username}/" for username in clean_usernames],
                    "resultsType": "details",
                    "resultsLimit": 1,
                    "addParentData": True,
                },
                timeout=30,
            )
        except Exception as e:
            log(f"  警告: 批量用户详情爬取失败 - {e}")
            return {}

        profiles: dict[str, dict] = {}
        for item in results:
            username = clean_str(
                first_present(
                    item.get("username"),
                    item.get("ownerUsername"),
                    item.get("userName"),
                )
            ).lstrip("@")
            if username:
                profiles[username] = item
        return profiles

    def fetch_posts_comments(self, post_urls: list[str], limit: int) -> dict[str, list[dict]]:
        """批量爬取多个帖子的公开评论，按 Instagram media code 分组。"""
        post_urls = [url for url in post_urls if url]
        if not post_urls or limit <= 0:
            return {}
        try:
            results = run_apify_actor(self.token, ACTOR, {
                "directUrls": post_urls,
                "resultsType": "comments",
                "resultsLimit": min(limit, 50),
                "addParentData": True,
            }, timeout=30)
        except Exception as e:
            log(f"  警告: 批量评论爬取失败 - {e}")
            return {}

        grouped: dict[str, list[dict]] = defaultdict(list)
        fallback_code = media_code_from_url(post_urls[0]) if len(post_urls) == 1 else ""
        unmatched = 0
        for item in results:
            code = media_code_from_record(item) or fallback_code
            if code:
                grouped[code].append(item)
            else:
                unmatched += 1
        if unmatched:
            log(f"  警告: {unmatched} 条评论缺少父帖标识，已跳过")
        return dict(grouped)

    def fetch_post_comments(self, post_url: str, limit: int) -> list[dict]:
        """爬取公开帖子评论。Apify 限制和 Instagram 返回量会影响实际数量。"""
        if not post_url or limit <= 0:
            return []
        try:
            return run_apify_actor(self.token, ACTOR, {
                "directUrls": [post_url],
                "resultsType": "comments",
                "resultsLimit": min(limit, 50),
            }, timeout=30)
        except Exception as e:
            log(f"  警告: 评论爬取失败 {post_url} - {e}")
            return []
