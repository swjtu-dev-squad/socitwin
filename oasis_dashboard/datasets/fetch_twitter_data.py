"""
Twitter 数据采集集成脚本
默认行为：获取热门趋势 -> 搜索趋势帖子 -> 结构化数据 -> 直接写入 MongoDB
"""

import argparse
import os
import sys
import time
import json
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import requests
from dotenv import load_dotenv, dotenv_values
from pathlib import Path

# 脚本所在目录 = oasis_dashboard/datasets
# 项目根目录 = 向上两级
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"

# override=True：避免父进程传入空的 TWITTER_BEARER_TOKEN 时挡住 .env 里的值
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=True)


def _twitter_bearer_token() -> str:
    """优先从 .env 文件读取，再读环境变量；避免 spawn 继承空变量导致读不到 token。"""
    if _ENV_FILE.is_file():
        raw = (dotenv_values(_ENV_FILE).get("TWITTER_BEARER_TOKEN") or "").strip()
        if raw:
            return raw
    return (os.getenv("TWITTER_BEARER_TOKEN") or "").strip()

# ============== 可配置区域 ==============
API_BASE_V2 = "https://api.x.com/2"
WOEID = 23424960  # 泰国

# 趋势数量限制
MAX_TRENDS = 3

# 每个话题抓取多少条帖子
MAX_POSTS = 10

# 每条帖子抓取多少条回复
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

COLLECTIONS = {
    "users": "users",
    "posts": "posts",
    "replies": "replies",
    "relationships": "relationships",
    "networks": "networks",
    "topics": "topics",
    "persona_datasets": "persona_datasets",
    "generated_agents": "generated_agents",
    "generated_graphs": "generated_graphs",
}

ZERO_COUNTS = {
    "users": 0,
    "posts": 0,
    "replies": 0,
    "relationships": 0,
    "networks": 0,
    "topics": 0,
}

EMPTY_AVAILABILITY = {
    "users": "not_collected",
    "posts": "not_collected",
    "replies": "not_collected",
    "relationships": "not_collected",
    "networks": "not_collected",
    "topics": "not_collected",
}


