"""
用户画像（Persona）：SQLite 话题/种子 + 进程内 CAMEL LLM（app.services.persona.llm）。
不含 MongoDB。
"""

from __future__ import annotations

import logging
import random
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.services.dataset_service import DatasetService
from app.services.persona.llm.runners import run_persona_llm_only, run_topics_users_llm
from app.services.persona import sqlite_seed as seed
from app.services.persona.legacy_pipeline.runner import persist_topics_users_get
from app.services.persona.social_graph_sqlite import build_social_graph_bundle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/persona", tags=["persona"])


def _db_path() -> Any:
    return DatasetService().db_path


class TopicSeedBody(BaseModel):
    topic_keys: List[str] = Field(..., min_length=1)
    seed_user_count: int = Field(100, ge=1, le=2000)
    include_ids: bool = False


class SqlitePersonasLlmBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    topic_keys: List[str] = Field(..., min_length=1)
    seed_user_count: int = Field(100, ge=1, le=2000)
    target_count: Optional[int] = None
    llm_batch_size: Optional[int] = Field(
        None, validation_alias=AliasChoices("llm_batch_size", "llmBatchSize")
    )
    llm_seed_sample: Optional[int] = Field(
        None, validation_alias=AliasChoices("llm_seed_sample", "llmSeedSample")
    )
    llm_max_retries: Optional[int] = Field(
        None, validation_alias=AliasChoices("llm_max_retries", "llmMaxRetries")
    )
    llm_kol_normal_ratio: Optional[str] = Field(
        None, validation_alias=AliasChoices("llm_kol_normal_ratio", "llmKolNormalRatio")
    )


class SqliteSocialGraphBody(BaseModel):
    """与旧 social-graph-bundle 等价的输入：由 SQLite 真实边 + 算法补边生成 relationships。"""

    model_config = ConfigDict(populate_by_name=True)

    topic_keys: List[str] = Field(..., min_length=1)
    algorithm: str = Field("community-homophily", min_length=1, max_length=64)
    agents: List[Dict[str, Any]] = Field(..., min_length=1)
    topics: List[Dict[str, Any]] = Field(default_factory=list)
    seed_external_user_ids: Optional[List[str]] = None
    seed_sample_user_count: int = Field(100, ge=10, le=2000)
    rng_seed: int = Field(42, ge=0, le=2_000_000_000)


class SqliteTopicsPersonasLlmBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    topic_keys: List[str] = Field(..., min_length=1)
    seed_user_count: int = Field(100, ge=1, le=2000)
    synthetic_topic_count: int = Field(..., ge=1, le=64)
    user_target_count: int = Field(10, ge=1, le=2000)
    llm_batch_size: Optional[int] = Field(
        None, validation_alias=AliasChoices("llm_batch_size", "llmBatchSize")
    )
    llm_seed_sample: Optional[int] = Field(
        None, validation_alias=AliasChoices("llm_seed_sample", "llmSeedSample")
    )
    llm_max_retries: Optional[int] = Field(
        None, validation_alias=AliasChoices("llm_max_retries", "llmMaxRetries")
    )
    llm_kol_normal_ratio: Optional[str] = Field(
        None, validation_alias=AliasChoices("llm_kol_normal_ratio", "llmKolNormalRatio")
    )


@router.get("/twitter/sqlite-topics")
async def sqlite_topics(
    format: str = Query("", alias="format"),
    recent_pool: int = Query(500, ge=1, le=5000),
    min_topics: int = Query(30, ge=1, le=200),
):
    """与旧版 GET /api/persona/twitter/sqlite-topics 对齐。"""
    path = _db_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"SQLite 不存在: {path}")
    fmt = (format or "").lower()
    conn = seed.open_readonly(path)
    try:
        if fmt == "list":
            topics = seed.list_recent_topics_ordered(conn, recent_pool)
            return {"status": "ok", "topics": topics, "total": len(topics), "format": "list"}
        topics = seed.list_recent_topics_ordered(conn, recent_pool)
        _shuffle = list(topics)
        random.shuffle(_shuffle)
        picked = _shuffle[: min(min_topics, len(_shuffle))]
        return {"status": "ok", "topics": picked, "total_recent": len(topics), "min_topics": min_topics}
    finally:
        conn.close()


