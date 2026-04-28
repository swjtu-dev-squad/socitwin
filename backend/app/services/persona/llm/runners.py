"""进程内执行 Persona LLM（域入口：app.services.persona.llm）。"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from app.services.persona.llm.batch import (
    generate_llm_persona_users,
    generate_synthetic_topics,
    model_spec_from_env,
)
from app.services.persona.llm.camel_llm_build import build_shared_model


def _parse_ratio_topics(s: str) -> tuple[int, int]:
    raw = (s or "").strip()
    if not raw:
        return (1, 10)
    if ":" not in raw:
        raise ValueError("kol_normal_ratio 需形如 '1:10'")
    a, b = raw.split(":", 1)
    x = int(a.strip())
    y = int(b.strip())
    if x < 0 or y < 0 or (x == 0 and y == 0):
        raise ValueError("kol_normal_ratio 必须为非负整数，且不能同时为 0")
    return (x, y)


def _parse_ratio_persona_only(s: str) -> tuple[int, int]:
    raw = (s or "").strip()
    if not raw:
        return (1, 8)
    if ":" not in raw:
        raise ValueError("kol_normal_ratio 需形如 '1:8'")
    a, b = raw.split(":", 1)
    x = int(a.strip())
    y = int(b.strip())
    if x < 0 or y < 0 or (x == 0 and y == 0):
        raise ValueError("kol_normal_ratio 必须为非负整数，且不能同时为 0")
    return (x, y)


def run_topics_users_llm_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    selected = payload.get("selected_topics") or []
    if not isinstance(selected, list) or not selected:
        raise ValueError("selected_topics 必须为非空数组")
    syn_n = int(payload.get("synthetic_topic_count") or 0)
    if syn_n < 1:
        raise ValueError("synthetic_topic_count 须 >= 1")
    seed_users = payload.get("seed_users") or []
    if not isinstance(seed_users, list) or not seed_users:
        raise ValueError("seed_users 必须为非空数组")
    user_target_count = int(payload.get("user_target_count") or 0)
    if user_target_count < 1:
        raise ValueError("user_target_count 须 >= 1")
    dataset_id = str(payload.get("dataset_id") or "").strip()
    if not dataset_id:
        raise ValueError("dataset_id 不能为空")
    recsys_type = str(payload.get("recsys_type") or "twitter").strip()
    batch_size = int(payload.get("batch_size") or 8)
    seed_sample = int(payload.get("seed_sample") or 12)
    max_retries = int(payload.get("max_retries") or 3)
    kol_ratio = _parse_ratio_topics(str(payload.get("kol_normal_ratio") or "1:10").strip())

    spec = model_spec_from_env()
    model = build_shared_model(spec).model
    topics = generate_synthetic_topics(model, selected_topics=selected, topic_count=syn_n, max_retries=max(1, min(10, max_retries)))
    topic_titles = [str(t.get("title") or "").strip() for t in topics if isinstance(t, dict) and str(t.get("title") or "").strip()]
    users, meta = generate_llm_persona_users(
        seed_users,
        target_count=max(1, min(2000, user_target_count)),
        dataset_id=dataset_id,
        recsys_type=recsys_type,
        batch_size=max(2, min(20, batch_size)),
        seed_sample=max(3, min(40, seed_sample)),
        max_retries=max(1, min(10, max_retries)),
        kol_normal_ratio=kol_ratio,
        global_context=json.dumps(topics, ensure_ascii=False, indent=2),
        synthetic_topic_titles=topic_titles,
    )
    meta = dict(meta or {})
    meta["synthetic_topics"] = topics
    meta["synthetic_topic_count_requested"] = syn_n
    meta["synthetic_topic_count_actual"] = len(topics)
    return {"status": "ok", "topics": topics, "users": users, "meta": meta}


async def run_topics_users_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await asyncio.to_thread(run_topics_users_llm_sync, payload)


def run_persona_llm_only_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    seed_users = payload.get("seed_users") or []
    target_count = int(payload.get("target_count", 0))
    dataset_id = str(payload.get("dataset_id") or "").strip()
    recsys_type = str(payload.get("recsys_type") or "unknown").strip()
    batch_size = int(payload.get("batch_size") or 8)
    seed_sample = int(payload.get("seed_sample") or 12)
    max_retries = int(payload.get("max_retries") or 3)
    kol_ratio = _parse_ratio_persona_only(str(payload.get("kol_normal_ratio") or "1:8").strip())
    if not isinstance(seed_users, list) or not seed_users:
        raise ValueError("seed_users 必须为非空数组")
    if target_count < 1:
        raise ValueError("target_count 须 >= 1")
    if not dataset_id:
        raise ValueError("dataset_id 不能为空")
    users, meta = generate_llm_persona_users(
        seed_users,
        target_count=target_count,
        dataset_id=dataset_id,
        recsys_type=recsys_type,
        batch_size=max(2, min(20, batch_size)),
        seed_sample=max(3, min(40, seed_sample)),
        max_retries=max(1, min(10, max_retries)),
        kol_normal_ratio=kol_ratio,
    )
    return {"status": "ok", "users": users, "meta": meta}


async def run_persona_llm_only(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await asyncio.to_thread(run_persona_llm_only_sync, payload)
