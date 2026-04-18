"""
Topic Service - Business logic for topic management

Coordinates topic activation with the OASIS simulation system.
"""

import logging
import time
from typing import List, Optional, Dict, Any

from oasis import SocialAgent, ManualAction, ActionType

from app.core.oasis_manager import OASISManager, OASISStateError
from app.core.topic_loader import TopicLoader, get_topic_loader, TopicLoadError
from app.models.topics import (
    Topic,
    TopicActivationResult,
    TopicDetail,
    TopicListItem,
    TopicReloadResult,
)


logger = logging.getLogger(__name__)


class TopicServiceError(Exception):
    """Topic service error"""
    pass


class TopicNotReadyError(Exception):
    """Simulation not ready for topic activation"""
    pass


class TopicService:
    """
    Topic service - Business logic coordinator

    Responsibilities:
    - Coordinate topic activation with OASIS manager
    - Validate simulation state before activation
    - Execute initial posts and refresh operations
    - Provide topic query functionality
    """

    def __init__(self, oasis_manager: OASISManager, topic_loader: TopicLoader = None):
        """
        Initialize topic service

        Args:
            oasis_manager: OASIS manager instance
            topic_loader: Topic loader instance (uses singleton if not provided)
        """
        self.oasis_manager = oasis_manager
        self.topic_loader = topic_loader or get_topic_loader()

        logger.info("Topic Service initialized")

    # ========================================================================
    # Topic Activation
    # ========================================================================

    async def activate_topic(self, topic_id: str) -> TopicActivationResult:
        """
        Activate a topic by posting initial content and refreshing feeds

        Args:
            topic_id: ID of the topic to activate

        Returns:
            Activation result with execution details

        Raises:
            TopicServiceError: If activation fails
        """
        start_time = time.time()

        try:
            # 1. Load topic configuration
            topic = self.topic_loader.get_topic(topic_id)
            if not topic:
                return TopicActivationResult(
                    success=False,
                    message=f"Topic not found: {topic_id}",
                    topic_id=topic_id,
                    error="TOPIC_NOT_FOUND"
                )

            # 2. Validate simulation state
            if not self.oasis_manager.is_ready:
                return TopicActivationResult(
                    success=False,
                    message=f"Simulation not ready. Current state: {self.oasis_manager.state.value}",
                    topic_id=topic_id,
                    error="SIMULATION_NOT_READY"
                )

            # 3. Validate posting agent exists
            posting_agent = self.oasis_manager.get_agent(topic.initial_post.agent_id)
            if not posting_agent:
                return TopicActivationResult(
                    success=False,
                    message=f"Posting agent not found: {topic.initial_post.agent_id}",
                    topic_id=topic_id,
                    error="AGENT_NOT_FOUND"
                )

            logger.info(f"Activating topic '{topic_id}' with agent {topic.initial_post.agent_id}")

            # 4. Execute initial post
            post_result = await self._execute_initial_post(topic, posting_agent)
            if not post_result["success"]:
                return TopicActivationResult(
                    success=False,
                    message=f"Failed to create initial post: {post_result['error']}",
                    topic_id=topic_id,
                    error=post_result["error"]
                )

            # 5. Refresh all agents if requested
            agents_refreshed = 0
            if topic.settings.trigger_refresh:
                refresh_result = await self._refresh_all_agents()
                agents_refreshed = refresh_result["count"]
                logger.info(f"Refreshed {agents_refreshed} agents after initial post")

            execution_time = time.time() - start_time

            logger.info(f"Topic '{topic_id}' activated successfully in {execution_time:.3f}s")

            return TopicActivationResult(
                success=True,
                message=f"Topic '{topic.name}' activated successfully",
                topic_id=topic_id,
                initial_post_created=True,
                agents_refreshed=agents_refreshed,
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Failed to activate topic '{topic_id}': {e}")
            execution_time = time.time() - start_time
            return TopicActivationResult(
                success=False,
                message=f"Topic activation failed: {str(e)}",
                topic_id=topic_id,
                error=str(e),
                execution_time=execution_time,
            )

    async def _execute_initial_post(
        self, topic: Topic, agent: SocialAgent
    ) -> Dict[str, Any]:
        """
        Execute the initial post for a topic

        Args:
            topic: Topic configuration
            agent: Agent that will post

        Returns:
            Result dictionary with success status
        """
        try:
            # Create ManualAction for initial post
            # Note: OASIS uses 'action_type' and 'action_args' parameters
            action = ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": topic.initial_post.content}
            )

            # Execute step with only the posting agent
            actions = {agent: action}
            result = await self.oasis_manager.step(
                actions,
                count_towards_budget=False,
            )

            if result["success"]:
                logger.info(
                    f"Initial post created by agent {agent.social_agent_id}: "
                    f'{topic.initial_post.content[:50]}...'
                )
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": "STEP_EXECUTION_FAILED"
                }

        except OASISStateError as e:
            logger.error(f"OASIS state error during initial post: {e}")
            return {"success": False, "error": "OASIS_STATE_ERROR"}
        except Exception as e:
            logger.error(f"Failed to execute initial post: {e}")
            return {"success": False, "error": str(e)}

    async def _refresh_all_agents(self) -> Dict[str, Any]:
        """
        Execute REFRESH action for all agents

        Returns:
            Result dictionary with count of refreshed agents
        """
        try:
            # Get all agents
            all_agents = self.oasis_manager.get_all_agents()

            if not all_agents:
                logger.warning("No agents to refresh")
                return {"count": 0}

            # Create REFRESH actions for all agents
            refresh_actions = {
                agent: ManualAction(
                    action_type=ActionType.REFRESH,
                    action_args={}
                )
                for agent in all_agents
            }

            # Execute refresh step
            result = await self.oasis_manager.step(
                refresh_actions,
                count_towards_budget=False,
            )

            if result["success"]:
                logger.info(f"Refreshed {len(all_agents)} agents")
                return {"count": len(all_agents)}
            else:
                logger.warning(f"Refresh step failed: {result}")
                return {"count": 0}

        except Exception as e:
            logger.error(f"Failed to refresh agents: {e}")
            return {"count": 0}

    # ========================================================================
    # Topic Query
    # ========================================================================

    def list_topics(self) -> List[TopicListItem]:
        """
        Get all available topics

        Returns:
            List of topic items
        """
        topics = self.topic_loader.list_topics()

        return [
            TopicListItem(
                id=topic.id,
                name=topic.name,
                description=topic.description,
                has_initial_post=True,
                settings_trigger_refresh=topic.settings.trigger_refresh,
            )
            for topic in topics
        ]

    def get_topic(self, topic_id: str) -> Optional[TopicDetail]:
        """
        Get detailed information about a specific topic

        Args:
            topic_id: Topic identifier

        Returns:
            Topic detail or None if not found
        """
        topic = self.topic_loader.get_topic(topic_id)

        if not topic:
            return None

        # All topics are available regardless of platform
        available = True

        return TopicDetail(
            id=topic.id,
            name=topic.name,
            description=topic.description,
            initial_post=topic.initial_post,
            settings=topic.settings,
            available=available,
        )

    def get_topic_count(self) -> int:
        """Get total number of topics"""
        return self.topic_loader.count()

    def topic_exists(self, topic_id: str) -> bool:
        """Check if a topic exists"""
        return self.topic_loader.exists(topic_id)

    # ========================================================================
    # Configuration Management
    # ========================================================================

    async def reload_config(self) -> TopicReloadResult:
        """
        Reload topic configuration from disk

        Returns:
            Reload result with statistics
        """
        try:
            start_time = time.time()
            result = self.topic_loader.reload()
            reload_time = time.time() - start_time

            return TopicReloadResult(
                success=result["success"],
                message=result["message"],
                topics_loaded=result["topics_loaded"],
                reload_time=reload_time,
            )

        except TopicLoadError as e:
            logger.error(f"Failed to reload topic config: {e}")
            return TopicReloadResult(
                success=False,
                message=f"Reload failed: {str(e)}",
                topics_loaded=0,
            )
        except Exception as e:
            logger.error(f"Unexpected error during reload: {e}")
            return TopicReloadResult(
                success=False,
                message=f"Unexpected error: {str(e)}",
                topics_loaded=0,
            )

    # ========================================================================
    # Validation
    # ========================================================================

    def validate_topic_for_simulation(self, topic_id: str) -> Dict[str, Any]:
        """
        Validate if a topic can be activated in the current simulation

        Args:
            topic_id: Topic identifier

        Returns:
            Validation result with any issues found
        """
        issues = []

        # Check topic exists
        if not self.topic_loader.exists(topic_id):
            issues.append("Topic does not exist")
            return {"valid": False, "issues": issues}

        topic = self.topic_loader.get_topic(topic_id)

        # Check simulation state
        if not self.oasis_manager.is_initialized:
            issues.append("Simulation not initialized")

        # Check posting agent exists
        if not self.oasis_manager.get_agent(topic.initial_post.agent_id):
            issues.append(f"Posting agent {topic.initial_post.agent_id} not found")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }
