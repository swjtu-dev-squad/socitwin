"""
stdin: JSON
  generation_id: str
  dataset_id: str
  agents: list[dict]   # GeneratedAgentDocument[]
  graph: dict          # GeneratedGraphDocument

env:
  NEO4J_URI        default bolt://localhost:7687
  NEO4J_USER       default neo4j
  NEO4J_PASSWORD   or NEO4J_AUTH=neo4j/password
  OASIS_NEO4J_DATABASE optional (neo4j multi-db)

stdout: single-line JSON
  { "status": "ok", "counts": {...} } | { "status": "error", "error": "...", "type": "neo4j_import_worker" }
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Tuple

from neo4j import GraphDatabase


def _parse_auth() -> Tuple[str, str]:
    raw = (os.environ.get("NEO4J_AUTH") or "").strip()
    if raw and "/" in raw:
        u, p = raw.split("/", 1)
        return (u.strip() or "neo4j", p.strip())
    user = (os.environ.get("NEO4J_USER") or "neo4j").strip() or "neo4j"
    pwd = (os.environ.get("NEO4J_PASSWORD") or "").strip()
    return (user, pwd)


def _json_out(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), flush=True)


def _safe_get(d: Dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def ensure_constraints(tx) -> None:
    tx.run("CREATE CONSTRAINT persona_id IF NOT EXISTS FOR (p:Persona) REQUIRE p.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")


def upsert_personas(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (p:Persona {id: row.id})
        SET p.generation_id = row.generation_id,
            p.dataset_id = row.dataset_id,
            p.algorithm = row.algorithm,
            p.generated_agent_id = row.generated_agent_id,
            p.source_user_key = row.source_user_key,
            p.user_name = row.user_name,
            p.name = row.name,
            p.description = row.description,
            p.bio = row.bio,
            p.interests = row.interests,
            p.user_type = row.user_type,
            p.recsys_type = row.recsys_type,
            p.gender = row.gender,
            p.age = row.age,
            p.mbti = row.mbti,
            p.country = row.country,
            p.created_at = row.created_at
        """,
        rows=rows,
    )


def upsert_topics(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (t:Topic {id: row.id})
        SET t.name = row.name,
            t.heat = row.heat,
            t.source = row.source,
            t.generation_id = row.generation_id,
            t.dataset_id = row.dataset_id
        """,
        rows=rows,
    )


def upsert_topic_links(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (p:Persona {id: row.source})
        MATCH (t:Topic {id: row.target})
        MERGE (p)-[r:INTERESTED_IN]->(t)
        SET r.edge_id = row.id,
            r.generation_id = row.generation_id,
            r.dataset_id = row.dataset_id,
            r.origin = row.origin,
            r.reason = row.reason,
            r.edge_type = row.type
        """,
        rows=rows,
    )