@router.post("/twitter/sqlite-topic-seed")
async def sqlite_topic_seed_post(body: TopicSeedBody):
    path = _db_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"SQLite 不存在: {path}")
    conn = seed.open_readonly(path)
    try:
        result = seed.compute_multi_topic_seed_sample(conn, body.topic_keys, body.seed_user_count)
    finally:
        conn.close()
    out: Dict[str, Any] = {
        "status": "ok",
        "topic_key": result["topic_key"],
        "topic_keys": body.topic_keys,
        "user_limit_requested": result["user_limit_requested"],
        "users_selected": result["users_selected"],
        "kol_selected": result["kol_selected"],
        "normal_selected": result["normal_selected"],
        "counts": result["counts"],
    }
    if body.include_ids:
        out["external_user_ids"] = result["external_user_ids"]
    return out


@router.get("/twitter/sqlite-topic-seed")
async def sqlite_topic_seed_get(
    topic_key: str = Query(""),
    topic_keys: Optional[List[str]] = Query(None),
    user_limit: int = Query(100, ge=1, le=2000),
    include_ids: bool = Query(False),
):
    keys: List[str] = []
    if topic_keys:
        keys.extend(topic_keys)
    if topic_key.strip():
        keys.append(topic_key.strip())
    keys = list(dict.fromkeys(keys))
    if not keys:
        raise HTTPException(status_code=400, detail="缺少 topic_key 或 topic_keys")
    return await sqlite_topic_seed_post(TopicSeedBody(topic_keys=keys, seed_user_count=user_limit, include_ids=include_ids))


