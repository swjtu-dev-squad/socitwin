"""
Probabilistic Engine - Action selection based on probability distributions

This module implements probabilistic action selection for agents based on
configured probability distributions, with support for conditional probabilities
and platform-specific action filtering.
"""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

# OASIS framework imports
from oasis import ActionType, ManualAction, SocialAgent

# Local imports
from app.models.behavior import BehaviorContext, ProbabilityDistribution
from app.models.simulation import OASISActionType, PlatformType

logger = logging.getLogger(__name__)


class ProbabilisticEngineError(Exception):
    """Probabilistic engine error base class"""

    pass


class NoValidActionsError(ProbabilisticEngineError):
    """No valid actions available error"""

    pass


class ProbabilisticEngine:
    """
    Probabilistic action selection engine

    Responsibilities:
    - Select actions based on probability distributions
    - Filter actions by platform compatibility
    - Handle conditional probabilities
    - Generate appropriate action arguments
    """

    def __init__(self, platform: PlatformType):
        """
        Initialize probabilistic engine

        Args:
            platform: Platform type (Twitter/Reddit)
        """
        self.platform = platform
        self._available_actions = self._load_platform_actions(platform)
        self._default_action_args = self._load_default_action_args(platform)

        # Statistics
        self.action_selection_counts: Dict[str, int] = {}
        self.total_selections = 0

        logger.info(f"Probabilistic Engine initialized for {platform.value}")

    # ========================================================================
    # Public API
    # ========================================================================

    async def select_action(
        self, agent: SocialAgent, distribution: ProbabilityDistribution, context: BehaviorContext
    ) -> ManualAction:
        """
        Select action based on probability distribution

        Args:
            agent: The agent
            distribution: Probability distribution
            context: Behavior context

        Returns:
            ManualAction with selected action

        Raises:
            NoValidActionsError: If no valid actions available
        """
        try:
            # Get available actions for this agent/context
            available_actions = self._get_available_actions(agent, context)

            if not available_actions:
                raise NoValidActionsError("No actions available for agent")

            # Filter and weight actions based on distribution
            weighted_actions = self._apply_distribution(distribution, available_actions, context)

            if not weighted_actions:
                raise NoValidActionsError("No actions after applying distribution")

            # Select action using weighted random choice
            selected_action_type, selected_probability = self._weighted_random_choice(
                weighted_actions
            )

            # Generate action arguments
            action_args = self._generate_action_args(selected_action_type, agent, context)

            # Update statistics
            self._update_statistics(selected_action_type.value)

            logger.debug(
                f"Agent {agent.social_agent_id} selected {selected_action_type.value} "
                f"(probability: {selected_probability:.3f})"
            )

            # Create and return ManualAction
            return ManualAction(
                action_type=getattr(ActionType, selected_action_type.value), action_args=action_args
            )

        except NoValidActionsError as e:
            logger.warning(f"No valid actions for agent {agent.social_agent_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to select action for agent {agent.social_agent_id}: {e}")
            raise ProbabilisticEngineError(f"Action selection failed: {str(e)}")

    async def batch_select_actions(
        self,
        agents: List[SocialAgent],
        distribution: ProbabilityDistribution,
        context: BehaviorContext,
    ) -> Dict[SocialAgent, ManualAction]:
        """
        Select actions for multiple agents

        Args:
            agents: List of agents
            distribution: Probability distribution
            context: Behavior context

        Returns:
            Dictionary mapping agents to their actions
        """
        actions = {}

        for agent in agents:
            try:
                action = await self.select_action(agent, distribution, context)
                actions[agent] = action
            except Exception as e:
                logger.error(f"Failed to select action for agent {agent.social_agent_id}: {e}")
                # Skip this agent

        return actions

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine statistics

        Returns:
            Statistics dictionary
        """
        total = self.total_selections

        # Calculate percentages
        percentages = {}
        for action_type, count in self.action_selection_counts.items():
            percentage = (count / total * 100) if total > 0 else 0
            percentages[action_type] = round(percentage, 2)

        return {
            "total_selections": total,
            "action_counts": self.action_selection_counts,
            "percentages": percentages,
            "platform": self.platform.value,
        }

    def reset_statistics(self) -> None:
        """Reset engine statistics"""
        self.action_selection_counts.clear()
        self.total_selections = 0
        logger.info("Probabilistic engine statistics reset")

    # ========================================================================
    # Distribution Application
    # ========================================================================

    def _apply_distribution(
        self,
        distribution: ProbabilityDistribution,
        available_actions: List[OASISActionType],
        context: BehaviorContext,
    ) -> List[Tuple[OASISActionType, float]]:
        """
        Apply probability distribution to available actions

        Args:
            distribution: Probability distribution
            available_actions: List of available action types
            context: Behavior context

        Returns:
            List of (action_type, probability) tuples
        """
        weighted_actions = []

        # Apply each probability rule
        for action_prob in distribution.actions:
            action_type = action_prob.action_type

            # Check if action is available
            if action_type not in available_actions:
                continue

            # Check conditions
            if not self._check_conditions(action_prob.conditions, context):
                continue

            # Add to weighted list
            weighted_actions.append((action_type, action_prob.probability))

        # If no weighted actions from distribution, use equal distribution
        if not weighted_actions:
            equal_prob = 1.0 / len(available_actions)
            for action_type in available_actions:
                weighted_actions.append((action_type, equal_prob))

        # Normalize probabilities
        weighted_actions = self._normalize_probabilities(weighted_actions)

        return weighted_actions

    def _check_conditions(
        self, conditions: Optional[Dict[str, Any]], context: BehaviorContext
    ) -> bool:
        """
        Check if conditions are met

        Args:
            conditions: Conditions dictionary
            context: Behavior context

        Returns:
            True if conditions met or no conditions, False otherwise
        """
        if not conditions:
            return True

        context_dict = context.model_dump()

        for key, value in conditions.items():
            # Check if key exists in context
            if key not in context_dict:
                return False

            # Compare values
            if context_dict[key] != value:
                return False

        return True

    # ========================================================================
    # Action Selection
    # ========================================================================

    def _weighted_random_choice(
        self, weighted_actions: List[Tuple[OASISActionType, float]]
    ) -> Tuple[OASISActionType, float]:
        """
        Select action using weighted random choice

        Args:
            weighted_actions: List of (action_type, probability)

        Returns:
            Selected (action_type, probability)
        """
        # Extract actions and probabilities
        actions, probabilities = zip(*weighted_actions)

        # Make selection
        selected_index = random.choices(range(len(actions)), weights=probabilities, k=1)[0]

        return actions[selected_index], probabilities[selected_index]

    def _normalize_probabilities(
        self, weighted_actions: List[Tuple[OASISActionType, float]]
    ) -> List[Tuple[OASISActionType, float]]:
        """
        Normalize probabilities to sum to 1.0

        Args:
            weighted_actions: List of (action_type, probability)

        Returns:
            Normalized list
        """
        if not weighted_actions:
            return weighted_actions

        total = sum(prob for _, prob in weighted_actions)

        if total == 0:
            # Equal distribution
            equal_prob = 1.0 / len(weighted_actions)
            return [(action, equal_prob) for action, _ in weighted_actions]

        # Normalize
        normalized = []
        for action, prob in weighted_actions:
            normalized_prob = prob / total
            normalized.append((action, normalized_prob))

        return normalized

    # ========================================================================
    # Action Availability and Arguments
    # ========================================================================

    def _get_available_actions(
        self, agent: SocialAgent, context: BehaviorContext
    ) -> List[OASISActionType]:
        """
        Get available actions for agent

        Args:
            agent: The agent
            context: Behavior context

        Returns:
            List of available action types
        """
        # Start with platform-specific actions
        available = list(self._available_actions)

        # Filter based on agent state (optional)
        # For example, can't LIKE_POST if haven't seen any posts
        # This is a simplified version - can be extended

        # Filter out actions that require specific conditions
        filtered_actions = []
        for action in available:
            if self._is_action_available(action, agent, context):
                filtered_actions.append(action)

        return filtered_actions

    def _is_action_available(
        self, action_type: OASISActionType, agent: SocialAgent, context: BehaviorContext
    ) -> bool:
        """
        Check if an action is available for the agent

        Args:
            action_type: Action type to check
            agent: The agent
            context: Behavior context

        Returns:
            True if action is available
        """
        # Basic availability checks
        # These can be extended based on agent state and context

        if action_type == OASISActionType.CREATE_POST:
            # Always available to create posts
            return True

        elif action_type in [
            OASISActionType.LIKE_POST,
            OASISActionType.DISLIKE_POST,
            OASISActionType.CREATE_COMMENT,
            OASISActionType.QUOTE_POST,
        ]:
            # Need to have posts in feed
            # Simplified check - in real implementation would check agent's feed
            return context.current_step > 0  # Assume posts exist after step 0

        elif action_type == OASISActionType.REFRESH:
            # Always available
            return True

        elif action_type == OASISActionType.DO_NOTHING:
            # Always available
            return True

        # For other actions, assume available
        return True

    def _generate_action_args(
        self, action_type: OASISActionType, agent: SocialAgent, context: BehaviorContext
    ) -> Dict[str, Any]:
        """
        Generate action arguments for selected action

        Args:
            action_type: Selected action type
            agent: The agent
            context: Behavior context

        Returns:
            Action arguments dictionary
        """
        # Get default arguments for this action type
        args = self._default_action_args.get(action_type.value, {}).copy()

        # Customize based on action type
        if action_type == OASISActionType.CREATE_POST:
            args = self._generate_post_content(agent, context)

        elif action_type == OASISActionType.CREATE_COMMENT:
            args = self._generate_comment_content(agent, context)

        elif action_type == OASISActionType.QUOTE_POST:
            args = self._generate_quote_content(agent, context)

        # Add agent context
        args["agent_id"] = agent.social_agent_id
        args["step"] = context.current_step

        return args

    def _generate_post_content(
        self, agent: SocialAgent, context: BehaviorContext
    ) -> Dict[str, Any]:
        """
        Generate content for a post

        Args:
            agent: The agent
            context: Behavior context

        Returns:
            Content arguments
        """
        # Simplified content generation
        # In real implementation, could use templates or LLM
        topics = ["technology", "politics", "entertainment", "sports", "science"]
        topic = random.choice(topics)

        templates = [
            f"Just thinking about {topic}...",
            f"My take on {topic}: it's more complex than people think.",
            f"Interesting developments in {topic} recently.",
            f"Does anyone else have thoughts about {topic}?",
        ]

        content = random.choice(templates)

        return {
            "content": content,
            "topic": topic,
            "sentiment": random.choice(["positive", "neutral", "negative"]),
        }

    def _generate_comment_content(
        self, agent: SocialAgent, context: BehaviorContext
    ) -> Dict[str, Any]:
        """
        Generate content for a comment

        Args:
            agent: The agent
            context: Behavior context

        Returns:
            Content arguments
        """
        responses = [
            "Interesting perspective!",
            "I agree with this.",
            "I see it differently.",
            "Thanks for sharing!",
            "This is worth discussing further.",
            "I have a similar experience.",
        ]

        content = random.choice(responses)

        return {
            "content": content,
            "post_id": self._get_random_post_id(context),  # Would need real post ID
        }

    def _generate_quote_content(
        self, agent: SocialAgent, context: BehaviorContext
    ) -> Dict[str, Any]:
        """
        Generate content for a quote post

        Args:
            agent: The agent
            context: Behavior context

        Returns:
            Content arguments
        """
        comments = [
            "This is spot on!",
            "Sharing this important perspective.",
            "Wanted to highlight this point.",
            "Adding my thoughts to this discussion.",
        ]

        content = random.choice(comments)

        return {
            "content": content,
            "original_post_id": self._get_random_post_id(context),
            "add_comment": True,
        }

    def _get_random_post_id(self, context: BehaviorContext) -> int:
        """
        Get a random post ID (simplified)

        Args:
            context: Behavior context

        Returns:
            Random post ID
        """
        # In real implementation, would query database for available posts
        # For now, return a random number
        return random.randint(1, 100)

    # ========================================================================
    # Platform Configuration
    # ========================================================================

    def _load_platform_actions(self, platform: PlatformType) -> List[OASISActionType]:
        """
        Load available actions for platform

        Args:
            platform: Platform type

        Returns:
            List of available action types
        """
        from oasis import ActionType

        # Platform-specific action sets
        if platform == PlatformType.TWITTER:
            twitter_actions = [
                OASISActionType.CREATE_POST,
                OASISActionType.CREATE_COMMENT,
                OASISActionType.LIKE_POST,
                OASISActionType.REPOST,
                OASISActionType.QUOTE_POST,
                OASISActionType.FOLLOW,
                OASISActionType.REFRESH,
                OASISActionType.DO_NOTHING,
            ]
            # Filter to actions that exist in OASIS
            available = []
            for action in twitter_actions:
                try:
                    getattr(ActionType, action.value)
                    available.append(action)
                except AttributeError:
                    logger.debug(f"Action {action.value} not available in OASIS for Twitter")
            return available

        elif platform == PlatformType.REDDIT:
            reddit_actions = [
                OASISActionType.CREATE_POST,
                OASISActionType.CREATE_COMMENT,
                OASISActionType.LIKE_POST,
                OASISActionType.DISLIKE_POST,
                OASISActionType.REFRESH,
                OASISActionType.DO_NOTHING,
            ]
            # Filter to actions that exist in OASIS
            available = []
            for action in reddit_actions:
                try:
                    getattr(ActionType, action.value)
                    available.append(action)
                except AttributeError:
                    logger.debug(f"Action {action.value} not available in OASIS for Reddit")
            return available

        else:
            logger.warning(f"Unknown platform: {platform}, using default actions")
            return [
                OASISActionType.CREATE_POST,
                OASISActionType.CREATE_COMMENT,
                OASISActionType.LIKE_POST,
                OASISActionType.REFRESH,
                OASISActionType.DO_NOTHING,
            ]

    def _load_default_action_args(self, platform: PlatformType) -> Dict[str, Dict[str, Any]]:
        """
        Load default action arguments for platform

        Args:
            platform: Platform type

        Returns:
            Dictionary mapping action types to default arguments
        """
        defaults = {
            OASISActionType.CREATE_POST.value: {
                "content": "Default post content",
                "platform": platform.value,
            },
            OASISActionType.CREATE_COMMENT.value: {
                "content": "Default comment",
                "platform": platform.value,
            },
            OASISActionType.LIKE_POST.value: {
                "platform": platform.value,
            },
            OASISActionType.DISLIKE_POST.value: {
                "platform": platform.value,
            },
            OASISActionType.REPOST.value: {
                "platform": platform.value,
            },
            OASISActionType.QUOTE_POST.value: {
                "content": "Quoting this post",
                "platform": platform.value,
            },
            OASISActionType.FOLLOW.value: {
                "platform": platform.value,
            },
            OASISActionType.REFRESH.value: {
                "platform": platform.value,
            },
            OASISActionType.DO_NOTHING.value: {
                "platform": platform.value,
            },
        }

        return defaults

    # ========================================================================
    # Statistics
    # ========================================================================

    def _update_statistics(self, action_type: str) -> None:
        """
        Update selection statistics

        Args:
            action_type: Selected action type
        """
        self.total_selections += 1

        if action_type not in self.action_selection_counts:
            self.action_selection_counts[action_type] = 0
        self.action_selection_counts[action_type] += 1

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_available_action_types(self) -> List[str]:
        """
        Get list of available action types

        Returns:
            List of action type names
        """
        return [action.value for action in self._available_actions]


# ========================================================================
# Factory Function
# ========================================================================

_probabilistic_engines = {}


def get_probabilistic_engine(platform: PlatformType) -> ProbabilisticEngine:
    """
    Get probabilistic engine for platform (singleton per platform)

    Args:
        platform: Platform type

    Returns:
        ProbabilisticEngine instance
    """
    global _probabilistic_engines

    if platform not in _probabilistic_engines:
        _probabilistic_engines[platform] = ProbabilisticEngine(platform)
        logger.info(f"Probabilistic Engine for {platform.value} created")

    return _probabilistic_engines[platform]


def reset_probabilistic_engines() -> None:
    """Reset all probabilistic engines (mainly for testing)"""
    global _probabilistic_engines
    _probabilistic_engines.clear()
    logger.info("Probabilistic engines reset")
