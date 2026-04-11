"""
Topics API Endpoints - FastAPI router for topic management

Provides REST API endpoints for managing simulation topics.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.services.topic_service import TopicService
from app.services.simulation_service import SimulationService
from app.models.topics import (
    TopicActivationResult,
    TopicDetail,
    TopicListItem,
    TopicListResponse,
    TopicReloadResult,
)


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)


# ============================================================================
# Dependencies
# ============================================================================

# These will be provided by the dependency injection system
# For now, we'll use placeholder functions that will be replaced
# when we update the dependencies module

async def get_topic_service():
    """Get topic service instance (placeholder)"""
    # This will be replaced by proper dependency injection
    from app.core.dependencies import get_topic_service_dependency
    return await get_topic_service_dependency().__anext__()


async def get_simulation_service():
    """Get simulation service instance (placeholder)"""
    # This will be replaced by proper dependency injection
    from app.core.dependencies import get_simulation_service_dependency
    return await get_simulation_service_dependency().__anext__()


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=TopicListResponse)
async def list_topics(
    service: TopicService = Depends(get_topic_service)
):
    """
    List all available topics

    Returns a list of all topics with their basic information.
    """
    try:
        topics = service.list_topics()

        return TopicListResponse(
            success=True,
            count=len(topics),
            topics=topics,
        )

    except Exception as e:
        logger.error(f"Failed to list topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list topics: {str(e)}"
        )


@router.get("/{topic_id}", response_model=TopicDetail)
async def get_topic(
    topic_id: str,
    service: TopicService = Depends(get_topic_service)
):
    """
    Get detailed information about a specific topic

    Returns complete topic configuration including initial post and settings.
    """
    try:
        topic = service.get_topic(topic_id)

        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic not found: {topic_id}"
            )

        return topic

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get topic '{topic_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topic: {str(e)}"
        )


@router.post("/{topic_id}/activate", response_model=TopicActivationResult)
async def activate_topic(
    topic_id: str,
    topic_service: TopicService = Depends(get_topic_service),
    sim_service: SimulationService = Depends(get_simulation_service)
):
    """
    Activate a topic by posting initial content and refreshing feeds

    This endpoint will:
    1. Load the topic configuration
    2. Have the specified agent post the initial content
    3. Refresh all agents' feeds (if configured)

    The simulation must be in READY state for activation to succeed.
    """
    try:
        # Validate simulation state
        if not sim_service.oasis_manager.is_ready:
            return TopicActivationResult(
                success=False,
                message=f"Simulation not ready. Current state: {sim_service.oasis_manager.state.value}",
                topic_id=topic_id,
                error="SIMULATION_NOT_READY"
            )

        # Activate topic
        result = await topic_service.activate_topic(topic_id)

        return result

    except Exception as e:
        logger.error(f"Failed to activate topic '{topic_id}': {e}")
        return TopicActivationResult(
            success=False,
            message=f"Topic activation failed: {str(e)}",
            topic_id=topic_id,
            error=str(e),
        )


@router.post("/reload", response_model=TopicReloadResult)
async def reload_topics(
    service: TopicService = Depends(get_topic_service)
):
    """
    Reload topic configuration from disk

    This endpoint reloads the topics.yaml file to pick up any changes
    without requiring a server restart.
    """
    try:
        result = await service.reload_config()
        return result

    except Exception as e:
        logger.error(f"Failed to reload topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload topics: {str(e)}"
        )


@router.get("/{topic_id}/validate")
async def validate_topic(
    topic_id: str,
    topic_service: TopicService = Depends(get_topic_service)
):
    """
    Validate if a topic can be activated in the current simulation

    Returns validation result with any issues found.
    """
    try:
        if not topic_service.topic_exists(topic_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic not found: {topic_id}"
            )

        validation = topic_service.validate_topic_for_simulation(topic_id)
        return validation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate topic '{topic_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )
