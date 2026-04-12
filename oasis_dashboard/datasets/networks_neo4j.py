#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将本地 datasets/data 下的 users.json、topics.json、relationships.json、
user_networks.json 导入 Neo4j，形成可查询的知识图谱。

图模型（概要）：
  - (:User {id: "user_0", ...})  — 与 relationships 中的 fromUserId/toUserId 对齐
  - (:TopicCategory {name}) -[:INCLUDES]-> (:Topic {id, title, ...})
  - (:User)-[:INTERESTED_IN]->(:Topic)  — 来自用户 profile 内的话题列表（标题与 Topic.title 一致则连边）
  - (:User)-[:FOLLOWS|:FRIENDS_WITH|:SOCIAL {rel_type}]->(:User)  — 来自 relationships.json
  - user_networks 中的 statistics 写回对应 User 节点属性

依赖：
  pip install "neo4j>=5"
  可选 pip install "python-dotenv>=1" — 安装后会在非 dry-run 时自动加载 oasis-dashboard/.env（或当前工作目录 .env）

环境变量（与 neo4j_import_worker 一致；也可写在项目根 .env 中）：
  NEO4J_URI        默认 bolt://localhost:7687
  NEO4J_USER       默认 neo4j
  NEO4J_PASSWORD   或 NEO4J_AUTH=neo4j/password
  OASIS_NEO4J_DATABASE  可选，多库时指定
  NEO4J_URI_WSL_FIX   默认 1：在 WSL 内运行时若 URI 含 127.0.0.1/localhost，则自动改为宿主机 IP（连 Windows 上的 Neo4j Desktop）。Neo4j 若装在 WSL 本机则设为 0。

用法：
  python networks_neo4j.py
  python networks_neo4j.py --dry-run
  python networks_neo4j.py --clear   # 先删除本脚本创建的 User/Topic/TopicCategory 再导入
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None  # type: ignore


def _load_dotenv_from_project() -> None:
    """加载项目根或当前目录的 .env；已存在的环境变量不被覆盖（override=False）。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # networks_neo4j.py 位于 oasis-dashboard/oasis_dashboard/datasets/
    project_root = Path(__file__).resolve().parent.parent.parent
    for candidate in (project_root / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


def _parse_auth() -> Tuple[str, str]:
    raw = (os.environ.get("NEO4J_AUTH") or "").strip()
    if raw and "/" in raw:
        u, p = raw.split("/", 1)
        return (u.strip() or "neo4j", p.strip())
    user = (os.environ.get("NEO4J_USER") or "neo4j").strip() or "neo4j"
    pwd = (os.environ.get("NEO4J_PASSWORD") or "").strip()
    return (user, pwd)


def _running_under_wsl() -> bool:
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _windows_host_ip_from_wsl() -> Optional[str]:
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("nameserver "):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[1].strip()
                        if ip and ip != "127.0.0.1":
                            return ip
    except OSError:
        return None
    return None


def _neo4j_uri_for_current_platform(uri: str) -> str:
    """
    WSL 内运行时：Neo4j Desktop 若在 Windows 上监听 127.0.0.1:7687，Linux 侧访问 127.0.0.1
    连不到该服务。将 bolt/neo4j URL 中的 127.0.0.1 或 localhost 替换为 /etc/resolv.conf 中的宿主机 IP。
    若 Neo4j 实际跑在 WSL 本机，请设置环境变量 NEO4J_URI_WSL_FIX=0 关闭此逻辑。
    """
    if os.environ.get("NEO4J_URI_WSL_FIX", "1").strip() == "0":
        return uri
    if not _running_under_wsl():
        return uri
    host = _windows_host_ip_from_wsl()
    if not host:
        return uri
    u = uri.strip()
    if "127.0.0.1" in u:
        return u.replace("127.0.0.1", host)
    if re.search(r"(?i)localhost", u):
        return re.sub(r"(?i)localhost", host, u, count=1)
    return u


def _datasets_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def _topic_stable_id(title: str, category: str = "") -> str:
    raw = f"{category}\0{title.strip()}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:28]
    return f"topic_{h}"


def _safe_get(d: Any, *path: str) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _coerce_users(doc: Any) -> List[Dict[str, Any]]:
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and isinstance(doc.get("data"), list):
        return doc["data"]
    return []


def _coerce_topics(doc: Any) -> List[Dict[str, Any]]:
    if isinstance(doc, dict) and isinstance(doc.get("data"), list):
        return doc["data"]
    return []


def chunked(xs: List[Dict[str, Any]], n: int) -> List[List[Dict[str, Any]]]:
    if n < 1:
        n = 500
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def ensure_constraints(tx) -> None:
    tx.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")
    tx.run(
        "CREATE CONSTRAINT topic_category_name IF NOT EXISTS FOR (c:TopicCategory) REQUIRE c.name IS UNIQUE"
    )


def clear_graph(tx) -> None:
    tx.run(
        """
        MATCH (n)
        WHERE n:User OR n:Topic OR n:TopicCategory
        DETACH DELETE n
        """
    )


def upsert_users(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (u:User {id: row.id})
        SET u.agent_id = row.agent_id,
            u.user_name = row.user_name,
            u.name = row.name,
            u.description = row.description,
            u.user_type = row.user_type,
            u.topic_type = row.topic_type,
            u.recsys_type = row.recsys_type,
            u.source = row.source,
            u.ingest_status = row.ingest_status,
            u.gender = row.gender,
            u.age = row.age,
            u.mbti = row.mbti,
            u.country = row.country
        """,
        rows=rows,
    )


