"""旧 dashboard 的 /api/datasets/* 兼容端点。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.persona.legacy_pipeline.runner import (
    get_social_graph_bundle,
    run_social_local_pipeline,
)
from app.services.persona.neo4j_sqlite_sync import import_from_sqlite
from app.services.persona.neo4j_sync import import_from_data_dir

router = APIRouter(prefix="/datasets", tags=["person-dataset"])

class SqliteNeo4jSyncRequest(BaseModel):
    platform: str = Field(default="", description="过滤 platform（如 twitter/reddit/twitter_llm）；空表示全量")
    clear: bool = Field(default=False, description="是否清空 Neo4j 中已有的 User/Topic（仅删这些标签）")
    limit_edges: int | None = Field(default=None, description="调试用：限制导入的 user_topics 条数")


@router.post("/social-local-pipeline")
async def social_local_pipeline():
    try:
        return run_social_local_pipeline()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/social-graph-bundle")
async def social_graph_bundle():
    try:
        return get_social_graph_bundle()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/networks-neo4j-sync")
async def networks_neo4j_sync():
    data_dir = Path(__file__).resolve().parents[2] / "data" / "datasets" / "data"
    try:
        return import_from_data_dir(data_dir=data_dir, clear=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/sqlite-neo4j-sync")
async def sqlite_neo4j_sync(req: SqliteNeo4jSyncRequest):
    db_path = Path(__file__).resolve().parents[2] / "data" / "datasets" / "oasis_datasets.db"
    try:
        return import_from_sqlite(
            db_path=db_path,
            platform=req.platform.strip() or None,
            clear=bool(req.clear),
            limit_edges=req.limit_edges,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
