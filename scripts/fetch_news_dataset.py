#!/usr/bin/env python3
"""
从 X News → 新闻详情中的 post_id → 帖子 / 回复 → 用户，组装为与 twitter 抓取一致的 data 结构。
`users` 仅含主帖作者（按 X user id 去重）；回复正文仍在 `replies_texts`，回复账号不进 `users`。
每条 `posts` 的 `post_id` 为 X 帖子雪花 id（不额外增加帖字段）；新闻与帖对应见 `data.news_posts[].post_ids`。

API 参考（与官方文档一致）：
- Search News: https://docs.x.com/x-api/news/search-news
- Get News by ID: https://docs.x.com/x-api/news/get-news-stories-by-id
- Get Post by ID: https://docs.x.com/enterprise-api/posts/get-post-by-id （即 GET /2/tweets/{id}）
- Get User by ID: https://docs.x.com/x-api/users/get-user-by-id （批量用 GET /2/users）

环境变量：TWITTER_BEARER_TOKEN（项目根 .env 会自动加载）

默认会把完整结果写入项目下 `artifacts/news_dataset_<UTC时间>.json`，并在终端打印一行摘要；
仅需要打印到控制台时用 `--stdout-only`；指定路径用 `-o path`。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv, dotenv_values

warnings.filterwarnings("ignore", message=".*doesn't match a supported version", category=Warning)

import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=True)

API_BASE = "https://api.x.com/2"

# 政治 / 经济 / 社会：分三次搜索，每次 max_results=10
NEWS_AXIS_QUERIES: List[Tuple[str, str]] = [
    ("politics", "politics government election policy legislature diplomacy"),
    ("economy", "economy finance business market inflation trade employment"),
    ("society", "society social public health education justice immigration community"),
]

TWEET_FIELDS = [
    "id",
    "text",
    "author_id",
    "in_reply_to_user_id",
    "conversation_id",
    "created_at",
    "referenced_tweets",
    "lang",
]
USER_FIELDS = [
    "id",
    "name",
    "username",
    "location",
    "description",
    "entities",
    "created_at",
    "public_metrics",
    "verified",
    "verified_followers_count",
    "protected",
    "profile_image_url",
    "url",
]
EXPANSIONS_TWEET = "author_id,referenced_tweets.id"


def _bearer() -> str:
    if _ENV_FILE.is_file():
        t = (dotenv_values(_ENV_FILE).get("TWITTER_BEARER_TOKEN") or "").strip()
        if t:
            return t
    return (os.getenv("TWITTER_BEARER_TOKEN") or "").strip()


def _session() -> requests.Session:
    tok = _bearer()
    if not tok:
        raise RuntimeError("缺少 TWITTER_BEARER_TOKEN（请在项目根 .env 或环境中配置）")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Accept": "application/json"})
    return s


def _get(sess: requests.Session, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = sess.get(url, params=params or {}, timeout=90)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} {url}: {r.text[:800]}")
    return r.json()


def _news_id(item: Dict[str, Any]) -> str:
    # news.fields 不允许包含 rest_id；官方允许字段含 id，见错误提示中的枚举
    return str(item.get("id") or item.get("rest_id") or "").strip()


def _is_retweet(tweet: Dict[str, Any]) -> bool:
    refs = tweet.get("referenced_tweets")
    if isinstance(refs, list):
        for ref in refs:
            if isinstance(ref, dict) and ref.get("type") == "retweeted":
                return True
    text = (tweet.get("text") or "").lstrip()
    if text.startswith("RT @"):
        return True
    return False


def _fmt_created_at(raw: Optional[str]) -> str:
    if raw and isinstance(raw, str):
        return raw
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")


def search_news(sess: requests.Session, query: str, max_results: int, max_age_hours: int) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/news/search"
    params = {
        "query": query,
        "max_results": max(1, min(100, max_results)),
        "max_age_hours": max(1, min(720, max_age_hours)),
        "news.fields": "id,name,summary,category",
    }
    data = _get(sess, url, params=params)
    rows = data.get("data")
    if not isinstance(rows, list):
        return []
    return [x for x in rows if isinstance(x, dict)]


def get_news_by_id(sess: requests.Session, news_id: str) -> Dict[str, Any]:
    url = f"{API_BASE}/news/{news_id}"
    params = {"news.fields": "id,name,cluster_posts_results,summary,category"}
    data = _get(sess, url, params=params)
    d = data.get("data")
    if not isinstance(d, dict):
        raise RuntimeError(f"news/{news_id} 无 data")
    return d


def get_tweets_batch(sess: requests.Session, ids: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    if not ids:
        return [], {}
    url = f"{API_BASE}/tweets"
    chunk: List[Dict[str, Any]] = []
    users: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(ids), 100):
        part = ids[i : i + 100]
        params = {
            "ids": ",".join(part),
            "tweet.fields": ",".join(TWEET_FIELDS),
            "expansions": EXPANSIONS_TWEET,
            "user.fields": ",".join(USER_FIELDS),
        }
        data = _get(sess, url, params=params)
        for t in data.get("data") or []:
            if isinstance(t, dict):
                chunk.append(t)
        inc = data.get("includes") or {}
        for u in inc.get("users") or []:
            if isinstance(u, dict) and u.get("id"):
                users[str(u["id"])] = u
        time.sleep(0.05)
    return chunk, users


def search_recent_replies(sess: requests.Session, root_tweet_id: str, max_results: int) -> List[Dict[str, Any]]:
    """GET /2/tweets/search/recent — 用 conversation_id 拉线程内帖子，过滤掉根帖，最多 max_results 条回复。"""
    url = f"{API_BASE}/tweets/search/recent"
    q = f"conversation_id:{root_tweet_id} -is:retweet"
    params = {
        "query": q,
        "max_results": min(100, max(10, max_results + 5)),
        "tweet.fields": "id,text,author_id,created_at,conversation_id,referenced_tweets",
    }
    try:
        data = _get(sess, url, params=params)
    except RuntimeError:
        return []
    out: List[Dict[str, Any]] = []
    for t in data.get("data") or []:
        if not isinstance(t, dict):
            continue
        if str(t.get("id")) == str(root_tweet_id):
            continue
        if _is_retweet(t):
            continue
        out.append(t)
        if len(out) >= max_results:
            break
    time.sleep(0.12)
    return out


def get_users_batch(sess: requests.Session, user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not user_ids:
        return {}
    url = f"{API_BASE}/users"
    users: Dict[str, Dict[str, Any]] = {}
    uniq = list(dict.fromkeys(user_ids))
    for i in range(0, len(uniq), 100):
        part = uniq[i : i + 100]
        params = {"ids": ",".join(part), "user.fields": ",".join(USER_FIELDS)}
        data = _get(sess, url, params=params)
        for u in data.get("data") or []:
            if isinstance(u, dict) and u.get("id"):
                users[str(u["id"])] = u
        time.sleep(0.05)
    return users


def _followers(u: Dict[str, Any]) -> int:
    pm = u.get("public_metrics")
    if isinstance(pm, dict):
        fc = pm.get("followers_count")
        if isinstance(fc, int):
            return fc
    return 0


def run_pipeline(
    *,
    max_age_hours: int,
    max_replies_per_post: int,
) -> Dict[str, Any]:
    sess = _session()

    # --- Step 1: 三次新闻搜索，每类 10 条 ---
    news_rows: List[Dict[str, Any]] = []
    for axis, q in NEWS_AXIS_QUERIES:
        items = search_news(sess, q, max_results=4, max_age_hours=max_age_hours)
        for it in items:
            nid = _news_id(it)
            name = str(it.get("name") or "").strip()
            if nid and name:
                news_rows.append({"news_id": nid, "name": name, "axis": axis, "search_query": q})
        time.sleep(0.15)

    # 同一新闻可能出现在多次搜索中，按 news_id 去重
    seen_nid: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for row in news_rows:
        k = row["news_id"]
        if k in seen_nid:
            continue
        seen_nid.add(k)
        deduped.append(row)
    news_rows = deduped

    # --- Step 2: 每条新闻拉 cluster_posts_results，收集 post_id 去重 ---
    post_to_news_names: Dict[str, Set[str]] = {}
    # 同一帖可挂在多条新闻 cluster 下：按 news_id 去重保留 axis / 标题
    post_to_news_links: Dict[str, List[Dict[str, str]]] = {}
    post_order: List[str] = []

    for row in news_rows:
        nid = row["news_id"]
        nm = row["name"]
        axis = row["axis"]
        try:
            detail = get_news_by_id(sess, nid)
        except Exception:
            time.sleep(0.2)
            continue
        cpr = detail.get("cluster_posts_results")
        if not isinstance(cpr, list):
            time.sleep(0.1)
            continue
        for cell in cpr:
            if not isinstance(cell, dict):
                continue
            pid = str(cell.get("post_id") or "").strip()
            if not pid:
                continue
            if pid not in post_to_news_names:
                post_to_news_names[pid] = set()
                post_to_news_links[pid] = []
                post_order.append(pid)
            post_to_news_names[pid].add(nm)
            link_row = post_to_news_links[pid]
            if not any(x.get("news_id") == nid for x in link_row):
                link_row.append({"news_id": nid, "trend_name": nm, "axis": axis})
        time.sleep(0.12)

    if not post_order:
        return {
            "status": "ok",
            "data": {
                "topics": [],
                "topics_document": {"twitter_trends": []},
                "news_posts": [],
                "users": [],
                "posts": [],
                "posts_texts": [],
                "replies_texts": [],
                "meta": {
                    "trends_processed": [],
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "trends_data": [],
                    "counts": {
                        "topics": 0,
                        "news_posts": 0,
                        "users": 0,
                        "posts": 0,
                        "posts_texts": 0,
                        "replies_texts": 0,
                    },
                },
            },
        }

    # --- Step 3: 批量拉帖子，跳过转推 ---
    tweets, tw_users = get_tweets_batch(sess, post_order)
    tid_to_tweet = {str(t.get("id")): t for t in tweets if t.get("id")}

    kept_posts: List[Dict[str, Any]] = []
    for pid in post_order:
        t = tid_to_tweet.get(pid)
        if not t:
            continue
        if _is_retweet(t):
            continue
        kept_posts.append(
            {
                "tweet": t,
                "post_id_str": pid,
                "news_names": sorted(post_to_news_names.get(pid, set())),
            }
        )

    # --- Step 3b: 每条帖子最多 max_replies_per_post 条回复（纯文本收集）---
    replies_texts: List[str] = []
    root_to_reply_rows: Dict[str, List[Dict[str, Any]]] = {}

    for kp in kept_posts:
        root_id = str(kp["tweet"].get("id"))
        rel = search_recent_replies(sess, root_id, max_results=max_replies_per_post)
        root_to_reply_rows[root_id] = rel
        for rt in rel:
            txt = (rt.get("text") or "").strip()
            if txt:
                replies_texts.append(txt)

    # --- Step 4: 仅主帖作者（按 author_id 去重），不包含回复用户 ---
    ordered_author_ids: List[str] = []
    seen_u: Set[str] = set()

    def _add_author(aid: str) -> None:
        aid = (aid or "").strip()
        if not aid or aid in seen_u:
            return
        seen_u.add(aid)
        ordered_author_ids.append(aid)

    for kp in kept_posts:
        _add_author(str(kp["tweet"].get("author_id") or ""))

    user_map = get_users_batch(sess, ordered_author_ids)
    for uid, u in tw_users.items():
        if uid not in user_map:
            user_map[uid] = u

    # --- 用户 topics：仅主帖作者，来自其帖关联的新闻 name ---
    author_to_news: Dict[str, Set[str]] = {}

    for kp in kept_posts:
        aid = str(kp["tweet"].get("author_id") or "")
        if aid:
            author_to_news.setdefault(aid, set())
            for nm in kp["news_names"]:
                author_to_news[aid].add(nm)

    # topics = 新闻 name 列表（顺序：按三轴搜索出现顺序去重）
    topics_ordered: List[str] = []
    seen_n: Set[str] = set()
    for row in news_rows:
        n = row["name"]
        if n and n not in seen_n:
            seen_n.add(n)
            topics_ordered.append(n)

    users_out: List[Dict[str, Any]] = []
    agent_by_uid: Dict[str, int] = {}
    for i, uid in enumerate(ordered_author_ids):
        agent_by_uid[uid] = i
        u = user_map.get(uid) or {}
        uname = str(u.get("username") or "").strip() or str(uid)
        dname = str(u.get("name") or "").strip() or uname
        desc = str(u.get("description") or "").strip()
        topics_u = sorted(author_to_news.get(uid, set()))
        utype = "kol" if _followers(u) > 20000 else "normal"
        users_out.append(
            {
                "agent_id": i,
                "user_name": uname,
                "name": dname,
                "description": desc,
                "profile": {
                    "other_info": {
                        "topics": topics_u,
                        "gender": None,
                        "age": None,
                        "mbti": None,
                        "country": None,
                    }
                },
                "recsys_type": "twitter",
                "user_type": utype,
            }
        )

    kept_pid_set = {kp["post_id_str"] for kp in kept_posts}

    posts_out: List[Dict[str, Any]] = []
    posts_texts: List[str] = []
    for kp in kept_posts:
        t = kp["tweet"]
        aid = str(t.get("author_id") or "")
        ag = agent_by_uid.get(aid, 0)
        u = user_map.get(aid) or {}
        post_user = str(u.get("username") or "").strip() or str(u.get("name") or "").strip() or aid
        content = str(t.get("text") or "")
        posts_out.append(
            {
                "post_id": kp["post_id_str"],
                "post_user": post_user,
                "agent_id": str(ag),
                "content": content,
                "createdAt": _fmt_created_at(str(t.get("created_at") or "")),
            }
        )
        posts_texts.append(content)

    # 每条新闻 → 本批保留的主帖（X 帖 id，与 posts[].post_id 一致）
    news_posts_out: List[Dict[str, Any]] = []
    for row in news_rows:
        nid = row["news_id"]
        tw_candidates: List[str] = []
        for pid, links in post_to_news_links.items():
            if any(ln.get("news_id") == nid for ln in links):
                tw_candidates.append(pid)
        tw_kept = sorted((p for p in set(tw_candidates) if p in kept_pid_set), key=lambda x: int(x) if x.isdigit() else 0)
        news_posts_out.append(
            {
                "news_id": nid,
                "trend_name": row["name"],
                "axis": row["axis"],
                "query": row["search_query"],
                "post_ids": tw_kept,
            }
        )

    # meta.trends_data：每条新闻 story 的统计
    trends_data: List[Dict[str, Any]] = []
    for row in news_rows:
        nm = row["name"]
        nid = row["news_id"]
        axis = row["axis"]
        pids_for_news: Set[str] = set()
        for pid, nms in post_to_news_names.items():
            if nm in nms:
                pids_for_news.add(pid)
        authors: Set[str] = set()
        post_cnt = 0
        for kp in kept_posts:
            if kp["post_id_str"] not in pids_for_news:
                continue
            post_cnt += 1
            authors.add(str(kp["tweet"].get("author_id") or ""))
        trends_data.append(
            {
                "trend_name": nm,
                "news_id": nid,
                "axis": axis,
                "query": row["search_query"],
                "stats": {"posts": post_cnt, "unique_users": len(authors - {""})},
                "results_count": post_cnt,
            }
        )

    collected = datetime.now(timezone.utc).isoformat()
    counts = {
        "topics": len(topics_ordered),
        "news_posts": len(news_posts_out),
        "users": len(users_out),
        "posts": len(posts_out),
        "posts_texts": len(posts_texts),
        "replies_texts": len(replies_texts),
    }

    return {
        "status": "ok",
        "data": {
            "topics": topics_ordered,
            "topics_document": {"twitter_trends": list(topics_ordered)},
            "news_posts": news_posts_out,
            "users": users_out,
            "posts": posts_out,
            "posts_texts": posts_texts,
            "replies_texts": replies_texts,
            "meta": {
                "trends_processed": list(topics_ordered),
                "collected_at": collected,
                "trends_data": trends_data,
                "counts": counts,
            },
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="News → posts → users 组装为 dataset 形态 JSON")
    p.add_argument("--max-age-hours", type=int, default=168, help="news/search 的 max_age_hours（1–720）")
    p.add_argument("--max-replies-per-post", type=int, default=20, help="每条帖子最多拉取回复条数")
    p.add_argument(
        "-o",
        "--output",
        default="",
        metavar="PATH",
        help="写入 JSON 的路径；省略则使用 artifacts/news_dataset_<UTC时间>.json",
    )
    p.add_argument(
        "--stdout-only",
        action="store_true",
        help="不写文件，把完整 JSON 打到 stdout（内容大时终端可能截断）",
    )
    p.add_argument("--compact", action="store_true", help="写入文件时用紧凑单行 JSON")
    args = p.parse_args()
    try:
        payload = run_pipeline(max_age_hours=args.max_age_hours, max_replies_per_post=args.max_replies_per_post)
        if args.compact:
            text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        else:
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.stdout_only:
            print(text, flush=True)
            return 0
        out = (args.output or "").strip()
        if not out:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            out = f"artifacts/news_dataset_{ts}.json"
        path = Path(out).expanduser()
        if not path.is_absolute():
            path = (_PROJECT_ROOT / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(
            json.dumps(
                {"status": "ok", "output_file": str(path), "bytes": path.stat().st_size},
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e), "type": type(e).__name__}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