def upsert_topic_categories_and_topics(tx, rows: List[Dict[str, Any]]) -> None:
    """rows: category, topic_id, title"""
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (c:TopicCategory {name: row.category})
        MERGE (t:Topic {id: row.topic_id})
        SET t.title = row.title,
            t.category = row.category
        MERGE (c)-[:INCLUDES]->(t)
        """,
        rows=rows,
    )


def upsert_interests(tx, rows: List[Dict[str, Any]]) -> None:
    """rows: user_id, topic_id"""
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (u:User {id: row.user_id})
        MATCH (t:Topic {id: row.topic_id})
        MERGE (u)-[r:INTERESTED_IN]->(t)
        SET r.source = 'users.profile'
        """,
        rows=rows,
    )


def upsert_social_edges(tx, rows: List[Dict[str, Any]], rel_cypher: str) -> None:
    """
    rel_cypher 须为固定片段之一（防注入，仅由本脚本传入）：
      MERGE (a)-[r:FOLLOWS]->(b)  或  MERGE (a)-[r:FRIENDS_WITH]->(b)
    """
    allowed = {
        "MERGE (a)-[r:FOLLOWS]->(b)",
        "MERGE (a)-[r:FRIENDS_WITH]->(b)",
    }
    if rel_cypher not in allowed:
        raise ValueError("invalid rel_cypher for upsert_social_edges")
    tx.run(
        f"""
        UNWIND $rows AS row
        MATCH (a:User {{id: row.source}})
        MATCH (b:User {{id: row.target}})
        {rel_cypher}
        SET r.edge_id = row.id,
            r.created_at = row.created_at,
            r.updated_at = row.updated_at,
            r.is_active = row.is_active
        """,
        rows=rows,
    )


def upsert_social_generic(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (a:User {id: row.source})
        MATCH (b:User {id: row.target})
        MERGE (a)-[r:SOCIAL {rel_type: row.rel_type}]->(b)
        SET r.edge_id = row.id,
            r.created_at = row.created_at,
            r.updated_at = row.updated_at,
            r.is_active = row.is_active
        """,
        rows=rows,
    )


def apply_user_network_stats(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (u:User {id: row.user_id})
        SET u.followers_count = row.followers_count,
            u.follows_count = row.follows_count,
            u.friends_count = row.friends_count,
            u.network_last_updated = row.last_updated
        """,
        rows=rows,
    )


