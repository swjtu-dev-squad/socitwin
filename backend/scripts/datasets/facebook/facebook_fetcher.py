"""
Facebook Apify 抓取与字段归一。
"""

import hashlib
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

try:
    from utils.apify_utils import run_apify_actor
except ModuleNotFoundError:
    from datasets.utils.apify_utils import run_apify_actor

PLATFORM = "facebook"
POSTS_SEARCH_ACTOR = "scraper_one/facebook-posts-search"
PAGE_POSTS_ACTOR = "apify/facebook-posts-scraper"
COMMENTS_ACTOR = "scraper_one/facebook-comments-scraper"
PAGE_DETAILS_ACTOR = "apify/facebook-pages-scraper"
PAGE_SEARCH_ACTOR = "apify/facebook-search-scraper"
KOL_FOLLOWER_THRESHOLD = 20000


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def clean_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        return int(normalized) if re.fullmatch(r"-?\d+", normalized) else None
    return None


def to_count(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    raw = clean_str(value).replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])?", raw, flags=re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(unit, 1)
    return int(number * multiplier)


def to_json(value: Any) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def select_keys(raw: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: raw.get(key) for key in keys if key in raw}


def compact_user_raw(raw: dict[str, Any]) -> dict[str, Any]:
    return select_keys(
        raw,
        (
            "author",
            "page",
            "user",
            "facebookUrl",
            "pageUrl",
            "profileUrl",
            "authorProfileUrl",
            "pageId",
            "facebookId",
            "pageName",
            "title",
            "name",
            "intro",
            "bio",
            "description",
            "address",
            "location",
            "categories",
            "category",
            "followers",
            "followings",
            "likes",
            "followersCount",
            "followingCount",
            "website",
            "websites",
            "email",
            "phone",
            "profilePictureUrl",
            "coverPhotoUrl",
        ),
    )


def compact_post_raw(raw: dict[str, Any]) -> dict[str, Any]:
    return select_keys(
        raw,
        (
            "url",
            "postUrl",
            "topLevelUrl",
            "facebookUrl",
            "inputUrl",
            "postId",
            "id",
            "pageName",
            "facebookId",
            "time",
            "timestamp",
            "createdAt",
            "postText",
            "text",
            "message",
            "content",
            "link",
            "likes",
            "comments",
            "shares",
            "likesCount",
            "commentsCount",
            "sharesCount",
            "reactionsCount",
            "viewsCount",
            "reactionLikeCount",
            "reactionLoveCount",
            "reactionCareCount",
            "reactionWowCount",
            "reactionHahaCount",
            "author",
            "user",
            "page",
            "attachments",
        ),
    )


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_topic_key(value: Any) -> str:
    text = clean_str(value).lstrip("#").lower()
    text = re.sub(r"[^\w\s:-]+", "", text)
    return re.sub(r"\s+", "_", text).strip("_")


def parse_facebook_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    raw = clean_str(value)
    if not raw:
        return None
    if raw.isdigit():
        number = int(raw)
        seconds = number / 1000 if number > 10_000_000_000 else number
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return raw


def facebook_url_id(value: Any) -> str:
    text = clean_str(value)
    if not text:
        return ""
    match = re.search(r"/(?:posts|videos|photos|permalink)/([^/?#]+)", text)
    if match:
        return match.group(1).strip("/")
    match = re.search(r"[?&](?:story_fbid|fbid)=([^&#]+)", text)
    return match.group(1) if match else ""


def profile_id_from_url(value: Any) -> str:
    text = clean_str(value)
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    if "facebook.com" not in parsed.netloc:
        return ""
    query = urllib.parse.parse_qs(parsed.query)
    if query.get("id"):
        return clean_str(query["id"][0])
    path = parsed.path.strip("/")
    if not path or path in {"profile.php", "people", "groups", "pages"}:
        return ""
    return path.split("/")[0]


def normalize_facebook_url(value: Any) -> str:
    text = clean_str(value)
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    if not parsed.netloc:
        return text.rstrip("/").lower()
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc.lower(), path, "", "", "")).lower()


def raw_profile_url(raw: dict[str, Any]) -> str:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    page = raw.get("page") if isinstance(raw.get("page"), dict) else {}
    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    return clean_str(
        first_present(
            raw.get("authorProfileUrl"),
            raw.get("profileUrl"),
            raw.get("userUrl"),
            raw.get("pageUrl"),
            raw.get("facebookUrl"),
            author.get("url"),
            author.get("profileUrl"),
            author.get("profile_url"),
            page.get("url"),
            page.get("profileUrl"),
            page.get("profile_url"),
            user.get("url"),
            user.get("profileUrl"),
            user.get("profile_url"),
        )
    )


