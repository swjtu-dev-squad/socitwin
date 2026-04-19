"""
Twitter + SQLite 社交网络边生成。
"""

from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.persona import sqlite_seed as seed

PLATFORM = "twitter"


def _norm_uid(x: Any) -> str:
    return str(x or "").strip()


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _datasets_data_dir() -> Path:
    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / "data" / "datasets" / "data"


def _write_bundle_json_files(bundle: Dict[str, Any]) -> None:
    data_dir = _datasets_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    users = bundle.get("users") or []
    topics = bundle.get("topics") or {"data": []}
    rels = bundle.get("relationships") or []
    user_ids = [
        f"user_{_safe_int(u.get('agent_id'), 0)}"
        for u in users
        if isinstance(u, dict) and u.get("agent_id") is not None
    ]
    stats: Dict[str, Dict[str, int]] = {uid: {"followersCount": 0, "followsCount": 0, "friendsCount": 0} for uid in user_ids}
    for r in rels:
        if not isinstance(r, dict):
            continue
        src = _norm_uid(r.get("fromUserId"))
        tgt = _norm_uid(r.get("toUserId"))
        typ = _norm_uid(r.get("type")).lower() or "follow"
        if not src or not tgt:
            continue
        if src in stats:
            stats[src]["followsCount"] += 1
            if typ in ("friend", "friends"):
                stats[src]["friendsCount"] += 1
        if tgt in stats:
            stats[tgt]["followersCount"] += 1
            if typ in ("friend", "friends"):
                stats[tgt]["friendsCount"] += 1
    user_networks = [{"userId": uid, "statistics": {"followersCount": v["followersCount"], "followsCount": v["followsCount"], "friendsCount": v["friendsCount"], "lastUpdated": None}} for uid, v in stats.items()]
    (data_dir / "users.json").write_text(json.dumps({"data": users}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (data_dir / "topics.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (data_dir / "relationships.json").write_text(json.dumps(rels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (data_dir / "user_networks.json").write_text(json.dumps(user_networks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pair_key(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _fetch_real_seed_edges(conn: sqlite3.Connection, user_ids: List[str], topic_keys: List[str]) -> Set[Tuple[str, str]]:
    uids = sorted({_norm_uid(x) for x in user_ids if _norm_uid(x)})
    if len(uids) < 2:
        return set()
    ph = ",".join("?" * len(uids))
    edges: Set[Tuple[str, str]] = set()
    cur = conn.execute(
        f"""
        SELECT DISTINCT c.author_external_user_id AS ua, p.author_external_user_id AS ub
        FROM contents c JOIN contents p
          ON p.platform = c.platform AND p.external_content_id = c.parent_external_content_id
        WHERE c.platform = ? AND c.content_type = 'reply' AND p.content_type = 'post'
          AND c.author_external_user_id IN ({ph}) AND p.author_external_user_id IN ({ph})
          AND c.author_external_user_id IS NOT NULL AND p.author_external_user_id IS NOT NULL
          AND c.author_external_user_id != p.author_external_user_id
        """,
        (PLATFORM, *uids, *uids),
    )
    for row in cur.fetchall():
        a, b = _norm_uid(row["ua"]), _norm_uid(row["ub"])
        if a and b and a != b:
            edges.add(_pair_key(a, b))
    return edges


def _agent_topics(agent: Dict[str, Any]) -> List[str]:
    prof = agent.get("profile")
    if isinstance(prof, dict):
        oi = prof.get("other_info")
        if isinstance(oi, dict):
            t = oi.get("topics")
            if isinstance(t, list):
                return [str(x).strip() for x in t if str(x).strip()]
    interests = agent.get("interests")
    if isinstance(interests, list):
        return [str(x).strip() for x in interests if str(x).strip()]
    return []


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    u = len(sa | sb)
    return 0.0 if u == 0 else len(sa & sb) / u


def _map_agent_to_seed(agent: Dict[str, Any], seeds: List[str]) -> str:
    if not seeds:
        return ""
    sk = _norm_uid(agent.get("source_user_key"))
    if sk and sk in set(seeds):
        return sk
    idx = _safe_int(agent.get("generated_agent_id"), 1) - 1
    return seeds[max(0, idx) % len(seeds)]


def build_social_graph_bundle(
    *,
    db_path: Any,
    topic_keys: List[str],
    algorithm: str,
    agents: List[Dict[str, Any]],
    topic_rows: List[Dict[str, Any]],
    seed_external_user_ids: Optional[List[str]] = None,
    seed_sample_user_count: int = 100,
    rng_seed: int = 42,
) -> Dict[str, Any]:
    if not agents:
        raise ValueError("agents 不能为空")
    algo = (algorithm or "community-homophily").strip().lower()
    rng = random.Random(rng_seed)
    path = db_path
    if not path.exists():
        raise ValueError(f"SQLite 不存在: {path}")
    seeds = [_norm_uid(x) for x in (seed_external_user_ids or []) if _norm_uid(x)] if seed_external_user_ids else []
    conn = seed.open_readonly(path)
    try:
        if not seeds:
            sample = seed.compute_multi_topic_seed_sample(
                conn,
                [_norm_uid(k) for k in topic_keys if _norm_uid(k)],
                max(10, min(2000, int(seed_sample_user_count or 100))),
            )
            seeds = [_norm_uid(x) for x in sample.get("external_user_ids") or [] if _norm_uid(x)]
        if len(seeds) < 1:
            raise ValueError("无法得到种子用户 id：请传入 seed_external_user_ids 或有效 topic_keys")
        real_pairs = _fetch_real_seed_edges(conn, seeds, topic_keys)
    finally:
        conn.close()

    users_out: List[Dict[str, Any]] = []
    agent_uid: List[str] = []
    seed_for_agent: List[str] = []
    for agent in agents:
        gid = _safe_int(agent.get("generated_agent_id"), len(users_out) + 1)
        topics = _agent_topics(agent)
        ut = str(agent.get("user_type") or "normal").strip().lower()
        if ut != "kol":
            ut = "normal"
        users_out.append({"agent_id": gid, "name": str(agent.get("name") or ""), "user_name": str(agent.get("user_name") or ""), "description": str(agent.get("description") or ""), "user_type": ut, "profile": {"other_info": {"topics": topics}}})
        agent_uid.append(f"user_{gid}")
        seed_for_agent.append(_map_agent_to_seed(agent, seeds))

    directed: Set[Tuple[str, str]] = set()
    rel_list: List[Dict[str, str]] = []

    def add_directed(a: str, b: str, typ: str = "follow") -> None:
        if a == b or (a, b) in directed:
            return
        directed.add((a, b))
        rel_list.append({"fromUserId": a, "toUserId": b, "type": typ})

    seed_to_indices: Dict[str, List[int]] = {}
    for idx, su in enumerate(seed_for_agent):
        seed_to_indices.setdefault(su, []).append(idx)
    for su, sv in real_pairs:
        for i in sorted(seed_to_indices.get(su) or [], key=lambda x: agent_uid[x])[:3]:
            for j in sorted(seed_to_indices.get(sv) or [], key=lambda x: agent_uid[x])[:3]:
                if i != j:
                    add_directed(agent_uid[i], agent_uid[j])
                    add_directed(agent_uid[j], agent_uid[i])

    n = len(users_out)
    topic_lists = [_agent_topics(agents[i]) for i in range(n)]

    def homophily_prob(i: int, j: int) -> float:
        jac = _jaccard(topic_lists[i], topic_lists[j])
        if algo == "semantic-homophily":
            return min(0.88, 0.08 + 1.35 * jac)
        if algo == "community-homophily":
            return min(0.85, 0.05 + 1.2 * jac)
        if algo == "real-seed-fusion":
            return min(0.35, 0.02 + 0.45 * jac) if jac > 0 else 0.0
        if algo == "ba-structural":
            return min(0.75, 0.12 + 0.55 * jac)
        return min(0.8, 0.06 + jac)

    for i in range(n):
        for j in range(i + 1, n):
            p = homophily_prob(i, j)
            if algo == "real-seed-fusion" and _pair_key(seed_for_agent[i], seed_for_agent[j]) not in real_pairs:
                p *= 0.28
            if p > 0 and rng.random() < p:
                add_directed(agent_uid[i], agent_uid[j])

    titles = [str(t.get("title") or "").strip() for t in topic_rows if isinstance(t, dict)]
    titles = [x for x in titles if x] or sorted({t for tl in topic_lists for t in tl})[:24] or ["未分类"]
    topics_doc = {"data": [{"category": "sqlite_social", "topics": titles}]}
    undirected_e = len({tuple(sorted((r["fromUserId"], r["toUserId"]))) for r in rel_list})
    max_u = n * (n - 1) / 2 if n > 1 else 0
    density = undirected_e / max_u if max_u else 0.0
    bundle = {
        "status": "ok",
        "users": users_out,
        "relationships": rel_list,
        "user_networks": [],
        "topics": topics_doc,
        "metrics": {
            "user_count": n,
            "relationship_edge_count": len(rel_list),
            "network_density_ratio": density,
            "real_seed_edge_count": len(real_pairs),
            "algorithm": algo,
        },
    }
    _write_bundle_json_files(bundle)
    return bundle

