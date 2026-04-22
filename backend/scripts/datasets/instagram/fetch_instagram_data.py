"""
Instagram 数据采集脚本

流程：固定热点 topic → Instagram 相关公开帖子 → 评论区采样用户 → 区分 KOL/normal → 爬取用户帖子/评论 → 写入数据集。

用法：
    cd backend
    uv run python scripts/datasets/instagram/fetch_instagram_data.py --user-count 50
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# 将 scripts/datasets 加入模块搜索路径
_SCRIPTS_DATASETS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_DATASETS))

from utils.db_utils import DatasetDB
from instagram.instagram_fetcher import (
    InstagramFetcher,
    extract_hashtags,
    get_apify_key,
    log,
    media_code_from_record,
    media_code_from_url,
    normalize_topic_key,
    now_iso,
)

# ============== 配置 ==============
DEFAULT_USER_COUNT = 20
HOT_TOPICS = [
    "trending",
    "viral",
    "explorepage",
    "reels",
    "instagood",
    "foodie",
    "wanderlust",
    "fitnessmotivation",
    "fashionreels",
    "ootd",
    "streetstyle",
    "tech",
    "AI",
    "recipeereel",
    "foodreels",
    "travelgram",
    "gymlife",
    "fitfam",
    "healthylifestyle",
    "reelsinstagram",
]
TOPIC_POSTS_PER_TOPIC = 10
TOPIC_POST_COMMENTS_PER_POST = 20
POSTS_PER_USER = 10
COMMENTS_PER_POST = 10
PROFILE_BATCH_SIZE = 10
USER_POST_BATCH_SIZE = 5
COMMENT_BATCH_SIZE = 10
REQUEST_SLEEP_SECONDS = 0.5

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "datasets" / "oasis_datasets.db"


def chunked(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def parse_json_object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def topic_key_from_label(label: str) -> str:
    text = " ".join(str(label or "").strip().lower().split())
    return re.sub(r"[^\w\s:-]+", "", text)


def load_hot_topics() -> list[dict]:
    """读取脚本内固定热点 topic，不依赖其他平台或外部趋势接口。"""
    topics: list[dict] = []
    seen: set[str] = set()
    for rank, label in enumerate(HOT_TOPICS, start=1):
        topic_key = topic_key_from_label(label)
        if not topic_key or topic_key in seen:
            continue
        seen.add(topic_key)
        topics.append(
            {
                "topic_key": topic_key,
                "topic_label": label,
                "topic_type": "hot_topic",
                "trend_rank": rank,
                "news_external_id": None,
                "raw": {"source": "fixed_hot_topics", "rank": rank},
            }
        )
    return topics


def annotate_user_strategy(user_data: dict, strategy: str, known_strategies: set[str] | None = None) -> dict:
    profile = parse_json_object(user_data.get("profile_json"))
    strategies = profile.get("sample_strategies")
    if not isinstance(strategies, list):
        strategies = []
    if known_strategies:
        for known in sorted(known_strategies):
            if known and known not in strategies:
                strategies.append(known)
    if strategy and strategy not in strategies:
        strategies.append(strategy)
    profile["sample_strategy"] = strategies[0] if strategies else strategy
    profile["sample_strategies"] = strategies
    user_data["profile_json"] = json.dumps(profile, ensure_ascii=False)
    return user_data


def hashtag_topic_keys(raw_post: dict, content_text: str) -> list[str]:
    return sorted(dict.fromkeys(extract_hashtags(content_text or "", raw_post)))


def crawl(user_count: int) -> dict:
    """主爬取流程"""

    token = get_apify_key()
    if not token:
        log("错误: 缺少 APIFY_KEY，请在 backend/.env 中配置")
        sys.exit(1)

    fetcher = InstagramFetcher(token, REQUEST_SLEEP_SECONDS)
    stats = {
        "hot_topics": 0,
        "users": 0,
        "topic_posts": 0,
        "posts": 0,
        "comments": 0,
        "topics": 0,
    }
    collected_at = now_iso()

    topic_stats: dict[str, dict] = {}
    user_topic_stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"content_count": 0, "roles": set()}
    )
    inserted_users: set[str] = set()
    inserted_contents: set[str] = set()
    user_rows: dict[str, dict] = {}
    sampled_usernames: list[str] = []
    sampled_seen: set[str] = set()
    user_strategy: dict[str, str] = {}
    user_strategies: dict[str, set[str]] = defaultdict(set)
    user_primary_topic: dict[str, str] = {}

    def ensure_topic(
        topic_key: str,
        topic_label: str,
        topic_type: str,
        news_external_id: str | None = None,
        trend_rank: int | None = None,
        raw_meta: dict | None = None,
    ) -> None:
        if not topic_key:
            return
        if topic_key not in topic_stats:
            topic_stats[topic_key] = {
                "topic_label": topic_label,
                "topic_type": topic_type,
                "news_external_id": news_external_id,
                "trend_rank": trend_rank,
                "raw_meta": raw_meta or {},
                "post_count": 0,
                "reply_count": 0,
                "user_ids": set(),
            }

    def track_topic(topic_key: str, user_id: str | None, role: str, content_type: str) -> None:
        if not topic_key or topic_key not in topic_stats:
            return
        if content_type == "post":
            topic_stats[topic_key]["post_count"] += 1
        else:
            topic_stats[topic_key]["reply_count"] += 1
        if user_id:
            topic_stats[topic_key]["user_ids"].add(user_id)
            stat = user_topic_stats[(topic_key, user_id)]
            stat["content_count"] += 1
            stat["roles"].add(role)

    def insert_user(user_data: dict | None, strategy: str) -> str:
        if not user_data:
            return ""
        username = str(user_data.get("username") or user_data.get("external_user_id") or "").strip()
        if not username:
            return ""
        existing = user_rows.get(username, {})
        merged = dict(existing)

        for key, value in user_data.items():
            if key in {"follower_count", "following_count", "tweet_count", "post_count", "verified", "profile_json"}:
                continue
            if value not in (None, ""):
                merged[key] = value

        for key in ("follower_count", "following_count", "tweet_count", "post_count"):
            old_value = safe_int(existing.get(key))
            new_value = safe_int(user_data.get(key))
            if old_value is None:
                merged[key] = new_value
            elif new_value is None:
                merged[key] = old_value
            else:
                merged[key] = max(old_value, new_value)

        merged["verified"] = 1 if int(existing.get("verified") or 0) or int(user_data.get("verified") or 0) else 0

        profile = parse_json_object(existing.get("profile_json"))
        profile.update(parse_json_object(user_data.get("profile_json")))
        for known in profile.get("sample_strategies") or []:
            if known:
                user_strategies[username].add(str(known))
        if strategy:
            user_strategies[username].add(strategy)
        merged["profile_json"] = json.dumps(profile, ensure_ascii=False)
        merged = annotate_user_strategy(merged, strategy, user_strategies[username])

        follower_count = safe_int(merged.get("follower_count"))
        merged["user_type"] = "kol" if follower_count is not None and follower_count > 20000 else "normal"

        db.insert_user(merged)
        user_rows[username] = merged
        if username not in inserted_users:
            inserted_users.add(username)
            stats["users"] += 1
        user_strategy.setdefault(username, strategy)
        return username

    def add_sampled_user(username: str, strategy: str) -> None:
        if not username or username in sampled_seen or len(sampled_usernames) >= user_count:
            return
        sampled_seen.add(username)
        sampled_usernames.append(username)
        user_strategy.setdefault(username, strategy)

    def insert_content(content: dict) -> bool:
        content_id = str(content.get("external_content_id") or "").strip()
        if not content_id:
            return False
        is_new = content_id not in inserted_contents
        db.insert_content(content)
        if is_new:
            inserted_contents.add(content_id)
        return is_new

    def write_post(raw_post: dict, fallback_author: str, primary_topic: dict, is_topic_source_post: bool) -> dict | None:
        content = fetcher.extract_post(raw_post, fallback_author)
        if insert_content(content):
            stats["posts"] += 1
            if is_topic_source_post:
                stats["topic_posts"] += 1
        author_id = content["author_external_user_id"] or fallback_author

        db.add_content_topic(
            "instagram",
            content["external_content_id"],
            primary_topic["topic_key"],
            row_type="instagram",
        )
        track_topic(primary_topic["topic_key"], author_id, "author", "post")
        if author_id:
            user_primary_topic.setdefault(author_id, primary_topic["topic_key"])

        for tag in hashtag_topic_keys(raw_post, content.get("text") or ""):
            hashtag_key = normalize_topic_key(tag)
            if not hashtag_key:
                continue
            ensure_topic(
                hashtag_key,
                f"#{hashtag_key}",
                "hashtag",
                raw_meta={"source": "instagram_content_hashtag"},
            )
            db.add_content_topic(
                "instagram",
                content["external_content_id"],
                hashtag_key,
                row_type="instagram",
            )
            track_topic(hashtag_key, author_id, "author", "post")

        post_url = fetcher.post_url(raw_post)
        media_code = media_code_from_record(raw_post) or media_code_from_url(post_url)
        # 用 media_code 构造 URL，或从 URL 提取 media_code
        if not post_url and media_code:
            post_url = f"https://www.instagram.com/p/{media_code}/"
        if not media_code and post_url:
            media_code = media_code_from_url(post_url)
        if not post_url or not media_code:
            log(f"  警告: 帖子 {content['external_content_id']} 缺少 URL/media_code，跳过评论爬取")
            return None
        return {
            "url": post_url,
            "media_code": media_code,
            "parent_content_id": content["external_content_id"],
            "root_content_id": content["root_external_content_id"],
            "primary_topic_key": primary_topic["topic_key"],
            "author_external_user_id": author_id,
        }

    def write_comment(raw_comment: dict, task: dict, strategy: str, sample_user: bool = False) -> None:
        primary_topic_key = task["primary_topic_key"]
        comment_user = fetcher.extract_comment_user(raw_comment)
        commenter = insert_user(comment_user, strategy)
        if sample_user and commenter:
            add_sampled_user(commenter, strategy)
            user_primary_topic.setdefault(commenter, primary_topic_key)

        comment = fetcher.extract_comment(
            raw_comment,
            parent_content_id=task["parent_content_id"],
            root_content_id=task["root_content_id"],
        )
        if insert_content(comment):
            stats["comments"] += 1

        db.add_content_topic(
            "instagram",
            comment["external_content_id"],
            primary_topic_key,
            row_type="instagram",
        )
        track_topic(primary_topic_key, comment["author_external_user_id"], "replier", "comment")

        for tag in extract_hashtags(comment.get("text") or "", raw_comment):
            hashtag_key = normalize_topic_key(tag)
            if not hashtag_key:
                continue
            ensure_topic(
                hashtag_key,
                f"#{hashtag_key}",
                "hashtag",
                raw_meta={"source": "instagram_comment_hashtag"},
            )
            db.add_content_topic(
                "instagram",
                comment["external_content_id"],
                hashtag_key,
                row_type="instagram",
            )
            track_topic(hashtag_key, comment["author_external_user_id"], "replier", "comment")

    def fetch_comments_for_tasks(tasks: list[dict], limit: int) -> dict[str, list[dict]]:
        comments_by_code = fetcher.fetch_posts_comments(
            [task["url"] for task in tasks],
            limit,
        )
        if not comments_by_code and len(tasks) > 1:
            log("  批量评论没有返回可匹配结果，降级为单帖重试")
            comments_by_code = {
                task["media_code"]: fetcher.fetch_post_comments(task["url"], limit)
                for task in tasks
            }
        return comments_by_code

    with DatasetDB(DEFAULT_DB_PATH) as db:
        db.ensure_schema()
        db.begin_transaction()

        # ===== Step 1: 固定热点 topic =====
        hot_topics = load_hot_topics()
        stats["hot_topics"] = len(hot_topics)
        if not hot_topics:
            raise RuntimeError("没有配置固定热点 topic；请检查 HOT_TOPICS")

        topic_post_comment_tasks: list[dict] = []
        log(f"固定热点 topic: {len(hot_topics)} 个")
        for topic_idx, topic in enumerate(hot_topics, start=1):
            if len(sampled_usernames) >= user_count:
                log(f"已采样 {len(sampled_usernames)}/{user_count} 个用户，跳过剩余话题")
                break
            ensure_topic(
                topic["topic_key"],
                topic["topic_label"],
                topic["topic_type"],
                topic.get("news_external_id"),
                topic.get("trend_rank"),
                {
                    "source": "fixed_hot_topics",
                    "rank": topic.get("trend_rank"),
                    "raw": topic.get("raw"),
                },
            )
            log(f"[topic {topic_idx}/{len(hot_topics)}] {topic['topic_label']}")
            posts = fetcher.fetch_topic_posts(topic["topic_label"], TOPIC_POSTS_PER_TOPIC)
            for raw_post in posts:
                owner = insert_user(fetcher.extract_user(raw_post), "hot_topic_post_author")
                if owner:
                    add_sampled_user(owner, "hot_topic_post_author")
                task = write_post(raw_post, owner, topic, is_topic_source_post=True)
                if task:
                    topic_post_comment_tasks.append(task)
            time.sleep(REQUEST_SLEEP_SECONDS)

        # ===== Step 2: 从 topic 相关帖子评论区采样用户 =====
        comment_batches = list(chunked(topic_post_comment_tasks, COMMENT_BATCH_SIZE))
        for batch_idx, task_batch in enumerate(comment_batches, start=1):
            log(f"爬取 topic 帖子评论批次 {batch_idx}/{len(comment_batches)}: {len(task_batch)} 条帖子")
            started_at = time.monotonic()
            comments_by_code = fetch_comments_for_tasks(task_batch, TOPIC_POST_COMMENTS_PER_POST)
            batch_comment_count = sum(len(comments) for comments in comments_by_code.values())
            log(f"  topic 评论批次完成: {batch_comment_count} 条，耗时 {time.monotonic() - started_at:.1f}s")

            for task in task_batch:
                for raw_comment in comments_by_code.get(task["media_code"], []):
                    write_comment(raw_comment, task, "hot_topic_post_commenter", sample_user=True)
            if len(sampled_usernames) >= user_count:
                break
            time.sleep(REQUEST_SLEEP_SECONDS)

        log(f"采样用户: {len(sampled_usernames)}/{user_count}")

        # ===== Step 3: 批量补齐用户详情，按统一规则区分 KOL/normal =====
        profile_batches = list(chunked(sampled_usernames, PROFILE_BATCH_SIZE))
        for batch_idx, username_batch in enumerate(profile_batches, start=1):
            log(f"补齐用户详情批次 {batch_idx}/{len(profile_batches)}: {len(username_batch)} 个用户")
            profiles = fetcher.fetch_user_profiles(username_batch)
            for username in username_batch:
                profile = profiles.get(username)
                if profile:
                    insert_user(
                        fetcher.extract_user(profile),
                        user_strategy.get(username, "hot_topic_post_commenter"),
                    )
            time.sleep(REQUEST_SLEEP_SECONDS)

        # ===== Step 4: 批量爬取采样用户帖子 =====
        sampled_post_comment_tasks: list[dict] = []
        # 采样用户个人帖子使用该用户第一次进入样本池时关联的固定热点 topic。

        user_batches = list(chunked(sampled_usernames, USER_POST_BATCH_SIZE))
        for batch_idx, username_batch in enumerate(user_batches, start=1):
            log(f"爬取采样用户帖子批次 {batch_idx}/{len(user_batches)}: {', '.join('@' + u for u in username_batch)}")
            started_at = time.monotonic()
            posts_by_user = fetcher.fetch_users_posts(username_batch, POSTS_PER_USER)
            if not posts_by_user and len(username_batch) > 1:
                log("  批量帖子没有返回可匹配结果，降级为单用户重试")
                posts_by_user = {
                    username: fetcher.fetch_user_posts(username, POSTS_PER_USER)
                    for username in username_batch
                }
            batch_post_count = sum(len(posts) for posts in posts_by_user.values())
            log(f"  采样用户帖子批次完成: {batch_post_count} 条，耗时 {time.monotonic() - started_at:.1f}s")

            fallback_topic = hot_topics[0]
            topic_by_key = {topic["topic_key"]: topic for topic in hot_topics}
            for username in username_batch:
                primary_topic = topic_by_key.get(user_primary_topic.get(username, ""), fallback_topic)
                for raw_post in posts_by_user.get(username, []):
                    task = write_post(raw_post, username, primary_topic, is_topic_source_post=False)
                    if task:
                        sampled_post_comment_tasks.append(task)
            time.sleep(REQUEST_SLEEP_SECONDS)

        # ===== Step 5: 批量爬取采样用户帖子下的评论 =====
        user_comment_batches = list(chunked(sampled_post_comment_tasks, COMMENT_BATCH_SIZE))
        for batch_idx, task_batch in enumerate(user_comment_batches, start=1):
            log(f"爬取采样用户帖子评论批次 {batch_idx}/{len(user_comment_batches)}: {len(task_batch)} 条帖子")
            started_at = time.monotonic()
            comments_by_code = fetch_comments_for_tasks(task_batch, COMMENTS_PER_POST)
            batch_comment_count = sum(len(comments) for comments in comments_by_code.values())
            log(f"  采样用户帖子评论批次完成: {batch_comment_count} 条，耗时 {time.monotonic() - started_at:.1f}s")

            for task in task_batch:
                for raw_comment in comments_by_code.get(task["media_code"], []):
                    write_comment(raw_comment, task, "sampled_user_post_commenter")
            time.sleep(REQUEST_SLEEP_SECONDS)

        # ===== Step 6: 汇总话题并写入 topics/user_topics 表 =====
        log(f"提取到 {len(topic_stats)} 个话题")
        for topic_key, ts in topic_stats.items():
            db.insert_topic({
                "platform": "instagram",
                "type": "instagram",
                "topic_key": topic_key,
                "topic_label": ts["topic_label"],
                "topic_type": ts["topic_type"],
                "trend_rank": ts.get("trend_rank"),
                "post_count": ts["post_count"],
                "reply_count": ts["reply_count"],
                "user_count": len(ts["user_ids"]),
                "first_seen_at": collected_at,
                "last_seen_at": collected_at,
                "news_external_id": ts.get("news_external_id"),
                "raw_json": json.dumps(
                    {
                        **(ts.get("raw_meta") or {}),
                        "entry_method": "fixed_hot_topics",
                        "hot_topic_count": len(HOT_TOPICS),
                        "topic_posts_per_topic": TOPIC_POSTS_PER_TOPIC,
                        "topic_post_comments_per_post": TOPIC_POST_COMMENTS_PER_POST,
                        "posts_per_user": POSTS_PER_USER,
                        "comments_per_post": COMMENTS_PER_POST,
                        "kol_rule": "followers_count > 20000",
                    },
                    ensure_ascii=False,
                ),
            })
            stats["topics"] += 1

            for user_id in sorted(ts["user_ids"]):
                stat = user_topic_stats[(topic_key, user_id)]
                roles = stat["roles"]
                role = "both" if {"author", "replier"}.issubset(roles) else next(iter(roles), "author")
                db.add_user_topic(
                    "instagram",
                    topic_key,
                    user_id,
                    role,
                    stat["content_count"],
                    row_type="instagram",
                    news_external_id=ts.get("news_external_id"),
                )

        db.commit()

    log(f"完成: {stats}")
    return {"status": "success", "stats": stats}


def main():
    parser = argparse.ArgumentParser(description="Instagram数据采集")
    parser.add_argument("--user-count", type=int, default=DEFAULT_USER_COUNT, help="获取用户数量")
    args = parser.parse_args()

    result = crawl(args.user_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
