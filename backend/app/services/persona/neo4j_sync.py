"""
将 backend/data/datasets/data 下的 users.json、topics.json、relationships.json、user_networks.json
导入 Neo4j。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase


def _load_dotenv_from_backend() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    backend_root = Path(__file__).resolve().parents[3]
    for candidate in (backend_root / ".env", Path.cwd() / ".env"):
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


def _chunked(xs: List[Dict[str, Any]], n: int) -> List[List[Dict[str, Any]]]:
    if n < 1:
        n = 500
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def _ensure_constraints(tx) -> None:
    tx.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT topic_category_name IF NOT EXISTS FOR (c:TopicCategory) REQUIRE c.name IS UNIQUE")


def _clear_graph(tx) -> None:
    tx.run("""MATCH (n) WHERE n:User OR n:Topic OR n:TopicCategory DETACH DELETE n""")


def _upsert_users(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (u:User {id: row.id})
        SET u.agent_id = row.agent_id, u.user_name = row.user_name, u.name = row.name,
            u.description = row.description, u.user_type = row.user_type, u.topic_type = row.topic_type,
            u.recsys_type = row.recsys_type, u.source = row.source, u.ingest_status = row.ingest_status,
            u.gender = row.gender, u.age = row.age, u.mbti = row.mbti, u.country = row.country
        """,
        rows=rows,
    )


def _upsert_topic_categories_and_topics(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (c:TopicCategory {name: row.category})
        MERGE (t:Topic {id: row.topic_id})
        SET t.title = row.title, t.category = row.category
        MERGE (c)-[:INCLUDES]->(t)
        """,
        rows=rows,
    )


def _upsert_interests(tx, rows: List[Dict[str, Any]]) -> None:
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


def _upsert_social_edges(tx, rows: List[Dict[str, Any]], rel_cypher: str) -> None:
    tx.run(
        f"""
        UNWIND $rows AS row
        MATCH (a:User {{id: row.source}})
        MATCH (b:User {{id: row.target}})
        {rel_cypher}
        SET r.edge_id = row.id, r.created_at = row.created_at, r.updated_at = row.updated_at, r.is_active = row.is_active
        """,
        rows=rows,
    )


def _upsert_social_generic(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (a:User {id: row.source})
        MATCH (b:User {id: row.target})
        MERGE (a)-[r:SOCIAL {rel_type: row.rel_type}]->(b)
        SET r.edge_id = row.id, r.created_at = row.created_at, r.updated_at = row.updated_at, r.is_active = row.is_active
        """,
        rows=rows,
    )


