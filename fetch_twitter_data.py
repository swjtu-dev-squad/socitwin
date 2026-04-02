"""
Twitter 数据采集集成脚本
依次执行：获取热门趋势 -> 搜索趋势帖子 -> 提取用户和帖子信息
"""

import os
import sys
import time
import json
import re
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv, dotenv_values
from pathlib import Path

# 脚本所在目录 = 项目根（fetch_twitter_data.py 与 .env 同级）
_ENV_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _ENV_ROOT / ".env"

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


def _log(msg: str) -> None:
    """进度日志打到 stderr，便于 --json 时 stdout 仅输出一行 JSON。"""
    print(msg, file=sys.stderr, flush=True)


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        token = _twitter_bearer_token()
        if not token:
            hint = f"（已查找: {_ENV_FILE}）" if _ENV_FILE.is_file() else f"（未找到文件: {_ENV_FILE}，请把 .env 放在与 fetch_twitter_data.py 同一目录）"
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


def build_users(posts_payload: Dict[str, Any], primary_topic: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """从帖子数据提取用户信息"""
    results = posts_payload.get("results", [])
    users_map: Dict[str, Dict[str, Any]] = {}

    for item in results:
        author = item.get("author", {})
        if not isinstance(author, dict):
            continue
        uid = author.get("id")
        if not uid:
            post = item.get("post", {})
            uid = post.get("author_id")
        if not uid:
            continue
        uid = str(uid)

        username = author.get("username")
        name = author.get("name")
        description = author.get("description")
        followers_count = parse_followers(author.get("public_metrics"))

        users_map[uid] = {
            "agent_id": None,
            "user_name": username,
            "name": name,
            "description": description,
            "profile": {
                "other_info": {
                    "topics": [primary_topic] if primary_topic else [],
                    "gender": None,
                    "age": None,
                    "mbti": None,
                    "country": None
                }
            },
            "recsys_type": "twitter",
            "user_type": followers_to_user_type(followers_count),
        }

    users_list = list(users_map.values())
    uid_order = list(users_map.keys())
    uid_to_agent: Dict[str, int] = {}

    for i, uid in enumerate(uid_order):
        users_list[i]["agent_id"] = i
        uid_to_agent[uid] = i

    return users_list, uid_to_agent


def strip_urls(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return URL_REGEX.sub("", text).strip()


def build_posts(posts_payload: Dict[str, Any], uid_to_agent: Dict[str, int]) -> List[Dict[str, Any]]:
    """从帖子数据提取帖子信息"""
    results = posts_payload.get("results", [])
    posts_out: List[Dict[str, Any]] = []

    for idx, item in enumerate(results):
        post = item.get("post", {}) or {}
        author = item.get("author", {}) or {}

        uid = None
        if isinstance(author, dict) and author.get("id"):
            uid = str(author["id"])
        elif post.get("author_id"):
            uid = str(post["author_id"])

        agent_id_val = uid_to_agent.get(uid)
        agent_id_str = str(agent_id_val) if agent_id_val is not None else None

        text = strip_urls(post.get("text"))
        created = parse_created_at(post.get("created_at"))
        post_user = author.get("username")

        posts_out.append({
            "post_id": idx,
            "post_user": post_user,
            "agent_id": agent_id_str,
            "content": text,
            "createdAt": created
        })

    return posts_out


def extract_texts(posts_payload: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """提取所有 post 的 text 和所有 replies 的 text"""
    results = posts_payload.get("results", [])
    posts_texts: List[str] = []
    replies_texts: List[str] = []

    for item in results:
        post = item.get("post", {})
        if isinstance(post, dict):
            text = post.get("text")
            if text:
                posts_texts.append(text)

        replies = item.get("replies", [])
        if isinstance(replies, list):
            for reply in replies:
                if isinstance(reply, dict):
                    reply_text = reply.get("text")
                    if reply_text:
                        replies_texts.append(reply_text)

    return posts_texts, replies_texts


def extract_data(posts_payload: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """提取话题、用户和帖子"""
    primary_topic = clean_query_to_topic(posts_payload.get("query", ""))

    # 提取用户
    users, uid_to_agent = build_users(posts_payload, primary_topic)

    # 提取帖子
    posts = build_posts(posts_payload, uid_to_agent)

    _log(f"[Step 3] 提取到: 话题='{primary_topic}', {len(users)} 个用户, {len(posts)} 条帖子")
    return [primary_topic], users, posts


def _normalize_fetch_opts(raw: Dict[str, Any]) -> Dict[str, Any]:
    """支持 snake_case 与 camelCase（供 HTTP / CLI JSON 传参）。"""
    out: Dict[str, Any] = {}
    if "max_trends" in raw:
        out["max_trends"] = int(raw["max_trends"])
    elif "maxTrends" in raw:
        out["max_trends"] = int(raw["maxTrends"])
    if "max_posts" in raw:
        out["max_posts"] = int(raw["max_posts"])
    elif "maxPosts" in raw:
        out["max_posts"] = int(raw["maxPosts"])
    if "max_replies_per_post" in raw:
        out["max_replies_per_post"] = int(raw["max_replies_per_post"])
    elif "maxRepliesPerPost" in raw:
        out["max_replies_per_post"] = int(raw["maxRepliesPerPost"])
    if "sort_order" in raw:
        out["sort_order"] = str(raw["sort_order"])
    elif "sortOrder" in raw:
        out["sort_order"] = str(raw["sortOrder"])
    return out


def run_fetch_pipeline(
    max_trends: Optional[int] = None,
    max_posts: Optional[int] = None,
    max_replies_per_post: Optional[int] = None,
    sort_order: Optional[str] = None,
) -> Dict[str, Any]:
    """
    执行完整采集流程，返回可 JSON 序列化的结果（供 HTTP 接口或 --json 使用）。
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
    all_users: List[Dict[str, Any]] = []
    all_posts: List[Dict[str, Any]] = []
    all_posts_texts: List[str] = []
    all_replies_texts: List[str] = []
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

        topics, users, posts = extract_data(posts_data)
        posts_texts, replies_texts = extract_texts(posts_data)

        all_topics.extend(topics)
        all_users.extend(users)
        all_posts.extend(posts)
        all_posts_texts.extend(posts_texts)
        all_replies_texts.extend(replies_texts)
        all_raw_posts.append({
            "trend_name": trend_name,
            "query": posts_data.get("query"),
            "stats": posts_data.get("stats"),
            "results_count": len(posts_data.get("results", [])),
        })

        if i < len(trends) - 1:
            time.sleep(1)

    topics_dedup = list(dict.fromkeys(all_topics))

    return {
        "topics": topics_dedup,
        "topics_document": {"twitter_trends": topics_dedup},
        "users": all_users,
        "posts": all_posts,
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
                "posts_texts": len(all_posts_texts),
                "replies_texts": len(all_replies_texts),
            },
        },
    }


# ============== 主流程 ==============
def save_json(path: str, obj: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    _log("=" * 50)
    _log("Twitter 数据采集集成脚本")
    _log(f"参数: MAX_TRENDS={MAX_TRENDS}, MAX_POSTS={MAX_POSTS}")
    _log("=" * 50)

    try:
        result = run_fetch_pipeline()
    except APIError as e:
        raise SystemExit(f"[Step 1] 获取趋势失败: {e.status_code} {e.detail}") from e
    except RuntimeError as e:
        raise SystemExit(str(e)) from e

    trends = result["meta"]["trends_processed"]
    all_topics = result["topics"]
    all_users = result["users"]
    all_posts = result["posts"]
    all_posts_texts = result["posts_texts"]
    all_replies_texts = result["replies_texts"]
    all_raw_posts = result["meta"]["trends_data"]

    timestamp = int(time.time())
    os.makedirs("output", exist_ok=True)

    topics_file = f"output/topics_result_{timestamp}.json"
    users_file = f"output/users_formatted_{timestamp}.json"
    posts_file = f"output/posts_formatted_{timestamp}.json"
    posts_texts_file = f"output/posts_texts_{timestamp}.json"
    replies_texts_file = f"output/replies_texts_{timestamp}.json"
    raw_file = f"output/raw_posts_{timestamp}.json"

    save_json(topics_file, {"topics": all_topics})
    save_json(users_file, all_users)
    save_json(posts_file, all_posts)
    save_json(posts_texts_file, {"posts_texts": all_posts_texts})
    save_json(replies_texts_file, {"replies_texts": all_replies_texts})

    save_json(raw_file, {
        "trends_processed": trends,
        "collected_at": result["meta"]["collected_at"],
        "trends_data": all_raw_posts,
    })

    _log("\n" + "=" * 50)
    _log("采集完成!")
    _log(f"- 话题文件: {topics_file}")
    _log(f"- 用户文件: {users_file}")
    _log(f"- 帖子文件: {posts_file}")
    _log(f"- 帖子文本: {posts_texts_file}")
    _log(f"- 回复文本: {replies_texts_file}")
    _log(f"- 原始摘要: {raw_file}")
    _log(
        f"统计: {len(all_topics)} 个话题, {len(all_users)} 个用户, {len(all_posts)} 条帖子, "
        f"{len(all_posts_texts)} 条帖子文本, {len(all_replies_texts)} 条回复文本"
    )
    _log("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        try:
            opts_raw: Dict[str, Any] = {}
            if len(sys.argv) > 2 and sys.argv[2].strip():
                opts_raw = json.loads(sys.argv[2])
            opts = _normalize_fetch_opts(opts_raw)
            payload = run_fetch_pipeline(**opts)
            print(json.dumps(payload, ensure_ascii=False), flush=True)
        except APIError as e:
            print(
                json.dumps({"error": e.detail, "status_code": e.status_code, "type": "APIError"}),
                flush=True,
            )
            sys.exit(1)
        except Exception as e:
            print(
                json.dumps({"error": str(e), "type": type(e).__name__}),
                flush=True,
            )
            sys.exit(1)
    else:
        main()