def build_user_rows(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in users:
        if not isinstance(u, dict):
            continue
        aid = u.get("agent_id")
        if aid is None:
            continue
        uid = f"user_{int(aid)}"
        oi = _safe_get(u, "profile", "other_info") or {}
        out.append(
            {
                "id": uid,
                "agent_id": int(aid),
                "user_name": u.get("user_name"),
                "name": u.get("name"),
                "description": u.get("description"),
                "user_type": u.get("user_type"),
                "topic_type": u.get("topic_type"),
                "recsys_type": u.get("recsys_type"),
                "source": u.get("source"),
                "ingest_status": u.get("ingest_status"),
                "gender": oi.get("gender"),
                "age": oi.get("age"),
                "mbti": oi.get("mbti"),
                "country": oi.get("country"),
            }
        )
    return out


def build_topic_rows(topics_doc: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for block in topics_doc:
        if not isinstance(block, dict):
            continue
        cat = str(block.get("category") or "").strip() or "Uncategorized"
        for title in block.get("topics") or []:
            t = str(title).strip()
            if not t:
                continue
            tid = _topic_stable_id(t, cat)
            rows.append({"category": cat, "topic_id": tid, "title": t})
    return rows


def build_interest_rows(users: List[Dict[str, Any]], topic_title_to_id: Dict[str, str]) -> List[Dict[str, Any]]:
    """用话题标题精确匹配 topics.json 展开得到的 Topic（同一标题多分类时取首次出现的 id）。"""
    rows: List[Dict[str, Any]] = []
    for u in users:
        if not isinstance(u, dict):
            continue
        aid = u.get("agent_id")
        if aid is None:
            continue
        uid = f"user_{int(aid)}"
        oi = _safe_get(u, "profile", "other_info") or {}
        topics = oi.get("topics")
        if not isinstance(topics, list):
            continue
        for raw in topics:
            title = str(raw).strip()
            tid = topic_title_to_id.get(title)
            if tid:
                rows.append({"user_id": uid, "topic_id": tid})
    return rows


def build_relationship_rows(rels: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    follows: List[Dict[str, Any]] = []
    friends: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for e in rels:
        if not isinstance(e, dict):
            continue
        src = str(e.get("fromUserId") or "").strip()
        tgt = str(e.get("toUserId") or "").strip()
        if not src or not tgt or src == tgt:
            continue
        typ = str(e.get("type") or "follow").strip().lower()
        row = {
            "id": e.get("id"),
            "source": src,
            "target": tgt,
            "created_at": e.get("createdAt"),
            "updated_at": e.get("updatedAt"),
            "is_active": bool(e.get("isActive", True)),
        }
        if typ == "follow":
            follows.append(row)
        elif typ in ("friend", "friends"):
            friends.append(row)
        else:
            row["rel_type"] = typ
            other.append(row)
    return follows, friends, other


def build_stats_rows(networks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for block in networks:
        if not isinstance(block, dict):
            continue
        uid = str(block.get("userId") or "").strip()
        if not uid:
            continue
        st = block.get("statistics") or {}
        if not isinstance(st, dict):
            st = {}
        out.append(
            {
                "user_id": uid,
                "followers_count": st.get("followersCount"),
                "follows_count": st.get("followsCount"),
                "friends_count": st.get("friendsCount"),
                "last_updated": st.get("lastUpdated"),
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Import local social JSON files into Neo4j.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="含四个 json 的目录，默认为本脚本同级的 data/",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印统计，不连接 Neo4j")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前删除所有 User、Topic、TopicCategory 节点（慎用）",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve() if args.data_dir else _datasets_data_dir()
    paths = {
        "users": data_dir / "users.json",
        "topics": data_dir / "topics.json",
        "relationships": data_dir / "relationships.json",
        "user_networks": data_dir / "user_networks.json",
    }
    for name, p in paths.items():
        if not p.is_file():
            print(f"错误: 缺少文件 {name}: {p}", file=sys.stderr)
            return 1

    users = _coerce_users(_load_json(paths["users"]))
    topics_blocks = _coerce_topics(_load_json(paths["topics"]))
    rels_raw = _load_json(paths["relationships"])
    networks_raw = _load_json(paths["user_networks"])

    rels_list = rels_raw if isinstance(rels_raw, list) else []
    networks_list = networks_raw if isinstance(networks_raw, list) else []

    user_rows = build_user_rows(users)
    topic_rows = build_topic_rows(topics_blocks)
    topic_title_to_id: Dict[str, str] = {}
    for r in topic_rows:
        topic_title_to_id.setdefault(r["title"], r["topic_id"])
    interest_rows = build_interest_rows(users, topic_title_to_id)
    follows, friends, other_rels = build_relationship_rows(rels_list)
    stats_rows = build_stats_rows(networks_list)

    print(
        json.dumps(
            {
                "data_dir": str(data_dir),
                "users": len(user_rows),
                "topic_nodes": len(topic_rows),
                "interested_in_edges": len(interest_rows),
                "follows": len(follows),
                "friends": len(friends),
                "other_social": len(other_rels),
                "user_network_stats": len(stats_rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.dry_run:
        return 0

    _load_dotenv_from_project()

    if GraphDatabase is None:
        print("错误: 未安装 neo4j 驱动。请执行: pip install 'neo4j>=5'", file=sys.stderr)
        return 1

    raw_uri = (os.environ.get("NEO4J_URI") or "bolt://localhost:7687").strip()
    neo4j_uri = _neo4j_uri_for_current_platform(raw_uri)
    if neo4j_uri != raw_uri:
        print(f"提示: 检测到 WSL，已将 NEO4J_URI 从 {raw_uri!r} 调整为 {neo4j_uri!r} 以连接 Windows 上的 Neo4j。", file=sys.stderr)
    neo4j_db = (os.environ.get("OASIS_NEO4J_DATABASE") or "").strip() or None
    user, pwd = _parse_auth()
    if not pwd:
        print("错误: 请设置 NEO4J_PASSWORD 或 NEO4J_AUTH", file=sys.stderr)
        return 1

    driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
    session_kw: Dict[str, Any] = {"database": neo4j_db} if neo4j_db else {}

    try:
        with driver.session(**session_kw) as session:
            if args.clear:
                session.execute_write(clear_graph)
            session.execute_write(ensure_constraints)
            for batch in chunked(user_rows, 400):
                session.execute_write(upsert_users, batch)
            for batch in chunked(topic_rows, 300):
                session.execute_write(upsert_topic_categories_and_topics, batch)
            for batch in chunked(interest_rows, 500):
                session.execute_write(upsert_interests, batch)
            for batch in chunked(follows, 2000):
                session.execute_write(
                    upsert_social_edges,
                    batch,
                    "MERGE (a)-[r:FOLLOWS]->(b)",
                )
            for batch in chunked(friends, 2000):
                session.execute_write(
                    upsert_social_edges,
                    batch,
                    "MERGE (a)-[r:FRIENDS_WITH]->(b)",
                )
            for batch in chunked(other_rels, 2000):
                session.execute_write(upsert_social_generic, batch)
            for batch in chunked(stats_rows, 500):
                session.execute_write(apply_user_network_stats, batch)
    finally:
        driver.close()

    print("导入完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
