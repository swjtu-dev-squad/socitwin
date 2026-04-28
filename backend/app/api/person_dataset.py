"""旧 dashboard 的 /api/datasets/* 兼容端点。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.services.persona.legacy_pipeline.runner import (
    get_social_graph_bundle,
    run_social_local_pipeline,
)
from app.services.persona.neo4j_sync import import_from_data_dir

router = APIRouter(prefix="/datasets", tags=["person-dataset"])


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
async def networks_neo4j_sync(clear: bool = Query(False, description="为 true 时先清空旧图（User/Topic/TopicCategory）再导入")):
    data_dir = Path(__file__).resolve().parents[2] / "data" / "datasets" / "data"
    try:
        return import_from_data_dir(data_dir=data_dir, clear=bool(clear))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