@router.post("/twitter/sqlite-personas-llm")
async def sqlite_personas_llm(body: SqlitePersonasLlmBody):
    path = _db_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"SQLite 不存在: {path}")
    conn = seed.open_readonly(path)
    try:
        sample = seed.compute_multi_topic_seed_sample(conn, body.topic_keys, body.seed_user_count)
        seeds = seed.build_seed_users_for_llm_from_sqlite(conn, sample["external_user_ids"])
    finally:
        conn.close()
    if not seeds:
        raise HTTPException(
            status_code=400,
            detail="未从 SQLite 组装到任何种子用户（请确认话题下有帖子且作者存在于 users 表）",
        )
    raw_target = body.target_count
    target = (
        max(1, min(2000, int(raw_target)))
        if raw_target is not None and int(raw_target) > 0
        else len(seeds)
    )
    dataset_id = f"sqlite_{uuid.uuid4().hex[:20]}"
    payload = {
        "seed_users": seeds,
        "target_count": target,
        "dataset_id": dataset_id,
        "recsys_type": "twitter",
        "batch_size": int(body.llm_batch_size or 4),
        "seed_sample": int(body.llm_seed_sample or 12),
        "max_retries": int(body.llm_max_retries or 2),
        "kol_normal_ratio": str(body.llm_kol_normal_ratio or "1:10"),
    }
    try:
        llm_out = await run_persona_llm_only(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("persona_llm_only failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    if llm_out.get("status") != "ok":
        raise HTTPException(status_code=502, detail=llm_out.get("error") or str(llm_out))
    users = llm_out.get("users") or []
    return {
        "status": "ok",
        "dataset_id": dataset_id,
        "seed_users_built": len(seeds),
        "seed_sample_counts": sample["counts"],
        "users": users,
        "meta": llm_out.get("meta"),
        "sqlite_persist": {"ok": True, "note": "未写入 SQLite（Mongo 已移除；持久化逻辑可后续接入）"},
    }


@router.post("/twitter/sqlite-topics-personas-llm")
async def sqlite_topics_personas_llm(body: SqliteTopicsPersonasLlmBody):
    path = _db_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"SQLite 不存在: {path}")
    conn = seed.open_readonly(path)
    try:
        selected = seed.get_topic_labels_for_keys(conn, body.topic_keys)
        sample = seed.compute_multi_topic_seed_sample(conn, body.topic_keys, body.seed_user_count)
        seeds = seed.build_seed_users_for_llm_from_sqlite(conn, sample["external_user_ids"])
    finally:
        conn.close()
    if not seeds:
        raise HTTPException(
            status_code=400,
            detail="未从 SQLite 组装到任何种子用户（请确认话题下有帖子且作者存在于 users 表）",
        )
    dataset_id = f"sqlite_{uuid.uuid4().hex[:20]}"
    payload = {
        "selected_topics": selected,
        "synthetic_topic_count": body.synthetic_topic_count,
        "seed_users": seeds,
        "user_target_count": body.user_target_count,
        "dataset_id": dataset_id,
        "recsys_type": "twitter",
        "batch_size": int(body.llm_batch_size or 4),
        "seed_sample": int(body.llm_seed_sample or 12),
        "max_retries": int(body.llm_max_retries or 2),
        "kol_normal_ratio": str(body.llm_kol_normal_ratio or "1:10"),
    }
    try:
        llm_out = await run_topics_users_llm(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("topics_users_llm failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    if llm_out.get("status") != "ok":
        raise HTTPException(status_code=502, detail=llm_out.get("error") or str(llm_out))
    topics_out = llm_out.get("topics") or []
    users_out = llm_out.get("users") or []
    persist_meta = persist_topics_users_get(
        [x for x in topics_out if isinstance(x, dict)],
        [x for x in users_out if isinstance(x, dict)],
    )
    return {
        "status": "ok",
        "dataset_id": dataset_id,
        "seed_users_built": len(seeds),
        "seed_sample_counts": sample["counts"],
        "seed_external_user_ids": sample.get("external_user_ids") or [],
        "topics": topics_out,
        "users": users_out,
        "meta": llm_out.get("meta"),
        "sqlite_persist": {"ok": True, **persist_meta},
    }


@router.post("/twitter/sqlite-social-graph-bundle")
async def sqlite_social_graph_bundle(body: SqliteSocialGraphBody):
    """生成与旧 /api/datasets/social-graph-bundle 结构一致的 JSON（基于 SQLite 真实互动 + 算法补边）。"""
    path = _db_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"SQLite 不存在: {path}")
    try:
        out = build_social_graph_bundle(
            db_path=path,
            topic_keys=body.topic_keys,
            algorithm=body.algorithm,
            agents=body.agents,
            topic_rows=body.topics,
            seed_external_user_ids=body.seed_external_user_ids,
            seed_sample_user_count=body.seed_sample_user_count,
            rng_seed=body.rng_seed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@router.get("/datasets", summary="List Datasets")
async def list_datasets():
    return {"datasets": []}


@router.get("/datasets/{dataset_id}", summary="Get Dataset")
async def get_dataset(dataset_id: str):
    raise HTTPException(status_code=404, detail="Mongo 数据集已移除；请使用 Twitter + SQLite 流程")


@router.post("/datasets/{dataset_id}/generate", summary="Generate Dataset")
async def generate_dataset(dataset_id: str):
    raise HTTPException(
        status_code=501,
        detail="基于 Mongo 的 /generate 未迁移。请使用「生成仿真话题与用户画像」+ SQLite 流程。",
    )


@router.get("/generations/{generation_id}/agents", summary="Generations Agents")
async def generations_agents(generation_id: str):
    raise HTTPException(status_code=404, detail="Mongo generations 已移除")


@router.get("/generations/{generation_id}/graph", summary="Generations Graph")
async def generations_graph(generation_id: str):
    raise HTTPException(status_code=404, detail="Mongo generations 已移除")


@router.get("/generations/{generation_id}/explanation", summary="Generations Explanation")
async def generations_explanation(generation_id: str):
    raise HTTPException(status_code=404, detail="Mongo generations 已移除")
