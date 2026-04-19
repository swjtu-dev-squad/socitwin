"""
Topics API Endpoints - FastAPI router for topic and seed-data management.

Serves topic metadata, preprocessed persona seeds, and simulation seed content
from the unified SQLite dataset database.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.simulation import PlatformType
from app.models.topics import (
    TopicActivationResult,
    TopicDetail,
    TopicListResponse,
    TopicProfilesResponse,
    TopicReloadResult,
    TopicSimulationResponse,
)
from app.services.simulation_service import SimulationService
from app.services.topic_service import TopicService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)


async def get_topic_service():
    """Get topic service instance."""
    from app.core.dependencies import get_topic_service_dependency

    return await get_topic_service_dependency().__anext__()


async def get_simulation_service():
    """Get simulation service instance."""
    from app.core.dependencies import get_simulation_service_dependency

    return await get_simulation_service_dependency().__anext__()


@router.get("", response_model=TopicListResponse)
async def list_topics(
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    limit: int = Query(default=50, ge=1, le=200),
    service: TopicService = Depends(get_topic_service),
):
    """List topics directly from `oasis_datasets.db`."""
    try:
        topics = service.list_topics(platform=platform, limit=limit)
        return TopicListResponse(success=True, count=len(topics), topics=topics)
    except Exception as exc:
        logger.error("Failed to list topics: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list topics: {exc}",
        ) from exc


@router.get("/{topic_id}/profiles", response_model=TopicProfilesResponse)
async def get_topic_profiles(
    topic_id: str,
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    limit: int = Query(default=50, ge=1, le=500),
    service: TopicService = Depends(get_topic_service),
):
    """Get preprocessed participant profiles for the user-profile sidebar."""
    try:
        result = service.get_topic_profiles(topic_id, platform=platform, limit=limit)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic not found: {topic_id}",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get profiles for topic '%s': %s", topic_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topic profiles: {exc}",
        ) from exc


@router.get("/{topic_id}/simulation", response_model=TopicSimulationResponse)
async def get_topic_simulation_data(
    topic_id: str,
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    participant_limit: int = Query(default=50, ge=1, le=500),
    content_limit: int = Query(default=80, ge=1, le=500),
    service: TopicService = Depends(get_topic_service),
):
    """Get simulation-ready seed data for the situational inference module."""
    try:
        result = service.get_topic_simulation(
            topic_id,
            platform=platform,
            participant_limit=participant_limit,
            content_limit=content_limit,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic not found: {topic_id}",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get simulation data for topic '%s': %s", topic_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topic simulation data: {exc}",
        ) from exc


@router.get("/{topic_id}", response_model=TopicDetail)
async def get_topic(
    topic_id: str,
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    service: TopicService = Depends(get_topic_service),
):
    """Get detailed topic information from the dataset database."""
    try:
        topic = service.get_topic(topic_id, platform=platform)
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic not found: {topic_id}",
            )
        return topic
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get topic '%s': %s", topic_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topic: {exc}",
        ) from exc


@router.post("/{topic_id}/activate", response_model=TopicActivationResult)
async def activate_topic(
    topic_id: str,
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    topic_service: TopicService = Depends(get_topic_service),
    sim_service: SimulationService = Depends(get_simulation_service),
):
    """Activate a topic by publishing its dataset-backed seed content into the simulation."""
    try:
        if not sim_service.oasis_manager.is_ready:
            return TopicActivationResult(
                success=False,
                message=(
                    "Simulation not ready. "
                    f"Current state: {sim_service.oasis_manager.state.value}"
                ),
                topic_id=topic_id,
                error="SIMULATION_NOT_READY",
            )

        return await topic_service.activate_topic(topic_id, platform=platform)
    except Exception as exc:
        logger.error("Failed to activate topic '%s': %s", topic_id, exc)
        return TopicActivationResult(
            success=False,
            message=f"Topic activation failed: {exc}",
            topic_id=topic_id,
            error=str(exc),
        )


@router.post("/reload", response_model=TopicReloadResult)
async def reload_topics(
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    service: TopicService = Depends(get_topic_service),
):
    """Refresh topic metadata. Database-backed topics do not require file reloads."""
    try:
        return await service.reload_config(platform=platform)
    except Exception as exc:
        logger.error("Failed to refresh topics: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh topics: {exc}",
        ) from exc


@router.get("/{topic_id}/validate")
async def validate_topic(
    topic_id: str,
    platform: PlatformType = Query(default=PlatformType.TWITTER),
    topic_service: TopicService = Depends(get_topic_service),
):
    """Validate whether a dataset topic can be activated in the current simulation."""
    try:
        if not topic_service.topic_exists(topic_id, platform=platform):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic not found: {topic_id}",
            )

        return topic_service.validate_topic_for_simulation(topic_id, platform=platform)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to validate topic '%s': %s", topic_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {exc}",
        ) from exc
