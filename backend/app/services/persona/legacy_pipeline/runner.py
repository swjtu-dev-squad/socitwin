from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.persona.legacy_pipeline.common import data_dir
from app.services.persona.legacy_pipeline.relations_generate import (
    generate_relationship_and_network_files,
)
from app.services.persona.legacy_pipeline.topics_classify import classify_topics_to_topics_json
from app.services.persona.legacy_pipeline.users_format_convert import (
    convert_users_get_to_users_json,
)


def persist_topics_users_get(topics: List[Dict[str, Any]], users: List[Dict[str, Any]]) -> Dict[str, Any]:
    dd = data_dir()
    dd.mkdir(parents=True, exist_ok=True)
    topics_get = dd / "topics_get.json"
    users_get = dd / "users_get.json"
    topics_get.write_text(json.dumps(topics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    users_get.write_text(json.dumps(users, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "topics_get": str(topics_get),
        "users_get": str(users_get),
        "topics_count": len(topics),
        "users_count": len(users),
    }


def run_social_local_pipeline() -> Dict[str, Any]:
    dd = data_dir()
    dd.mkdir(parents=True, exist_ok=True)
    classify_topics_to_topics_json()
    convert_users_get_to_users_json()
    metrics = generate_relationship_and_network_files(dd)
    return {"status": "ok", "metrics": metrics}


def get_social_graph_bundle() -> Dict[str, Any]:
    def load(name: str) -> Any:
        p = data_dir() / name
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    users = load("users.json")
    relationships = load("relationships.json")
    user_networks = load("user_networks.json")
    topics = load("topics.json")
    metrics = load("graph_metrics.json")
    if users is None or relationships is None:
        raise FileNotFoundError("社交关系生成失败：缺少 users.json 或 relationships.json")
    return {
        "status": "ok",
        "users": users,
        "relationships": relationships,
        "user_networks": user_networks or [],
        "topics": topics or None,
        "metrics": metrics or {},
    }