def _apply_user_network_stats(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (u:User {id: row.user_id})
        SET u.followers_count = row.followers_count, u.follows_count = row.follows_count,
            u.friends_count = row.friends_count, u.network_last_updated = row.last_updated
        """,
        rows=rows,
    )


def _build_user_rows(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in users:
        if not isinstance(u, dict):
            continue
        aid = u.get("agent_id")
        if aid is None:
            continue
        uid = f"user_{int(aid)}"
        oi = _safe_get(u, "profile", "other_info") or {}
        out.append({"id": uid, "agent_id": int(aid), "user_name": u.get("user_name"), "name": u.get("name"), "description": u.get("description"), "user_type": u.get("user_type"), "topic_type": u.get("topic_type"), "recsys_type": u.get("recsys_type"), "source": u.get("source"), "ingest_status": u.get("ingest_status"), "gender": oi.get("gender"), "age": oi.get("age"), "mbti": oi.get("mbti"), "country": oi.get("country")})
    return out


def _build_topic_rows(topics_doc: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for block in topics_doc:
        if not isinstance(block, dict):
            continue
        cat = str(block.get("category") or "").strip() or "Uncategorized"
        for title in block.get("topics") or []:
            t = str(title).strip()
            if t:
                rows.append({"category": cat, "topic_id": _topic_stable_id(t, cat), "title": t})
    return rows


def _build_interest_rows(users: List[Dict[str, Any]], topic_title_to_id: Dict[str, str]) -> List[Dict[str, Any]]:
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


def _build_relationship_rows(rels: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    follows: List[Dict[str, Any]] = []
    friends: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for e in rels:
        if not isinstance(e, dict):
            continue
        src, tgt = str(e.get("fromUserId") or "").strip(), str(e.get("toUserId") or "").strip()
        if not src or not tgt or src == tgt:
            continue
        typ = str(e.get("type") or "follow").strip().lower()
        row = {"id": e.get("id"), "source": src, "target": tgt, "created_at": e.get("createdAt"), "updated_at": e.get("updatedAt"), "is_active": bool(e.get("isActive", True))}
        if typ == "follow":
            follows.append(row)
        elif typ in ("friend", "friends"):
            friends.append(row)
        else:
            row["rel_type"] = typ
            other.append(row)
    return follows, friends, other


def _build_stats_rows(networks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for block in networks:
        if not isinstance(block, dict):
            continue
        uid = str(block.get("userId") or "").strip()
        if not uid:
            continue
        st = block.get("statistics") if isinstance(block.get("statistics"), dict) else {}
        out.append({"user_id": uid, "followers_count": st.get("followersCount"), "follows_count": st.get("followsCount"), "friends_count": st.get("friendsCount"), "last_updated": st.get("lastUpdated")})
    return out


def import_from_data_dir(data_dir: Path, clear: bool = False) -> Dict[str, Any]:
    _load_dotenv_from_backend()
    paths = {"users": data_dir / "users.json", "topics": data_dir / "topics.json", "relationships": data_dir / "relationships.json", "user_networks": data_dir / "user_networks.json"}
    for name, p in paths.items():
        if not p.is_file():
            raise ValueError(f"缺少文件 {name}: {p}")
    users = _coerce_users(_load_json(paths["users"]))
    topics_blocks = _coerce_topics(_load_json(paths["topics"]))
    rels_list = _load_json(paths["relationships"]) if isinstance(_load_json(paths["relationships"]), list) else []
    networks_list = _load_json(paths["user_networks"]) if isinstance(_load_json(paths["user_networks"]), list) else []
    user_rows = _build_user_rows(users)
    topic_rows = _build_topic_rows(topics_blocks)
    topic_title_to_id: Dict[str, str] = {}
    for r in topic_rows:
        topic_title_to_id.setdefault(r["title"], r["topic_id"])
    interest_rows = _build_interest_rows(users, topic_title_to_id)
    follows, friends, other_rels = _build_relationship_rows(rels_list)
    stats_rows = _build_stats_rows(networks_list)
    raw_uri = (os.environ.get("NEO4J_URI") or "bolt://localhost:7687").strip()
    neo4j_uri = _neo4j_uri_for_current_platform(raw_uri)
    neo4j_db = (os.environ.get("OASIS_NEO4J_DATABASE") or "").strip() or None
    user, pwd = _parse_auth()
    if not pwd:
        raise ValueError("请设置 NEO4J_PASSWORD 或 NEO4J_AUTH")
    driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
    session_kw: Dict[str, Any] = {"database": neo4j_db} if neo4j_db else {}
    try:
        with driver.session(**session_kw) as session:
            if clear:
                session.execute_write(_clear_graph)
            session.execute_write(_ensure_constraints)
            for batch in _chunked(user_rows, 400):
                session.execute_write(_upsert_users, batch)
            for batch in _chunked(topic_rows, 300):
                session.execute_write(_upsert_topic_categories_and_topics, batch)
            for batch in _chunked(interest_rows, 500):
                session.execute_write(_upsert_interests, batch)
            for batch in _chunked(follows, 2000):
                session.execute_write(_upsert_social_edges, batch, "MERGE (a)-[r:FOLLOWS]->(b)")
            for batch in _chunked(friends, 2000):
                session.execute_write(_upsert_social_edges, batch, "MERGE (a)-[r:FRIENDS_WITH]->(b)")
            for batch in _chunked(other_rels, 2000):
                session.execute_write(_upsert_social_generic, batch)
            for batch in _chunked(stats_rows, 500):
                session.execute_write(_apply_user_network_stats, batch)
    finally:
        driver.close()
    return {"status": "ok", "counts": {"users": len(user_rows), "topic_nodes": len(topic_rows), "interested_in_edges": len(interest_rows), "follows": len(follows), "friends": len(friends), "other_social": len(other_rels), "user_network_stats": len(stats_rows)}}