def upsert_agent_edges(tx, rows: List[Dict[str, Any]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (a:Persona {id: row.source})
        MATCH (b:Persona {id: row.target})
        MERGE (a)-[r:RELATED_TO {edge_type: row.type}]->(b)
        SET r.edge_id = row.id,
            r.generation_id = row.generation_id,
            r.dataset_id = row.dataset_id,
            r.origin = row.origin,
            r.reason = row.reason
        """,
        rows=rows,
    )


def chunked(xs: List[Dict[str, Any]], n: int) -> List[List[Dict[str, Any]]]:
    if n < 1:
        n = 1000
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        generation_id = str(payload.get("generation_id") or "").strip()
        dataset_id = str(payload.get("dataset_id") or "").strip()
        agents = payload.get("agents") or []
        graph = payload.get("graph") or {}
        if not generation_id or not dataset_id:
            raise ValueError("generation_id / dataset_id 不能为空")
        if not isinstance(agents, list) or not agents:
            raise ValueError("agents 必须为非空数组")
        if not isinstance(graph, dict):
            raise ValueError("graph 必须为对象")

        neo4j_uri = (os.environ.get("NEO4J_URI") or "bolt://localhost:7687").strip()
        neo4j_db = (os.environ.get("OASIS_NEO4J_DATABASE") or "").strip() or None
        user, pwd = _parse_auth()
        if not pwd:
            raise ValueError("缺少 NEO4J_PASSWORD 或 NEO4J_AUTH")

        # agent 节点表：尽量从 agents 补全字段；node 里的 bio/interests 也可用，但 agents 更全
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        agent_nodes = [n for n in nodes if isinstance(n, dict) and n.get("type") == "agent"]
        topic_nodes = [n for n in nodes if isinstance(n, dict) and n.get("type") == "topic"]

        agent_doc_by_node_id = {}
        for a in agents:
            if not isinstance(a, dict):
                continue
            gid = a.get("generated_agent_id")
            if gid is None:
                continue
            agent_doc_by_node_id[f"agent_{gid}"] = a

        personas_rows: List[Dict[str, Any]] = []
        for n in agent_nodes:
            node_id = str(n.get("id") or "").strip()
            doc = agent_doc_by_node_id.get(node_id, {})
            other = _safe_get(doc, "profile", "other_info") or {}
            personas_rows.append(
                {
                    "id": node_id,
                    "generation_id": doc.get("generation_id") or generation_id,
                    "dataset_id": doc.get("dataset_id") or dataset_id,
                    "algorithm": doc.get("algorithm"),
                    "generated_agent_id": doc.get("generated_agent_id"),
                    "source_user_key": doc.get("source_user_key") or n.get("sourceUserKey"),
                    "user_name": doc.get("user_name"),
                    "name": doc.get("name") or n.get("name"),
                    "description": doc.get("description"),
                    "bio": n.get("bio") or other.get("user_profile"),
                    "interests": doc.get("interests") or n.get("interests") or [],
                    "user_type": doc.get("user_type") or n.get("userType"),
                    "recsys_type": doc.get("recsys_type"),
                    "gender": other.get("gender"),
                    "age": other.get("age"),
                    "mbti": other.get("mbti"),
                    "country": other.get("country"),
                    "created_at": doc.get("created_at"),
                }
            )

        topics_rows: List[Dict[str, Any]] = []
        for t in topic_nodes:
            topics_rows.append(
                {
                    "id": str(t.get("id") or "").strip(),
                    "name": t.get("name"),
                    "heat": t.get("heat"),
                    "source": t.get("source"),
                    "generation_id": generation_id,
                    "dataset_id": dataset_id,
                }
            )

        rel_rows: List[Dict[str, Any]] = []
        for e in edges:
            if not isinstance(e, dict):
                continue
            source = str(e.get("source") or "").strip()
            target = str(e.get("target") or "").strip()
            if not source or not target or source == target:
                continue
            rel_rows.append(
                {
                    "id": e.get("id"),
                    "source": source,
                    "target": target,
                    "type": e.get("type"),
                    "origin": e.get("origin"),
                    "reason": e.get("reason"),
                    "generation_id": generation_id,
                    "dataset_id": dataset_id,
                }
            )

        topic_links = [
            r
            for r in rel_rows
            if r.get("type") == "topic_link"
            and str(r.get("source", "")).startswith("agent_")
            and str(r.get("target", "")).startswith("topic_")
        ]
        agent_edges = [
            r
            for r in rel_rows
            if str(r.get("source", "")).startswith("agent_")
            and str(r.get("target", "")).startswith("agent_")
            and r.get("type") != "topic_link"
        ]

        driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
        try:
            if neo4j_db:
                session_kwargs = {"database": neo4j_db}
            else:
                session_kwargs = {}
            with driver.session(**session_kwargs) as s:
                s.execute_write(ensure_constraints)
                for batch in chunked(personas_rows, 500):
                    s.execute_write(upsert_personas, batch)
                for batch in chunked(topics_rows, 200):
                    s.execute_write(upsert_topics, batch)
                for batch in chunked(topic_links, 2000):
                    s.execute_write(upsert_topic_links, batch)
                for batch in chunked(agent_edges, 2000):
                    s.execute_write(upsert_agent_edges, batch)
        finally:
            driver.close()

        _json_out(
            {
                "status": "ok",
                "counts": {
                    "personas": len(personas_rows),
                    "topics": len(topics_rows),
                    "topic_links": len(topic_links),
                    "agent_edges": len(agent_edges),
                },
            }
        )
    except Exception as e:
        _json_out({"status": "error", "error": str(e), "type": "neo4j_import_worker"})
        raise


if __name__ == "__main__":
    main()

