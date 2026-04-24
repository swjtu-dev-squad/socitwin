"""
Instagram 爬取工具类

负责调用 Apify API、数据提取等。
"""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 配置
PLATFORM = "instagram"
ACTOR = "apify/instagram-scraper"
ENV_FILE = Path(__file__).parents[3] / ".env"
KOL_FOLLOWER_THRESHOLD = 20000

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_apify_key() -> str:
    """获取 APIFY_KEY"""
    key = os.getenv("APIFY_KEY", "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("APIFY_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != "your-apify-api-key-here":
                    return key
    return ""


def run_apify_actor(token: str, payload: dict) -> list[dict]:
    """调用 Apify Actor"""
    query = urllib.parse.urlencode({"token": token, "clean": "true"})
    actor_id = ACTOR.replace("/", "~")
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?{query}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode()) or []
    except urllib.error.HTTPError as e:
        log(f"Apify request failed with HTTP {e.code}")
        raise RuntimeError(f"Apify error: HTTP {e.code}") from e


def clean_str(v: Any) -> str:
    return str(v).strip() if v else ""


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


def engagement_score(raw: dict) -> int:
    likes = to_int(raw.get("likesCount") or raw.get("like_count") or raw.get("likes")) or 0
    comments = to_int(raw.get("commentsCount") or raw.get("comment_count") or raw.get("comments")) or 0
    views = to_int(
        raw.get("videoViewCount")
        or raw.get("videoPlayCount")
        or raw.get("viewsCount")
        or raw.get("view_count")
        or raw.get("play_count")
    ) or 0
    return likes + comments * 3 + views // 100