class FacebookFetcher:
    def __init__(self, token: str, request_sleep_seconds: float = 0.5) -> None:
        self.token = token
        self.request_sleep_seconds = request_sleep_seconds

    def fetch_topic_posts(
        self,
        query: str,
        limit: int,
        search_type: str = "latest",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        topic = clean_str(query).lstrip("#")
        if not topic or limit <= 0:
            return []
        payload: dict[str, Any] = {
            "query": topic,
            "resultsCount": limit,
            "searchType": search_type,
        }
        if start_date:
            payload["startDate"] = start_date
        if end_date:
            payload["endDate"] = end_date

        log(f"  搜索 topic: {topic}")
        started_at = time.monotonic()
        try:
            results = run_apify_actor(self.token, POSTS_SEARCH_ACTOR, payload, timeout=90)
        except Exception as exc:
            log(f"  警告: Facebook 帖子抓取失败 '{topic}' - {exc}")
            return []
        log(f"  topic 返回 {len(results)} 条公开帖子，耗时 {time.monotonic() - started_at:.1f}s")
        return results[:limit]

    def fetch_page_posts(self, page_urls: list[str], limit_per_page: int) -> list[dict[str, Any]]:
        urls = [url for url in page_urls if url]
        if not urls or limit_per_page <= 0:
            return []

        log(f"  抓取 page posts: {len(urls)} 个页面")
        started_at = time.monotonic()
        try:
            results = run_apify_actor(
                self.token,
                PAGE_POSTS_ACTOR,
                {
                    "startUrls": [{"url": url} for url in urls[:5]],
                    "resultsLimit": min(max(1, limit_per_page), 100),
                    "captionText": False,
                },
                timeout=45,
            )
        except Exception as exc:
            log(f"  警告: Facebook 页面帖子抓取失败 - {exc}")
            return []
        log(f"  page posts 返回 {len(results)} 条公开帖子，耗时 {time.monotonic() - started_at:.1f}s")
        return results

    def fetch_posts_comments(self, post_urls: list[str], limit: int) -> dict[str, list[dict[str, Any]]]:
        urls = [url for url in post_urls if url]
        if not urls or limit <= 0:
            return {}
        try:
            results = run_apify_actor(
                self.token,
                COMMENTS_ACTOR,
                {
                    "postUrls": urls,
                    "resultsLimit": min(limit, 50),
                    "commentsSortType": "relevant",
                },
                timeout=30,
            )
        except Exception as exc:
            log(f"  警告: 批量评论抓取失败 - {exc}")
            return {}

        grouped: dict[str, list[dict[str, Any]]] = {facebook_url_id(url) or url: [] for url in urls}
        fallback_key = facebook_url_id(urls[0]) or urls[0] if len(urls) == 1 else ""
        for item in results:
            post_url = first_present(
                item.get("postUrl"),
                item.get("postURL"),
                item.get("url"),
                item.get("facebookUrl"),
                item.get("inputUrl"),
            )
            key = facebook_url_id(post_url) or fallback_key
            if key:
                grouped.setdefault(key, []).append(item)
        return grouped

    def fetch_page_profiles(self, profile_urls: list[str]) -> dict[str, dict[str, Any]]:
        clean_urls = []
        seen = set()
        for profile_url in profile_urls:
            normalized_url = normalize_facebook_url(profile_url)
            if not normalized_url or normalized_url in seen:
                continue
            seen.add(normalized_url)
            clean_urls.append(profile_url)

        if not clean_urls:
            return {}

        def index_profiles(results: list[dict[str, Any]], requested_urls: list[str]) -> dict[str, dict[str, Any]]:
            profiles: dict[str, dict[str, Any]] = {}
            for idx, item in enumerate(results):
                fallback_url = requested_urls[idx] if idx < len(requested_urls) else ""
                page_url = clean_str(first_present(item.get("pageUrl"), item.get("facebookUrl"), item.get("url")))
                keys = {
                    clean_str(item.get("pageId")),
                    clean_str(item.get("facebookId")),
                    clean_str(item.get("pageName")),
                    profile_id_from_url(page_url),
                    normalize_facebook_url(page_url),
                }
                if not page_url:
                    keys.add(normalize_facebook_url(fallback_url))
                for key in keys:
                    if key:
                        profiles[key] = item
            return profiles

        try:
            results = run_apify_actor(
                self.token,
                PAGE_DETAILS_ACTOR,
                {"startUrls": [{"url": profile_url} for profile_url in clean_urls]},
                timeout=60,
            )
        except Exception as exc:
            log(f"  警告: 批量主页详情抓取失败 - {exc}")
            if len(clean_urls) <= 1:
                return {}

            profiles: dict[str, dict[str, Any]] = {}
            for profile_url in clean_urls:
                try:
                    single_result = run_apify_actor(
                        self.token,
                        PAGE_DETAILS_ACTOR,
                        {"startUrls": [{"url": profile_url}]},
                        timeout=45,
                    )
                except Exception as single_exc:
                    log(f"  警告: 主页详情抓取失败 {profile_url} - {single_exc}")
                    continue
                profiles.update(index_profiles(single_result, [profile_url]))
                time.sleep(self.request_sleep_seconds)
            return profiles

        return index_profiles(results, clean_urls)

    def fetch_page_profiles_by_search(self, profile_urls: list[str]) -> dict[str, dict[str, Any]]:
        search_terms = []
        seen = set()
        for profile_url in profile_urls:
            term = profile_id_from_url(profile_url)
            if not term or term in seen:
                continue
            seen.add(term)
            search_terms.append(term)

        if not search_terms:
            return {}

        try:
            results = run_apify_actor(
                self.token,
                PAGE_SEARCH_ACTOR,
                {
                    "categories": search_terms,
                    "resultsLimit": len(search_terms),
                    "locations": [],
                },
                timeout=60,
            )
        except Exception as exc:
            log(f"  警告: Facebook 搜索主页详情失败 - {exc}")
            return {}

        profiles: dict[str, dict[str, Any]] = {}
        for item in results:
            page_url = raw_profile_url(item)
            keys = {
                clean_str(item.get("pageId")),
                clean_str(item.get("facebookId")),
                clean_str(item.get("pageName")),
                clean_str(item.get("title")),
                clean_str(item.get("name")),
                profile_id_from_url(page_url),
                normalize_facebook_url(page_url),
            }
            for key in keys:
                if key:
                    profiles[key] = item
        return profiles

    def extract_user(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
        page = raw.get("page") if isinstance(raw.get("page"), dict) else {}
        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        about_me = raw.get("about_me") if isinstance(raw.get("about_me"), dict) else {}
        profile_url = raw_profile_url(raw)
        author_name = clean_str(
            first_present(
                raw.get("authorName"),
                raw.get("profileName"),
                raw.get("pageName"),
                raw.get("title"),
                raw.get("name"),
                author.get("name"),
                page.get("name"),
                user.get("name"),
            )
        )
        external_user_id = clean_str(
            first_present(
                raw.get("authorId"),
                raw.get("userId"),
                raw.get("profileId"),
                raw.get("pageId"),
                raw.get("facebookId"),
                author.get("id"),
                page.get("id"),
                user.get("id"),
                profile_id_from_url(profile_url),
                author_name,
            )
        )
        if not external_user_id:
            return None

        follower_count = to_int(
            first_present(
                raw.get("followers"),
                raw.get("followersCount"),
                raw.get("followerCount"),
                raw.get("followers_count"),
                author.get("followersCount"),
                author.get("followerCount"),
                page.get("followersCount"),
                page.get("followerCount"),
                user.get("followersCount"),
                user.get("followerCount"),
            )
        ) or to_count(first_present(raw.get("followersText"), raw.get("followers_text")))
        following_count = to_int(
            first_present(
                raw.get("followings"),
                raw.get("followingCount"),
                raw.get("following_count"),
                author.get("followingCount"),
                user.get("followingCount"),
            )
        ) or to_count(first_present(raw.get("followingText"), raw.get("following_text")))
        post_count = to_int(first_present(raw.get("postsCount"), author.get("postsCount"), page.get("postsCount")))
        bio = clean_str(
            first_present(
                raw.get("intro"),
                raw.get("bio"),
                raw.get("description"),
                raw.get("about"),
                about_me.get("text"),
                author.get("description"),
                page.get("description"),
                user.get("description"),
            )
        )
        location = clean_str(
            first_present(
                raw.get("address"),
                raw.get("location"),
                raw.get("singleLineAddress"),
                raw.get("single_line_address"),
                author.get("location"),
                page.get("location"),
                user.get("location"),
            )
        )
        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_user_id": external_user_id,
            "username": profile_id_from_url(profile_url) or author_name or external_user_id,
            "display_name": author_name,
            "bio": bio,
            "location": location,
            "verified": 1 if first_present(raw.get("isVerified"), raw.get("verified"), raw.get("is_verified"), author.get("verified"), page.get("verified"), user.get("verified")) else 0,
            "follower_count": follower_count,
            "following_count": following_count,
            "tweet_count": post_count,
            "post_count": post_count,
            "user_type": "kol" if follower_count is not None and follower_count > KOL_FOLLOWER_THRESHOLD else "normal",
            "profile_json": to_json(
                {
                    "profile_url": profile_url,
                    "page_url": raw.get("pageUrl"),
                    "likes": to_count(first_present(raw.get("likes"), raw.get("likesCount"))),
                    "categories": raw.get("categories") or raw.get("category"),
                    "website": raw.get("website"),
                    "websites": raw.get("websites"),
                    "email": raw.get("email"),
                    "phone": raw.get("phone"),
                    "profile_picture_url": first_present(raw.get("profilePictureUrl"), raw.get("profile_picture_url")),
                    "cover_photo_url": first_present(raw.get("coverPhotoUrl"), raw.get("cover_photo_url")),
                    "raw_author": author or page or user or None,
                }
            ),
            "raw_json": to_json(compact_user_raw(raw)),
        }

    def extract_post(self, raw: dict[str, Any], author_id: str) -> dict[str, Any]:
        url = clean_str(first_present(raw.get("url"), raw.get("postUrl"), raw.get("permalinkUrl"), raw.get("permalink_url")))
        post_id = clean_str(first_present(raw.get("postId"), raw.get("post_id"), raw.get("id"), facebook_url_id(url)))
        if not post_id:
            post_id = stable_id("fb_post", author_id, raw.get("postText"), raw.get("timestamp"), url)
        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_content_id": post_id,
            "content_type": "post",
            "author_external_user_id": author_id,
            "parent_external_content_id": None,
            "root_external_content_id": post_id,
            "text": clean_str(first_present(raw.get("postText"), raw.get("message"), raw.get("text"), raw.get("content"), raw.get("title"))),
            "language": clean_str(raw.get("language")) or None,
            "created_at": parse_facebook_timestamp(first_present(raw.get("timestamp"), raw.get("createdAt"), raw.get("created_at"), raw.get("date"))) or now_iso(),
            "like_count": to_int(first_present(raw.get("likesCount"), raw.get("reactionsCount"), raw.get("reactionCount"), raw.get("likes"))),
            "reply_count": to_int(first_present(raw.get("commentsCount"), raw.get("commentCount"), raw.get("comments"))),
            "share_count": to_int(first_present(raw.get("sharesCount"), raw.get("shareCount"), raw.get("shares"))),
            "view_count": to_int(first_present(raw.get("viewsCount"), raw.get("videoViewCount"))),
            "url": url,
            "raw_json": to_json(compact_post_raw(raw)),
        }

    def extract_comment_user(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        return self.extract_user(raw)

    def extract_comment(self, raw: dict[str, Any], parent_content_id: str, root_content_id: str) -> dict[str, Any]:
        comment_url = clean_str(first_present(raw.get("url"), raw.get("commentUrl"), raw.get("facebookUrl")))
        comment_id = clean_str(first_present(raw.get("commentId"), raw.get("id"), facebook_url_id(comment_url)))
        if not comment_id:
            comment_id = stable_id("fb_comment", parent_content_id, raw.get("text"), raw.get("date"))
        author_doc = self.extract_comment_user(raw)
        return {
            "platform": PLATFORM,
            "type": PLATFORM,
            "external_content_id": comment_id,
            "content_type": "reply",
            "author_external_user_id": author_doc.get("external_user_id") if author_doc else "",
            "parent_external_content_id": parent_content_id,
            "root_external_content_id": root_content_id,
            "text": clean_str(first_present(raw.get("text"), raw.get("commentText"), raw.get("comment"), raw.get("message"))),
            "language": clean_str(raw.get("language")) or None,
            "created_at": parse_facebook_timestamp(first_present(raw.get("timestamp"), raw.get("createdAt"), raw.get("date"))) or now_iso(),
            "like_count": to_int(first_present(raw.get("likesCount"), raw.get("reactionsCount"), raw.get("reactionCount"))),
            "reply_count": to_int(first_present(raw.get("repliesCount"), raw.get("replyCount"))),
            "share_count": None,
            "view_count": None,
            "raw_json": to_json(raw),
        }
