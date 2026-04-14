"""
Topic Service - Business logic for database-backed topic management.

Coordinates topic activation with the OASIS simulation system and exposes
preprocessed topic/persona data sourced from oasis_datasets.db.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from oasis import ActionType, ManualAction, SocialAgent

from app.core.oasis_manager import OASISManager, OASISStateError
from app.models.simulation import PlatformType
from app.models.topics import (
    TopicActivationResult,
    TopicDetail,
    TopicListItem,
    TopicProfilesResponse,
    TopicReloadResult,
    TopicSimulationResponse,
)
from app.services.dataset_service import DatasetService, DatasetServiceError

logger = logging.getLogger(__name__)


class TopicServiceError(Exception):
    """Topic service error."""


class TopicNotReadyError(Exception):
    """Simulation not ready for topic activation."""


class TopicService:
    """Business logic coordinator for topics and simulation seed data."""

    def __init__(
        self,
        oasis_manager: OASISManager,
        dataset_service: Optional[DatasetService] = None,
    ):
        self.oasis_manager = oasis_manager
        self.dataset_service = dataset_service or DatasetService()
        logger.info("Topic Service initialized")

    async def activate_topic(
        self,
        topic_id: str,
        platform: PlatformType = PlatformType.TWITTER,
    ) -> TopicActivationResult:
        start_time = time.time()

        try:
            topic = self.dataset_service.get_topic(topic_id, platform)
            if not topic:
                return TopicActivationResult(
                    success=False,
                    message=f"Topic not found: {topic_id}",
                    topic_id=topic_id,
                    error="TOPIC_NOT_FOUND",
                )

            if not self.oasis_manager.is_ready:
                return TopicActivationResult(
                    success=False,
                    message=(
                        "Simulation not ready. "
                        f"Current state: {self.oasis_manager.state.value}"
                    ),
                    topic_id=topic_id,
                    error="SIMULATION_NOT_READY",
                )

            posting_agent = self._get_default_posting_agent()
            if not posting_agent:
                return TopicActivationResult(
                    success=False,
                    message="No simulation agent available to publish the seed content",
                    topic_id=topic_id,
                    error="AGENT_NOT_FOUND",
                )

            logger.info(
                "Activating topic '%s' with simulation agent %s",
                topic_id,
                getattr(posting_agent, "social_agent_id", "unknown"),
            )

            post_result = await self._execute_initial_post(
                topic.initial_post.content,
                posting_agent,
            )
            if not post_result["success"]:
                return TopicActivationResult(
                    success=False,
                    message=f"Failed to create initial post: {post_result['error']}",
                    topic_id=topic_id,
                    error=post_result["error"],
                )

            agents_refreshed = 0
            if topic.settings.trigger_refresh:
                refresh_result = await self._refresh_all_agents()
                agents_refreshed = refresh_result["count"]
                logger.info("Refreshed %s agents after initial post", agents_refreshed)

            execution_time = time.time() - start_time
            logger.info("Topic '%s' activated successfully in %.3fs", topic_id, execution_time)

            return TopicActivationResult(
                success=True,
                message=f"Topic '{topic.name}' activated successfully",
                topic_id=topic_id,
                initial_post_created=True,
                agents_refreshed=agents_refreshed,
                execution_time=execution_time,
            )

        except DatasetServiceError as exc:
            logger.error("Dataset lookup failed while activating topic '%s': %s", topic_id, exc)
            return TopicActivationResult(
                success=False,
                message=f"Topic activation failed: {exc}",
                topic_id=topic_id,
                error="DATASET_LOOKUP_FAILED",
                execution_time=time.time() - start_time,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Failed to activate topic '%s': %s", topic_id, exc)
            return TopicActivationResult(
                success=False,
                message=f"Topic activation failed: {exc}",
                topic_id=topic_id,
                error=str(exc),
                execution_time=time.time() - start_time,
            )

    def _get_default_posting_agent(self) -> Optional[SocialAgent]:
        all_agents = self.oasis_manager.get_all_agents()
        if not all_agents:
            return None
        return sorted(all_agents, key=lambda agent: getattr(agent, "social_agent_id", 0))[0]

    async def _execute_initial_post(self, content: str, agent: SocialAgent) -> Dict[str, Any]:
        try:
            action = ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": content},
            )

            result = await self.oasis_manager.step({agent: action})
            if result["success"]:
                logger.info(
                    "Initial post created by agent %s: %s...",
                    getattr(agent, "social_agent_id", "unknown"),
                    content[:50],
                )
                return {"success": True}
            return {"success": False, "error": "STEP_EXECUTION_FAILED"}

        except OASISStateError as exc:
            logger.error("OASIS state error during initial post: %s", exc)
            return {"success": False, "error": "OASIS_STATE_ERROR"}
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Failed to execute initial post: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _refresh_all_agents(self) -> Dict[str, Any]:
        try:
            all_agents = self.oasis_manager.get_all_agents()
            if not all_agents:
                logger.warning("No agents to refresh")
                return {"count": 0}

            refresh_actions = {
                agent: ManualAction(action_type=ActionType.REFRESH, action_args={})
                for agent in all_agents
            }
            result = await self.oasis_manager.step(refresh_actions)

            if result["success"]:
                logger.info("Refreshed %s agents", len(all_agents))
                return {"count": len(all_agents)}

            logger.warning("Refresh step failed: %s", result)
            return {"count": 0}

        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Failed to refresh agents: %s", exc)
            return {"count": 0}

    def list_topics(
        self,
        platform: PlatformType = PlatformType.TWITTER,
        limit: int = 50,
    ) -> List[TopicListItem]:
        return self.dataset_service.list_topics(platform=platform, limit=limit)

    def get_topic(
        self,
        topic_id: str,
        platform: PlatformType = PlatformType.TWITTER,
    ) -> Optional[TopicDetail]:
        return self.dataset_service.get_topic(topic_id, platform=platform)

    def get_topic_profiles(
        self,
        topic_id: str,
        platform: PlatformType = PlatformType.TWITTER,
        limit: int = 50,
    ) -> Optional[TopicProfilesResponse]:
        result = self.dataset_service.get_topic_profiles(topic_id, platform=platform, limit=limit)
        if not result:
            return None

        topic, profiles = result
        return TopicProfilesResponse(
            success=True,
            topic=topic,
            count=len(profiles),
            profiles=profiles,
        )

    def get_topic_simulation(
        self,
        topic_id: str,
        platform: PlatformType = PlatformType.TWITTER,
        participant_limit: int = 50,
        content_limit: int = 80,
    ) -> Optional[TopicSimulationResponse]:
        profiles_result = self.dataset_service.get_topic_profiles(
            topic_id,
            platform=platform,
            limit=participant_limit,
        )
        contents_result = self.dataset_service.get_topic_contents(
            topic_id,
            platform=platform,
            limit=content_limit,
        )

        if not profiles_result or not contents_result:
            return None

        topic, profiles = profiles_result
        _, contents = contents_result

        return TopicSimulationResponse(
            success=True,
            topic=topic,
            participant_count=len(profiles),
            content_count=len(contents),
            profiles=profiles,
            contents=contents,
        )

    def get_topic_count(self, platform: PlatformType = PlatformType.TWITTER) -> int:
        return self.dataset_service.get_topic_count(platform=platform)

    def topic_exists(
        self,
        topic_id: str,
        platform: PlatformType = PlatformType.TWITTER,
    ) -> bool:
        return self.dataset_service.topic_exists(topic_id, platform=platform)

    async def reload_config(
        self,
        platform: PlatformType = PlatformType.TWITTER,
    ) -> TopicReloadResult:
        try:
            start_time = time.time()
            topic_count = self.dataset_service.get_topic_count(platform=platform)
            reload_time = time.time() - start_time
            return TopicReloadResult(
                success=True,
                message="Topic data is read directly from database; reload not required",
                topics_loaded=topic_count,
                reload_time=reload_time,
            )
        except DatasetServiceError as exc:
            logger.error("Failed to refresh topic metadata: %s", exc)
            return TopicReloadResult(
                success=False,
                message=f"Refresh failed: {exc}",
                topics_loaded=0,
            )

    def validate_topic_for_simulation(
        self,
        topic_id: str,
        platform: PlatformType = PlatformType.TWITTER,
    ) -> Dict[str, Any]:
        issues: List[str] = []
        topic = self.dataset_service.get_topic(topic_id, platform=platform)

        if not topic:
            issues.append("Topic does not exist")
            return {"valid": False, "issues": issues}

        if not topic.initial_post.content.strip():
            issues.append("Topic has no usable seed content")

        if not self.oasis_manager.is_initialized:
            issues.append("Simulation not initialized")
        elif not self.oasis_manager.get_all_agents():
            issues.append("No simulation agents available")

        return {"valid": len(issues) == 0, "issues": issues}