def extract_hashtags(text: str, raw: dict | None = None) -> list[str]:
    """从文本中提取 hashtag"""
    tags = set()
    if text:
        tags.update(normalize_topic_key(tag) for tag in re.findall(r"#(\w+)", text))

    if raw:
        for key in ("hashtags", "hashtagsList"):
            values = raw.get(key)
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict):
                        tag = item.get("name") or item.get("tag") or item.get("hashtag")
                    else:
                        tag = item
                    normalized = normalize_topic_key(tag)
                    if normalized:
                        tags.add(normalized)

    return sorted(tag for tag in tags if tag)


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
        if not username:
            return None

        follower_count = to_int(
            raw.get("followersCount")
            or raw.get("ownerFollowersCount")
            or raw.get("ownerFollowers")
            or raw.get("followers")
            or raw.get("follower_count")
            or raw.get("followers_count")
            or owner.get("followers_count")
            or owner.get("followers")
            or user.get("followers_count")
            or user.get("followers")
        )
        following_count = to_int(
            raw.get("followsCount")
            or raw.get("ownerFollowsCount")
            or raw.get("following")
            or raw.get("following_count")
            or raw.get("followingsCount")
            or owner.get("following_count")
            or owner.get("following")
            or user.get("following_count")
            or user.get("following")
        )
        post_count = to_int(
            raw.get("postsCount")
            or raw.get("ownerPostsCount")
            or raw.get("posts")
            or raw.get("media_count")
            or raw.get("mediaCount")
            or owner.get("media_count")
            or owner.get("posts")
            or user.get("media_count")
            or user.get("posts")
        )

        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_user_id": username,
            "username": username,
            "display_name": clean_str(
                raw.get("fullName")
                or raw.get("ownerFullName")
                or raw.get("full_name")
                or owner.get("full_name")
                or user.get("full_name")
                or raw.get("name")
            ),
            "bio": clean_str(raw.get("biography") or raw.get("bio")),
            "location": clean_str(raw.get("location") or ""),
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
                "instagram_user_id": raw.get("id") or raw.get("ownerId") or owner.get("id") or user.get("id") or user.get("pk"),
                "profile_pic_url": (
                    raw.get("profilePicUrl")
                    or raw.get("profile_pic_url")
                    or owner.get("profile_pic_url")
                    or user.get("profile_pic_url")
                ),
                "external_url": raw.get("externalUrl") or raw.get("external_url"),
                "business_category": raw.get("businessCategoryName") or raw.get("category"),
                "is_private": raw.get("private") or raw.get("isPrivate") or owner.get("is_private"),
                "is_business": raw.get("isBusinessAccount") or raw.get("is_business"),
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
                raw.get("timestamp") or raw.get("takenAtTimestamp") or raw.get("createdAt")
            ) or now_iso(),
            "like_count": to_int(raw.get("likesCount") or raw.get("like_count") or raw.get("likes")),
            "reply_count": to_int(raw.get("commentsCount") or raw.get("comment_count") or raw.get("comments")),
            "share_count": to_int(raw.get("sharesCount") or raw.get("shares")),
            "view_count": to_int(
                raw.get("videoViewCount")
                or raw.get("videoPlayCount")
                or raw.get("viewsCount")
                or raw.get("view_count")
                or raw.get("play_count")
            ),
            "raw_json": to_json(raw),
        }

    def extract_comment_user(self, raw: dict) -> dict | None:
        """从评论记录中提取评论者的最小用户信息。"""
        owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
        username = clean_str(raw.get("ownerUsername") or owner.get("username"))
        if not username:
            return None
        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_user_id": username,
            "username": username,
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
        author_id = clean_str(raw.get("ownerUsername") or owner.get("username") or raw.get("ownerId") or owner.get("id"))

        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_content_id": comment_id,
            "content_type": "comment",
            "author_external_user_id": author_id,
            "parent_external_content_id": parent_content_id,
            "root_external_content_id": root_content_id,
            "text": clean_str(raw.get("text") or raw.get("comment") or ""),
            "language": None,
            "created_at": parse_instagram_timestamp(raw.get("timestamp") or raw.get("created_at")) or now_iso(),
            "like_count": to_int(raw.get("likesCount") or raw.get("likeCount")),
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

    def fetch_topic_posts(self, topic_label: str, limit: int) -> list[dict]:
        """通过 hashtag 页面 URL 直接爬取 Instagram 公开帖子，按互动分排序。"""
        log(f"  搜索 topic: {topic_label}")
        posts = []
        seen = set()

        started_at = time.monotonic()
        try:
            hashtag_url = f"https://www.instagram.com/explore/tags/{topic_label}/"
            results = run_apify_actor(self.token, {
                "directUrls": [hashtag_url],
                "resultsType": "posts",
                "resultsLimit": min(50, max(20, limit * 3)),
                "addParentData": True,
            })
            if results:
                log(f"  [DEBUG] 第一条结果 keys: {sorted(results[0].keys())}")
            for item in results:
                post_key = clean_str(
                    item.get("id") or item.get("pk") or media_code_from_record(item)
                )
                if post_key and post_key not in seen:
                    seen.add(post_key)
                    item["_source_topic_label"] = topic_label
                    posts.append(item)
        except Exception as e:
            log(f"  警告: topic 搜索失败 '{topic_label}' - {e}")
        elapsed = time.monotonic() - started_at

        posts.sort(key=engagement_score, reverse=True)
        log(f"  topic 返回 {len(posts)} 条公开帖子，耗时 {elapsed:.1f}s")
        return posts[:limit]

    def fetch_user_profiles(self, usernames: list[str]) -> dict[str, dict]:
        """批量获取用户主页详情，用于补齐粉丝数并区分 kol/normal。"""
        usernames = [name for name in usernames if name]
        if not usernames:
            return {}
        try:
            results = run_apify_actor(self.token, {
                "directUrls": [f"https://www.instagram.com/{username}/" for username in usernames],
                "resultsType": "details",
                "resultsLimit": 1,
                "addParentData": True,
            })
        except Exception as e:
            log(f"  警告: 批量用户详情爬取失败 - {e}")
            return {}

        profiles = {}
        for item in results:
            username = clean_str(
                item.get("username")
                or item.get("ownerUsername")
                or item.get("userName")
                or ""
            )
            if username:
                profiles[username] = item
        return profiles

    def fetch_users_posts(self, usernames: list[str], limit: int) -> dict[str, list[dict]]:
        """批量爬取多个用户的公开帖子，减少 Apify actor 启动次数。"""
        usernames = [name for name in usernames if name]
        if not usernames or limit <= 0:
            return {}

        payload = {
            "directUrls": [f"https://www.instagram.com/{username}/" for username in usernames],
            "resultsType": "posts",
            "resultsLimit": limit,
            "addParentData": True,
        }
        try:
            results = run_apify_actor(self.token, payload)
        except Exception as e:
            log(f"  警告: 批量爬取用户帖子失败 - {e}")
            return {}

        grouped: dict[str, list[dict]] = defaultdict(list)
        fallback_username = usernames[0] if len(usernames) == 1 else ""
        for item in results:
            username = clean_str(
                item.get("ownerUsername")
                or item.get("username")
                or item.get("userName")
                or fallback_username
            )
            if username:
                grouped[username].append(item)
        return dict(grouped)

    def fetch_user_posts(self, username: str, limit: int, only_newer_than: str | None = None) -> list[dict]:
        """爬取用户帖子"""
        payload = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": limit,
            "addParentData": True,
        }
        if only_newer_than:
            payload["onlyPostsNewerThan"] = only_newer_than
        try:
            return run_apify_actor(self.token, payload)
        except Exception as e:
            log(f"  警告: @{username} 爬取失败 - {e}")
            return []

    def fetch_posts_comments(self, post_urls: list[str], limit: int) -> dict[str, list[dict]]:
        """批量爬取多个帖子的公开评论，按 Instagram media code 分组。"""
        post_urls = [url for url in post_urls if url]
        if not post_urls or limit <= 0:
            return {}
        try:
            results = run_apify_actor(self.token, {
                "directUrls": post_urls,
                "resultsType": "comments",
                "resultsLimit": min(limit, 50),
                "addParentData": True,
            })
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
            return run_apify_actor(self.token, {
                "directUrls": [post_url],
                "resultsType": "comments",
                "resultsLimit": min(limit, 50),
            })
        except Exception as e:
            log(f"  警告: 评论爬取失败 {post_url} - {e}")
            return []
