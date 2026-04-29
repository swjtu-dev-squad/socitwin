"""
从 backend/data/datasets/oasis_datasets.db 直接导入 Neo4j（最小：User-Topic 关联）。

节点：
- (:User {id}) 其中 id = "{platform}:{external_user_id}"
- (:Topic {id}) 其中 id = "{platform}:{topic_key}"

关系：
- (:User)-[:INTERESTED_IN {role, content_count, source_type}]->(:Topic)
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from neo4j import GraphDatabase


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


def _parse_auth() -> Tuple[str, str]:
    raw = (os.environ.get("NEO4J_AUTH") or "").strip()
    if raw and "/" in raw:
        u, p = raw.split("/", 1)
        return (u.strip() or "neo4j", p.strip())
    user = (os.environ.get("NEO4J_USER") or "neo4j").strip() or "neo4j"
    pwd = (os.environ.get("NEO4J_PASSWORD") or "").strip()
    return (user, pwd)


def _chunked(rows: List[Dict[str, Any]], n: int) -> Iterable[List[Dict[str, Any]]]:
    if n < 1:
        n = 500
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


def _ensure_constraints(tx) -> None:
    tx.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")


def _clear_graph(tx) -> None:
    tx.run("MATCH (n) WHERE n:User OR n:Topic DETACH DELETE n")


def _upsert_users(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (u:User {id: row.id})
        SET u.platform = row.platform,
            u.external_user_id = row.external_user_id,
            u.username = row.username,
            u.display_name = row.display_name,
            u.bio = row.bio,
            u.location = row.location,
            u.user_type = row.user_type
        """,
        rows=rows,
    )


def _upsert_topics(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (t:Topic {id: row.id})
        SET t.platform = row.platform,
            t.topic_key = row.topic_key,
            t.topic_label = row.topic_label,
            t.topic_type = row.topic_type,
            t.news_external_id = row.news_external_id
        """,
        rows=rows,
    )


def _upsert_user_topic_edges(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (u:User {id: row.user_id})
        MATCH (t:Topic {id: row.topic_id})
        MERGE (u)-[r:INTERESTED_IN]->(t)
        SET r.role = row.role,
            r.content_count = row.content_count,
            r.source_type = row.source_type
        """,
        rows=rows,
    )


def import_from_sqlite(
    *,
    db_path: str | Path,
    platform: str | None = None,
    clear: bool = False,
    limit_edges: int | None = None,
) -> Dict[str, Any]:
    """
    从 oasis_datasets.db 导入 Neo4j。

    Args:
        db_path: SQLite 路径（默认库：backend/data/datasets/oasis_datasets.db）
        platform: 仅导入特定 platform（如 'twitter' / 'reddit' / 'twitter_llm'），None 表示全量
        clear: 是否清空图中已有的 User/Topic（仅删这些标签）
        limit_edges: 仅用于调试，限制 user_topics 导入条数
    """
    p = Path(db_path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"SQLite 不存在: {p}")

    plat = (platform or "").strip().lower() or None

    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if plat:
            users_rows = cur.execute(
                """
                SELECT platform, external_user_id, username, display_name, bio, location, user_type
                FROM users
                WHERE lower(trim(platform)) = ?
                """,
                (plat,),
            ).fetchall()
            topics_rows = cur.execute(
                """
                SELECT platform, topic_key, topic_label, topic_type, news_external_id
                FROM topics
                WHERE lower(trim(platform)) = ?
                """,
                (plat,),
            ).fetchall()
            edges_sql = """
                SELECT platform, topic_key, external_user_id, role, content_count, type
                FROM user_topics
                WHERE lower(trim(platform)) = ?
            """
            params: Tuple[Any, ...] = (plat,)
        else:
            users_rows = cur.execute(
                "SELECT platform, external_user_id, username, display_name, bio, location, user_type FROM users"
            ).fetchall()
            topics_rows = cur.execute(
                "SELECT platform, topic_key, topic_label, topic_type, news_external_id FROM topics"
            ).fetchall()
            edges_sql = "SELECT platform, topic_key, external_user_id, role, content_count, type FROM user_topics"
            params = ()

        if limit_edges is not None:
            n = int(limit_edges)
            edges_sql += " LIMIT ?"
            params = (*params, n)

        edge_rows = cur.execute(edges_sql, params).fetchall()

        user_rows_out: List[Dict[str, Any]] = []
        for r in users_rows:
            platform_v = str(r["platform"]).strip().lower()
            ext = str(r["external_user_id"]).strip()
            if not platform_v or not ext:
                continue
            user_rows_out.append(
                {
                    "id": f"{platform_v}:{ext}",
                    "platform": platform_v,
                    "external_user_id": ext,
                    "username": r["username"],
                    "display_name": r["display_name"],
                    "bio": r["bio"],
                    "location": r["location"],
                    "user_type": r["user_type"],
                }
            )

        topic_rows_out: List[Dict[str, Any]] = []
        for r in topics_rows:
            platform_v = str(r["platform"]).strip().lower()
            tk = str(r["topic_key"]).strip()
            if not platform_v or not tk:
                continue
            topic_rows_out.append(
                {
                    "id": f"{platform_v}:{tk}",
                    "platform": platform_v,
                    "topic_key": tk,
                    "topic_label": r["topic_label"],
                    "topic_type": r["topic_type"],
                    "news_external_id": r["news_external_id"],
                }
            )

        edge_rows_out: List[Dict[str, Any]] = []
        for r in edge_rows:
            platform_v = str(r["platform"]).strip().lower()
            tk = str(r["topic_key"]).strip()
            ext = str(r["external_user_id"]).strip()
            if not platform_v or not tk or not ext:
                continue
            edge_rows_out.append(
                {
                    "user_id": f"{platform_v}:{ext}",
                    "topic_id": f"{platform_v}:{tk}",
                    "role": r["role"],
                    "content_count": int(r["content_count"] or 0),
                    "source_type": r["type"],
                }
            )
    finally:
        conn.close()

    raw_uri = (os.environ.get("NEO4J_URI") or "bolt://localhost:7687").strip()
    neo4j_uri = _neo4j_uri_for_current_platform(raw_uri)
    neo4j_db = (os.environ.get("OASIS_NEO4J_DATABASE") or "").strip() or None
    user, pwd = _parse_auth()
    if not pwd:
        raise ValueError("请设置 NEO4J_PASSWORD 或 NEO4J_AUTH（例如 neo4j/your_password）")

    driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
    session_kw: Dict[str, Any] = {"database": neo4j_db} if neo4j_db else {}
    try:
        with driver.session(**session_kw) as session:
            if clear:
                session.execute_write(_clear_graph)
            session.execute_write(_ensure_constraints)
            for batch in _chunked(user_rows_out, 800):
                session.execute_write(_upsert_users, batch)
            for batch in _chunked(topic_rows_out, 600):
                session.execute_write(_upsert_topics, batch)
            for batch in _chunked(edge_rows_out, 2000):
                session.execute_write(_upsert_user_topic_edges, batch)
    finally:
        driver.close()

    return {
        "status": "ok",
        "counts": {
            "users": len(user_rows_out),
            "topics": len(topic_rows_out),
            "user_topic_edges": len(edge_rows_out),
        },
        "platform": plat,
        "db_path": str(p),
        "neo4j_uri": neo4j_uri,
        "neo4j_db": neo4j_db,
    }

