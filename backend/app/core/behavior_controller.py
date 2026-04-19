"""
Behavior Controller - Core module for agent behavior decision making

This module coordinates different behavior decision engines (probabilistic, rule-based, scheduled)
and integrates with the existing LLM autonomous decision system.
"""

import logging
import random
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

# OASIS framework imports
from oasis import SocialAgent, LLMAction, ManualAction, ActionType

# Local imports
from app.core.oasis_manager import OASISManager
from app.models.behavior import (
    AgentBehaviorConfig,
    BehaviorStrategy,
    BehaviorContext,
    create_default_behavior_config
)
from app.models.simulation import PlatformType, OASISActionType

logger = logging.getLogger(__name__)


class BehaviorControllerError(Exception):
    """Behavior controller error base class"""
    pass


class BehaviorDecisionError(BehaviorControllerError):
    """Error during behavior decision making"""
    pass


class StrategyNotImplementedError(BehaviorControllerError):
    """Strategy not implemented error"""
    pass


class BehaviorController:
    """
    Central behavior decision controller

    Responsibilities:
    - Coordinate behavior decision for agents based on their configured strategy
    - Integrate with probabilistic, rule-based, and scheduling engines
    - Maintain agent behavior state and context
    - Provide fallback to LLM autonomous decisions
    """

    def __init__(self, oasis_manager: OASISManager):
        """
        Initialize behavior controller

        Args:
            oasis_manager: OASIS manager instance
        """
        self.oasis_manager = oasis_manager

        # Initialize strategy engines
        try:
            from app.core.probabilistic_engine import ProbabilisticEngine
            from app.core.rule_engine import RuleEngine
            from app.core.scheduling_engine import SchedulingEngine

            platform = self.oasis_manager._platform_type
            self._probabilistic_engine = ProbabilisticEngine(platform)
            self._rule_engine = RuleEngine([])  # Empty rule set initially
            self._scheduling_engine = SchedulingEngine()
        except ImportError as e:
            logger.warning(f"Failed to import behavior engines: {e}")
            self._probabilistic_engine = None
            self._rule_engine = None
            self._scheduling_engine = None
        except Exception as e:
            logger.warning(f"Failed to initialize behavior engines: {e}")
            self._probabilistic_engine = None
            self._rule_engine = None
            self._scheduling_engine = None

        # Agent behavior state tracking
        self.agent_behavior_state: Dict[int, Dict[str, Any]] = {}

        # Strategy execution counters
        self.strategy_counts: Dict[BehaviorStrategy, int] = {
            BehaviorStrategy.LLM_AUTONOMOUS: 0,
            BehaviorStrategy.PROBABILISTIC: 0,
            BehaviorStrategy.RULE_BASED: 0,
            BehaviorStrategy.SCHEDULED: 0,
            BehaviorStrategy.MIXED: 0,
        }

        logger.info("Behavior Controller initialized")

    # ========================================================================
    # Public API - Core Decision Making
    # ========================================================================

    async def decide_action(
        self,
        agent: SocialAgent,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[LLMAction, ManualAction]:
        """
        Decide action for an agent based on its behavior configuration

        Args:
            agent: The agent to decide action for
            context: Optional context information for decision making

        Returns:
            Either LLMAction (for autonomous) or ManualAction (for controlled)

        Raises:
            BehaviorDecisionError: If decision making fails
        """
        agent_id = agent.social_agent_id

        try:
            # Get agent behavior configuration
            behavior_config = await self._get_agent_behavior_config(agent)

            # Check if configuration is active
            if not behavior_config.enabled:
                logger.debug(f"Behavior config disabled for agent {agent_id}, using LLM autonomous")
                return LLMAction()

            # Build context
            behavior_context = self._build_behavior_context(agent, context)

            # Check configuration conditions
            if not behavior_config.is_active(behavior_context.dict()):
                logger.debug(f"Behavior config not active for agent {agent_id}, using LLM autonomous")
                return LLMAction()

            # Make decision based on strategy
            decision = await self._make_decision(agent, behavior_config, behavior_context)

            # Update strategy counters
            self.strategy_counts[behavior_config.strategy] += 1

            # Update agent state
            self._update_agent_state(agent_id, behavior_config.strategy, decision)

            logger.debug(f"Agent {agent_id} decision: {behavior_config.strategy} -> {type(decision).__name__}")
            return decision

        except Exception as e:
            logger.error(f"Failed to decide action for agent {agent_id}: {e}")
            # Fallback to LLM autonomous
            return LLMAction()

    async def batch_decide_actions(
        self,
        agents: List[SocialAgent],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[SocialAgent, Union[LLMAction, ManualAction]]:
        """
        Decide actions for multiple agents

        Args:
            agents: List of agents
            context: Optional context information

        Returns:
            Dictionary mapping agents to their actions
        """
        actions = {}

        for agent in agents:
            action = await self.decide_action(agent, context)
            actions[agent] = action

        return actions

    # ========================================================================
    # Configuration Management
    # ========================================================================

    async def update_agent_behavior(
        self,
        agent_id: int,
        behavior_config: AgentBehaviorConfig
    ) -> bool:
        """
        Update behavior configuration for an agent

        Args:
            agent_id: Agent ID
            behavior_config: New behavior configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get agent
            agent = self.oasis_manager.get_agent(agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return False

            # Store configuration in agent state
            if agent_id not in self.agent_behavior_state:
                self.agent_behavior_state[agent_id] = {}

            self.agent_behavior_state[agent_id]['config'] = behavior_config
            self.agent_behavior_state[agent_id]['updated_at'] = datetime.now()

            logger.info(f"Updated behavior config for agent {agent_id}: {behavior_config.strategy}")
            return True

        except Exception as e:
            logger.error(f"Failed to update behavior for agent {agent_id}: {e}")
            return False

    async def get_agent_behavior(
        self,
        agent_id: int
    ) -> Optional[AgentBehaviorConfig]:
        """
        Get behavior configuration for an agent

        Args:
            agent_id: Agent ID

        Returns:
            Behavior configuration or None if not found
        """
        try:
            agent = self.oasis_manager.get_agent(agent_id)
            if not agent:
                return None

            return await self._get_agent_behavior_config(agent)

        except Exception as e:
            logger.error(f"Failed to get behavior for agent {agent_id}: {e}")
            return None

    def get_strategy_stats(self, use_configuration: bool = False) -> Dict[BehaviorStrategy, Dict[str, Any]]:
        """
        Get statistics about strategy usage

        Args:
            use_configuration: If True, return statistics based on agent configurations
                              If False, return statistics based on execution counts

        Returns:
            Dictionary with strategy statistics
        """
        if use_configuration:
            return self._get_config_based_strategy_stats()

        total = sum(self.strategy_counts.values())

        # If no strategy execution counts yet, fall back to configuration-based statistics
        if total == 0:
            return self._get_config_based_strategy_stats()

        stats = {}
        for strategy, count in self.strategy_counts.items():
            percentage = (count / total * 100) if total > 0 else 0
            stats[strategy] = {
                "count": count,
                "percentage": round(percentage, 2),
                "last_updated": datetime.now()
            }

        return stats

    def _get_config_based_strategy_stats(self) -> Dict[BehaviorStrategy, Dict[str, Any]]:
        """
        Get strategy statistics based on agent configurations when no execution data exists

        Returns:
            Dictionary with strategy statistics based on configurations
        """
        config_counts = {strategy: 0 for strategy in BehaviorStrategy}
        total_configs = 0

        # Count strategies from agent configurations
        for agent_id, state in self.agent_behavior_state.items():
            config = state.get('config')
            if config:
                strategy = config.strategy
                config_counts[strategy] = config_counts.get(strategy, 0) + 1
                total_configs += 1

        # If no configurations found, return zero counts for all strategies
        if total_configs == 0:
            stats = {}
            for strategy in BehaviorStrategy:
                stats[strategy] = {
                    "count": 0,
                    "percentage": 0.0,
                    "last_updated": datetime.now()
                }
            return stats

        # Calculate percentages
        stats = {}
        for strategy, count in config_counts.items():
            percentage = (count / total_configs * 100) if total_configs > 0 else 0
            stats[strategy] = {
                "count": count,
                "percentage": round(percentage, 2),
                "last_updated": datetime.now()
            }

        return stats

    # ========================================================================
    # Strategy Decision Implementations
    # ========================================================================

    async def _make_decision(
        self,
        agent: SocialAgent,
        config: AgentBehaviorConfig,
        context: BehaviorContext
    ) -> Union[LLMAction, ManualAction]:
        """
        Make decision based on strategy

        Args:
            agent: The agent
            config: Behavior configuration
            context: Behavior context

        Returns:
            Action decision
        """
        strategy = config.strategy

        if strategy == BehaviorStrategy.LLM_AUTONOMOUS:
            return await self._llm_autonomous_decision(agent, config, context)

        elif strategy == BehaviorStrategy.PROBABILISTIC:
            return await self._probabilistic_decision(agent, config, context)

        elif strategy == BehaviorStrategy.RULE_BASED:
            return await self._rule_based_decision(agent, config, context)

        elif strategy == BehaviorStrategy.SCHEDULED:
            return await self._scheduled_decision(agent, config, context)

        elif strategy == BehaviorStrategy.MIXED:
            return await self._mixed_decision(agent, config, context)

        else:
            raise StrategyNotImplementedError(f"Strategy not implemented: {strategy}")

    async def _llm_autonomous_decision(
        self,
        agent: SocialAgent,
        config: AgentBehaviorConfig,
        context: BehaviorContext
    ) -> LLMAction:
        """
        LLM autonomous decision (original behavior)

        Args:
            agent: The agent
            config: Behavior configuration
            context: Behavior context

        Returns:
            LLMAction for autonomous decision
        """
        # Simple LLM action - OASIS will handle the actual LLM decision
        return LLMAction()

    async def _probabilistic_decision(
        self,
        agent: SocialAgent,
        config: AgentBehaviorConfig,
        context: BehaviorContext
    ) -> ManualAction:
        """
        Probabilistic decision based on configured distribution

        Args:
            agent: The agent
            config: Behavior configuration
            context: Behavior context

        Returns:
            ManualAction based on probability distribution
        """
        try:
            from app.core.probabilistic_engine import ProbabilisticEngine

            # Get or create probabilistic engine
            if self._probabilistic_engine is None:
                platform = self.oasis_manager._platform_type
                self._probabilistic_engine = ProbabilisticEngine(platform)

            # Get probability distribution
            distribution = config.probability_distribution
            if not distribution:
                logger.warning(f"No probability distribution for agent {agent.social_agent_id}, using LLM autonomous")
                return LLMAction()

            # Let probabilistic engine decide
            return await self._probabilistic_engine.select_action(
                agent=agent,
                distribution=distribution,
                context=context
            )

        except ImportError:
            logger.error("Probabilistic engine not available, using LLM autonomous")
            return LLMAction()
        except Exception as e:
            logger.error(f"Probabilistic decision failed: {e}, using LLM autonomous")
            return LLMAction()

    async def _rule_based_decision(
        self,
        agent: SocialAgent,
        config: AgentBehaviorConfig,
        context: BehaviorContext
    ) -> Union[LLMAction, ManualAction]:
        """
        Rule-based decision

        Args:
            agent: The agent
            config: Behavior configuration
            context: Behavior context

        Returns:
            ManualAction if rule triggers, otherwise LLMAction
        """
        try:
            from app.core.rule_engine import RuleEngine

            # Get rule set
            rule_set = config.rule_set
            if not rule_set or not rule_set.rules:
                logger.debug(f"No rules for agent {agent.social_agent_id}, using LLM autonomous")
                return LLMAction()

            # Get or create rule engine
            if self._rule_engine is None:
                self._rule_engine = RuleEngine(rule_set.rules)
            else:
                # Update rules if needed
                self._rule_engine.update_rules(rule_set.rules)

            # Evaluate rules
            action = await self._rule_engine.evaluate_rules(agent, context)

            if action:
                return action
            else:
                # No rule triggered, use LLM autonomous
                logger.debug(f"No rules triggered for agent {agent.social_agent_id}, using LLM autonomous")
                return LLMAction()

        except ImportError:
            logger.error("Rule engine not available, using LLM autonomous")
            return LLMAction()
        except Exception as e:
            logger.error(f"Rule-based decision failed: {e}, using LLMAction")
            return LLMAction()

    async def _scheduled_decision(
        self,
        agent: SocialAgent,
        config: AgentBehaviorConfig,
        context: BehaviorContext
    ) -> Union[LLMAction, ManualAction]:
        """
        Scheduled decision based on timeline

        Args:
            agent: The agent
            config: Behavior configuration
            context: Behavior context

        Returns:
            ManualAction if scheduled event exists, otherwise LLMAction
        """
        try:
            from app.core.scheduling_engine import SchedulingEngine

            # Get schedule
            schedule = config.schedule
            if not schedule or not schedule.timeline:
                logger.debug(f"No schedule for agent {agent.social_agent_id}, using LLMAction")
                return LLMAction()

            # Get or create scheduling engine
            if self._scheduling_engine is None:
                self._scheduling_engine = SchedulingEngine()

            # Get scheduled action for current step
            action = await self._scheduling_engine.get_scheduled_action(
                agent_id=agent.social_agent_id,
                schedule=schedule,
                current_step=context.current_step
            )

            if action:
                return action
            else:
                # No scheduled event for this step, use LLMAction
                logger.debug(f"No scheduled event for agent {agent.social_agent_id} at step {context.current_step}, using LLMAction")
                return LLMAction()

        except ImportError:
            logger.error("Scheduling engine not available, using LLMAction")
            return LLMAction()
        except Exception as e:
            logger.error(f"Scheduled decision failed: {e}, using LLMAction")
            return LLMAction()

    async def _mixed_decision(
        self,
        agent: SocialAgent,
        config: AgentBehaviorConfig,
        context: BehaviorContext
    ) -> Union[LLMAction, ManualAction]:
        """
        Mixed strategy decision

        Args:
            agent: The agent
            config: Behavior configuration
            context: Behavior context

        Returns:
            Action based on mixed strategy
        """
        try:
            mixed_config = config.mixed_strategy
            if not mixed_config or not mixed_config.strategy_weights:
                logger.warning(f"No mixed strategy config for agent {agent.social_agent_id}, using LLMAction")
                return LLMAction()

            # Select strategy based on weights
            strategies = [weight.strategy for weight in mixed_config.strategy_weights]
            weights = [weight.weight for weight in mixed_config.strategy_weights]

            selected_strategy = random.choices(strategies, weights=weights, k=1)[0]

            # Create temporary config with selected strategy
            temp_config = config.copy()
            temp_config.strategy = selected_strategy

            # Make decision with selected strategy
            return await self._make_decision(agent, temp_config, context)

        except Exception as e:
            logger.error(f"Mixed decision failed: {e}, using LLMAction")
            return LLMAction()

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_agent_behavior_config(
        self,
        agent: SocialAgent
    ) -> AgentBehaviorConfig:
        """
        Get behavior configuration for an agent

        Args:
            agent: The agent

        Returns:
            Behavior configuration
        """
        agent_id = agent.social_agent_id

        # Check if we have stored configuration
        if agent_id in self.agent_behavior_state:
            state = self.agent_behavior_state[agent_id]
            if 'config' in state:
                return state['config']

        # Try to get from agent user info profile
        try:
            profile = getattr(agent.user_info, 'profile', None)
            if profile and 'behavior_config' in profile:
                # Parse from profile
                import json
                config_dict = profile['behavior_config']
                if isinstance(config_dict, str):
                    config_dict = json.loads(config_dict)

                from app.models.behavior import AgentBehaviorConfig
                return AgentBehaviorConfig(**config_dict)
        except Exception as e:
            logger.debug(f"Failed to parse behavior config from profile: {e}")

        # Return default configuration
        return create_default_behavior_config()

    def _build_behavior_context(
        self,
        agent: SocialAgent,
        external_context: Optional[Dict[str, Any]] = None
    ) -> BehaviorContext:
        """
        Build behavior context for decision making

        Args:
            agent: The agent
            external_context: External context information

        Returns:
            BehaviorContext object
        """
        from app.models.behavior import BehaviorContext

        # Base context
        context_dict = {
            'current_step': self.oasis_manager._current_step,
            'platform': self.oasis_manager._platform_type,
            'agent_id': agent.social_agent_id,
            'agent_state': self._get_agent_state(agent),
            'simulation_state': self.oasis_manager.get_state_info(),
            'recent_actions': self._get_recent_actions(agent.social_agent_id),
            'timestamp': datetime.now(),
            # Probability bucket for rule-based probabilistic behavior (0-99)
            'probability_bucket': (agent.social_agent_id + self.oasis_manager._current_step) % 100,
        }

        # Merge external context
        if external_context:
            context_dict.update(external_context)

        return BehaviorContext(**context_dict)

    def _get_agent_state(self, agent: SocialAgent) -> Dict[str, Any]:
        """
        Get current agent state

        Args:
            agent: The agent

        Returns:
            Agent state dictionary
        """
        # This is a simplified version - can be extended with more state info
        agent_id = agent.social_agent_id

        state = {
            'id': agent_id,
            'user_name': agent.user_info.user_name,
            'name': agent.user_info.name,
            'description': agent.user_info.description,
        }

        # Add behavior state if available
        if agent_id in self.agent_behavior_state:
            state.update(self.agent_behavior_state[agent_id])

        return state

    def _get_recent_actions(self, agent_id: int) -> List[Dict[str, Any]]:
        """
        Get recent actions for an agent

        Args:
            agent_id: Agent ID

        Returns:
            List of recent actions
        """
        # Simplified - would need integration with OASIS trace database
        # For now, return empty list
        return []

    def _update_agent_state(
        self,
        agent_id: int,
        strategy: BehaviorStrategy,
        decision: Union[LLMAction, ManualAction]
    ) -> None:
        """
        Update agent behavior state

        Args:
            agent_id: Agent ID
            strategy: Strategy used
            decision: Decision made
        """
        if agent_id not in self.agent_behavior_state:
            self.agent_behavior_state[agent_id] = {}

        state = self.agent_behavior_state[agent_id]
        state['last_strategy'] = strategy
        state['last_decision'] = type(decision).__name__
        state['last_decision_time'] = datetime.now()

        # Track decision count
        if 'decision_count' not in state:
            state['decision_count'] = 0
        state['decision_count'] += 1

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def reset_stats(self) -> None:
        """Reset strategy statistics"""
        for strategy in self.strategy_counts:
            self.strategy_counts[strategy] = 0
        logger.info("Behavior controller stats reset")

    def clear_agent_states(self) -> None:
        """Clear all agent behavior states"""
        self.agent_behavior_state.clear()
        logger.info("Agent behavior states cleared")


# ============================================================================
# Factory Function
# ============================================================================

_behavior_controller = None


async def get_behavior_controller(
    oasis_manager: Optional[OASISManager] = None
) -> BehaviorController:
    """
    Get behavior controller instance (singleton pattern)

    Args:
        oasis_manager: Optional OASIS manager instance

    Returns:
        BehaviorController instance
    """
    global _behavior_controller

    if _behavior_controller is None:
        if oasis_manager is None:
            from app.core.oasis_manager import get_oasis_manager
            oasis_manager = await get_oasis_manager()

        _behavior_controller = BehaviorController(oasis_manager)
        logger.info("Behavior Controller singleton created")

    return _behavior_controller


def reset_behavior_controller() -> None:
    """Reset behavior controller singleton (mainly for testing)"""
    global _behavior_controller
    _behavior_controller = None
    logger.info("Behavior Controller singleton reset")