def _log(msg: str) -> None:
    """进度日志打到 stderr，便于 --preview 时 stdout 仅输出一行 JSON。"""
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _unique_strings(values: List[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        text = _normalize_string(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _format_timestamp_for_id(date: Optional[datetime] = None) -> str:
    target = date or datetime.now(timezone.utc)
    target = target.astimezone(timezone.utc)
    return target.strftime("%Y%m%dT%H%M%SZ")


def create_dataset_id() -> str:
    return f"dataset_{_format_timestamp_for_id()}_{uuid4().hex[:8]}"


def _ensure_counts(partial: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    counts = dict(ZERO_COUNTS)
    if partial:
        for key in counts:
            raw = partial.get(key)
            try:
                counts[key] = int(raw) if raw is not None else 0
            except Exception:
                counts[key] = 0
    return counts


def _build_availability(counts: Dict[str, int], overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    normalized_counts = _ensure_counts(counts)
    availability = dict(EMPTY_AVAILABILITY)
    for key, value in normalized_counts.items():
        availability[key] = "collected" if value > 0 else "not_collected"
    if overrides:
        availability.update(overrides)
    return availability


def _determine_dataset_status(availability: Dict[str, str]) -> str:
    values = list(availability.values())
    if values and all(value == "failed" for value in values):
        return "failed"
    required_ok = availability.get("users") in {"collected", "unsupported"} and availability.get("posts") in {
        "collected",
        "unsupported",
    }
    return "ready" if required_ok else "partial"


def _build_external_id(doc_type: str, doc: Dict[str, Any], recsys_type: str) -> str:
    if doc_type == "users":
        return (
            _normalize_string(doc.get("twitter_user_id"))
            or _normalize_string(doc.get("external_user_id"))
            or _normalize_string(doc.get("external_id"))
            or _normalize_string(doc.get("user_name"))
            or f"{recsys_type}:user:{doc.get('agent_id') if doc.get('agent_id') is not None else uuid4()}"
        )
    if doc_type == "posts":
        return (
            _normalize_string(doc.get("twitter_post_id"))
            or _normalize_string(doc.get("external_post_id"))
            or _normalize_string(doc.get("external_id"))
            or f"{recsys_type}:post:{doc.get('post_id') if doc.get('post_id') is not None else uuid4()}"
        )
    if doc_type == "replies":
        return (
            _normalize_string(doc.get("twitter_reply_id"))
            or _normalize_string(doc.get("external_reply_id"))
            or _normalize_string(doc.get("external_id"))
            or f"{recsys_type}:reply:{doc.get('reply_id') if doc.get('reply_id') is not None else uuid4()}"
        )
    if doc_type == "relationships":
        return _normalize_string(doc.get("id")) or _normalize_string(doc.get("external_id")) or f"{recsys_type}:relationship:{uuid4()}"
    if doc_type == "networks":
        return _normalize_string(doc.get("userId")) or _normalize_string(doc.get("external_id")) or f"{recsys_type}:network:{uuid4()}"
    return _normalize_string(doc.get("category")) or _normalize_string(doc.get("external_id")) or f"{recsys_type}:topic:{uuid4()}"


def _stable_signature(doc_type: str, doc: Dict[str, Any], recsys_type: str) -> str:
    stable = _build_external_id(doc_type, doc, recsys_type)
    return hashlib.sha1(f"{doc_type}:{stable}".encode("utf-8")).hexdigest()


def _annotate_raw_doc(
    doc_type: str,
    doc: Dict[str, Any],
    dataset_id: str,
    recsys_type: str = "twitter",
    source: str = "twitter_live_fetch",
    ingest_status: str = "collected",
) -> Dict[str, Any]:
    normalized = dict(doc)
    normalized["recsys_type"] = _normalize_string(normalized.get("recsys_type")) or recsys_type
    normalized["dataset_id"] = dataset_id
    normalized["source"] = source
    normalized["ingest_status"] = ingest_status
    normalized["external_id"] = _build_external_id(doc_type, normalized, recsys_type)
    normalized["stable_signature"] = _stable_signature(doc_type, normalized, recsys_type)
    return normalized


def _build_dataset_label(recsys_type: str, source: str, trends: Optional[List[Any]] = None) -> str:
    unique_trends = _unique_strings(trends or [])
    if unique_trends:
        suffix = " +" if len(unique_trends) > 2 else ""
        return f"{recsys_type.upper()} {' / '.join(unique_trends[:2])}{suffix}"
    return f"{recsys_type.upper()} {source}"


def _normalize_fetch_for_dataset(
    dataset_id: str,
    payload: Dict[str, Any],
    source: str = "twitter_live_fetch",
) -> Dict[str, Any]:
    users_payload = payload.get("users") if isinstance(payload.get("users"), list) else []
    posts_payload = payload.get("posts") if isinstance(payload.get("posts"), list) else []
    replies_payload = payload.get("replies") if isinstance(payload.get("replies"), list) else []
    topics_source = payload.get("topics_document") if isinstance(payload.get("topics_document"), dict) else None
    if topics_source is None and isinstance(payload.get("topics"), list):
        topics_source = {"twitter_trends": payload.get("topics", [])}
    topics_source = topics_source or {}

    users_docs = [
        _annotate_raw_doc("users", doc, dataset_id=dataset_id, source=source)
        for doc in users_payload
        if isinstance(doc, dict)
    ]
    posts_docs = [
        _annotate_raw_doc("posts", doc, dataset_id=dataset_id, source=source)
        for doc in posts_payload
        if isinstance(doc, dict)
    ]
    replies_docs = [
        _annotate_raw_doc("replies", doc, dataset_id=dataset_id, source=source)
        for doc in replies_payload
        if isinstance(doc, dict)
    ]
    topics_docs = [
        _annotate_raw_doc(
            "topics",
            {
                "category": category,
                "topics": topics if isinstance(topics, list) else [],
            },
            dataset_id=dataset_id,
            source=source,
        )
        for category, topics in topics_source.items()
    ]

    counts = _ensure_counts(
        {
            "users": len(users_docs),
            "posts": len(posts_docs),
            "replies": len(replies_docs),
            "topics": len(topics_docs),
        }
    )
    availability = _build_availability(
        counts,
        {
            "relationships": "not_collected",
            "networks": "unsupported",
        },
    )
    return {
        "docs": {
            "users": users_docs,
            "posts": posts_docs,
            "replies": replies_docs,
            "relationships": [],
            "networks": [],
            "topics": topics_docs,
        },
        "counts": counts,
        "availability": availability,
    }


def _require_pymongo():
    try:
        from pymongo import MongoClient  # type: ignore
    except ImportError as exc:
        raise RuntimeError("缺少 pymongo，请先安装: pip install pymongo") from exc
    return MongoClient


def _connect_mongodb():
    uri = (os.getenv("MONGODB_URI") or "").strip()
    database = (os.getenv("MONGODB_DATABASE") or "oasis_dataset").strip() or "oasis_dataset"
    if not uri:
        raise RuntimeError("缺少 MONGODB_URI：请在环境变量或 .env 中配置 MongoDB 连接串")
    MongoClient = _require_pymongo()
    client = MongoClient(uri, serverSelectionTimeoutMS=30000)
    db = client[database]
    db.command("ping")
    return client, db


def _ensure_persona_indexes(db: Any) -> None:
    common_options = {"background": True}
    db[COLLECTIONS["users"]].create_index([("dataset_id", 1), ("external_id", 1)], **common_options)
    db[COLLECTIONS["posts"]].create_index([("dataset_id", 1), ("external_id", 1)], **common_options)
    db[COLLECTIONS["replies"]].create_index([("dataset_id", 1), ("external_id", 1)], **common_options)
    db[COLLECTIONS["relationships"]].create_index([("dataset_id", 1), ("external_id", 1)], **common_options)
    db[COLLECTIONS["networks"]].create_index([("dataset_id", 1), ("external_id", 1)], **common_options)
    db[COLLECTIONS["topics"]].create_index([("dataset_id", 1), ("external_id", 1)], **common_options)
    db[COLLECTIONS["persona_datasets"]].create_index([("dataset_id", 1)], unique=True, **common_options)
    db[COLLECTIONS["persona_datasets"]].create_index([("recsys_type", 1), ("updated_at", -1)], **common_options)
    db[COLLECTIONS["generated_agents"]].create_index([("generation_id", 1), ("generated_agent_id", 1)], **common_options)
    db[COLLECTIONS["generated_graphs"]].create_index([("generation_id", 1)], unique=True, **common_options)


def import_payload_to_mongodb(
    payload: Dict[str, Any],
    fetch_options: Dict[str, Any],
) -> Dict[str, Any]:
    client, db = _connect_mongodb()
    try:
        _ensure_persona_indexes(db)

        dataset_id = create_dataset_id()
        normalized = _normalize_fetch_for_dataset(dataset_id=dataset_id, payload=payload)

        for doc_type in ("users", "posts", "replies", "topics"):
            docs = normalized["docs"][doc_type]
            if docs:
                db[COLLECTIONS[doc_type]].insert_many(docs, ordered=False)

        created_at = _now_iso()
        manifest = {
            "dataset_id": dataset_id,
            "label": _build_dataset_label(
                recsys_type="twitter",
                source="twitter_live_fetch",
                trends=payload.get("meta", {}).get("trends_processed"),
            ),
            "recsys_type": "twitter",
            "source": "twitter_live_fetch",
            "status": _determine_dataset_status(normalized["availability"]),
            "ingest_status": "collected",
            "counts": normalized["counts"],
            "availability": normalized["availability"],
            "latest_generation_id": None,
            "created_at": created_at,
            "updated_at": created_at,
            "meta": {
                "fetch_options": fetch_options,
                "imported_via": "github_actions" if os.getenv("GITHUB_ACTIONS") == "true" else "python_cli",
                "trends_processed": payload.get("meta", {}).get("trends_processed", []),
                "collected_at": payload.get("meta", {}).get("collected_at") or created_at,
                "trends_data": payload.get("meta", {}).get("trends_data", []),
            },
        }

        db[COLLECTIONS["persona_datasets"]].replace_one(
            {"dataset_id": dataset_id},
            manifest,
            upsert=True,
        )

        return {
            "status": "success",
            "dataset_id": dataset_id,
            "dataset": manifest,
            "imported": normalized["counts"],
            "availability": manifest["availability"],
        }
    finally:
        client.close()


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


# ============== Step 1: 获取热门趋势 ==============
def get_hot_trends(max_trends: int = MAX_TRENDS) -> List[str]:
    """获取泰国热门趋势列表"""
    url = f"{API_BASE_V2}/trends/by/woeid/{WOEID}"
    params = {"max_trends": max_trends}

    _log(f"[Step 1] 正在获取泰国热门趋势 (max_trends={max_trends})...")

    data = _request("GET", url, params=params)

    # 提取 trend_name
    trends: List[str] = []
    trend_items = data.get("data", []) if isinstance(data, dict) else []
    for item in trend_items:
        if isinstance(item, dict) and item.get("trend_name"):
            trends.append(str(item["trend_name"]))

    _log(f"[Step 1] 获取到 {len(trends)} 个趋势: {trends}")
    return trends


# ============== Step 2: 搜索趋势帖子 ==============
def search_posts(query: str,
                 max_total: int = 50,
                 sort_order: str = "relevancy") -> Dict[str, Any]:
    """使用 /2/tweets/search/all 搜索帖子，自动翻页"""
    tweets: List[Dict[str, Any]] = []
    users_map: Dict[str, Dict[str, Any]] = {}
    places_map: Dict[str, Dict[str, Any]] = {}

    next_token: Optional[str] = None
    remaining = max_total

    SEARCH_ENDPOINT = f"{API_BASE_V2}/tweets/search/all"

    while remaining > 0:
        # Twitter API 要求 max_results 最小为 10，最大为 100
        page_size = min(100, max(10, remaining))
        params = {
            "query": query,
            "max_results": page_size,
            "sort_order": sort_order,
            "expansions": _join(EXPANSIONS),
            "tweet.fields": _join(TWEET_FIELDS),
            "user.fields": _join(USER_FIELDS),
            "place.fields": _join(PLACE_FIELDS),
        }
        if next_token:
            params["next_token"] = next_token

        data = _request("GET", SEARCH_ENDPOINT, params=params)

        page_tweets = data.get("data", [])
        includes = data.get("includes", {}) or {}
        meta = data.get("meta", {}) or {}

        if not page_tweets and not includes and not next_token:
            break

        tweets.extend(page_tweets)

        for u in includes.get("users", []) or []:
            if u.get("id"):
                users_map[u["id"]] = u

        for p in includes.get("places", []) or []:
            if p.get("id"):
                places_map[p["id"]] = p

        remaining -= len(page_tweets)
        next_token = meta.get("next_token")
        if not next_token:
            break

    return {
        "tweets": tweets,
        "users_map": users_map,
        "places_map": places_map,
        "meta": {"total": len(tweets)}
    }


def search_replies(conversation_id: str, max_total: int = 20) -> Dict[str, Any]:
    """基于 conversation_id 搜索回复"""
    q = f"conversation_id:{conversation_id} {BASE_QUERY_FILTERS}"
    return search_posts(q, max_total=max_total, sort_order="recency")


def assemble_result(main_query: str,
                    posts_bundle: Dict[str, Any],
                    replies_limit: int = 15) -> Dict[str, Any]:
    """将主结果与每条帖子的回复整合"""
    users_map = dict(posts_bundle.get("users_map", {}))
    tweets = posts_bundle.get("tweets", [])
    items: List[Dict[str, Any]] = []

    for t in tweets:
        author_id = t.get("author_id")
        author_obj = users_map.get(author_id)
        conv_id = t.get("conversation_id") or t.get("id")

        replies_pack = {"tweets": [], "users_map": {}}
        if conv_id and replies_limit > 0:
            try:
                replies_pack = search_replies(conv_id, max_total=replies_limit)
                for uid, u in replies_pack.get("users_map", {}).items():
                    users_map[uid] = u
            except APIError as e:
                replies_pack = {"error": {"status": e.status_code, "detail": e.detail}}

        replies = replies_pack.get("tweets", [])
        reply_authors = []
        if isinstance(replies_pack, dict) and replies:
            for rt in replies:
                ra = users_map.get(rt.get("author_id"))
                reply_authors.append(ra)

        items.append({
            "post": t,
            "author": author_obj,
            "replies": replies,
            "reply_authors": reply_authors,
            "reply_error": replies_pack.get("error") if isinstance(replies_pack, dict) else None
        })

    return {
        "query": main_query,
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "results": items,
        "users": list(users_map.values()),
        "stats": {
            "posts": len(tweets),
            "unique_users": len(users_map),
        }
    }


def fetch_trend_posts(
    trend_query: str,
    max_posts: int = MAX_POSTS,
    max_replies_per_post: int = MAX_REPLIES_PER_POST,
    sort_order: str = SORT_ORDER,
) -> Dict[str, Any]:
    """获取趋势帖子和回复"""
    final_query = f"{trend_query} {BASE_QUERY_FILTERS}".strip()
    _log(f"[Step 2] 正在搜索趋势帖子: {final_query} (max_posts={max_posts})...")

    posts_bundle = search_posts(final_query, max_total=max_posts, sort_order=sort_order)
    full_result = assemble_result(final_query, posts_bundle, replies_limit=max_replies_per_post)

    _log(f"[Step 2] 获取到 {full_result['stats']['posts']} 条帖子, {full_result['stats']['unique_users']} 个用户")
    return full_result


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
) -> Dict[str, Any]:
    """
    执行完整采集流程，返回可 JSON 序列化的结果（供 HTTP 接口或 --preview 使用）。
    首次请求前会检查 TWITTER_BEARER_TOKEN。
    """
    _get_session()

    mt = MAX_TRENDS if max_trends is None else max_trends
    mp = MAX_POSTS if max_posts is None else max_posts
    mr = MAX_REPLIES_PER_POST if max_replies_per_post is None else max_replies_per_post
    so = SORT_ORDER if sort_order is None else sort_order

    trends = get_hot_trends(max_trends=mt)
    if not trends:
        raise RuntimeError("[Step 1] 未获取到任何趋势")

    all_topics: List[str] = []
    all_users_map: Dict[str, Dict[str, Any]] = {}
    all_posts_map: Dict[str, Dict[str, Any]] = {}
    all_replies_map: Dict[str, Dict[str, Any]] = {}
    all_raw_posts: List[Dict[str, Any]] = []

    for i, trend_name in enumerate(trends):
        _log(f"\n--- 处理趋势 {i + 1}/{len(trends)}: {trend_name} ---")

        try:
            posts_data = fetch_trend_posts(
                trend_name,
                max_posts=mp,
                max_replies_per_post=mr,
                sort_order=so,
            )
        except APIError as e:
            _log(f"[Step 2] 跳过趋势 '{trend_name}': {e.status_code} {e.detail}")
            continue

        if not posts_data.get("results"):
            _log(f"[Step 2] 趋势 '{trend_name}' 无帖子数据，跳过")
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

        all_raw_posts.append({
            "trend_name": trend_name,
            "query": posts_data.get("query"),
            "stats": posts_data.get("stats"),
            "results_count": len(posts_data.get("results", [])),
        })

        if i < len(trends) - 1:
            time.sleep(1)

    topics_dedup, all_users, all_posts, all_replies = finalize_entities(
        all_topics,
        all_users_map,
        all_posts_map,
        all_replies_map,
    )
    all_posts_texts = [post.get("content", "") for post in all_posts if post.get("content")]
    all_replies_texts = [reply.get("content", "") for reply in all_replies if reply.get("content")]

    return {
        "topics": topics_dedup,
        "topics_document": {"twitter_trends": topics_dedup},
        "users": all_users,
        "posts": all_posts,
        "replies": all_replies,
        "posts_texts": all_posts_texts,
        "replies_texts": all_replies_texts,
        "meta": {
            "trends_processed": trends,
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
        description="抓取 X / Twitter 数据并直接写入 MongoDB。默认会入库，只有 --preview 才只输出 JSON。"
    )
    parser.add_argument("--preview", action="store_true", help="只输出抓取结果 JSON，不写入 MongoDB")
    parser.add_argument("--max-trends", type=int, default=MAX_TRENDS, help=f"趋势数量，默认 {MAX_TRENDS}")
    parser.add_argument("--max-posts", type=int, default=MAX_POSTS, help=f"每个趋势抓取帖子数，默认 {MAX_POSTS}")
    parser.add_argument(
        "--max-replies-per-post",
        type=int,
        default=MAX_REPLIES_PER_POST,
        help=f"每条帖子抓取回复数，默认 {MAX_REPLIES_PER_POST}",
    )
    return parser


def _run_cli(argv: List[str]) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    fetch_options = {
        "max_trends": args.max_trends,
        "max_posts": args.max_posts,
        "max_replies_per_post": args.max_replies_per_post,
    }

    try:
        payload = run_fetch_pipeline(**fetch_options)
        if args.preview:
            print(json.dumps(payload, ensure_ascii=False), flush=True)
        else:
            result = import_payload_to_mongodb(payload=payload, fetch_options=fetch_options)
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
