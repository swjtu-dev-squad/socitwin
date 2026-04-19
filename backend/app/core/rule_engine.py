"""
Rule Engine - Rule-based action selection for agents

This module implements rule-based action selection for agents based on
configured rules and conditions, with support for complex condition evaluation
and rule prioritization.
"""

import logging
import random
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

# OASIS framework imports
from oasis import SocialAgent, ManualAction, ActionType

# Local imports
from app.models.behavior import (
    BehaviorRule,
    RuleSet,
    RuleCondition,
    ConditionOperator,
    BehaviorContext
)
from app.models.simulation import PlatformType, OASISActionType

logger = logging.getLogger(__name__)


class RuleEngineError(Exception):
    """Rule engine error base class"""
    pass


class RuleEvaluationError(RuleEngineError):
    """Error during rule evaluation"""
    pass


class InvalidRuleError(RuleEngineError):
    """Invalid rule configuration error"""
    pass


class RuleEngine:
    """
    Rule-based action selection engine

    Responsibilities:
    - Evaluate rules against agent context
    - Select actions based on triggered rules
    - Handle rule prioritization and conflict resolution
    - Support complex condition evaluation
    """

    def __init__(self, rules: Optional[List[BehaviorRule]] = None):
        """
        Initialize rule engine

        Args:
            rules: Initial list of rules (optional)
        """
        self.rules: List[BehaviorRule] = rules or []
        self._sorted_rules: List[BehaviorRule] = []
        self._rule_index: Dict[str, BehaviorRule] = {}

        # Statistics
        self.rule_evaluation_counts: Dict[str, int] = {}
        self.rule_trigger_counts: Dict[str, int] = {}
        self.total_evaluations = 0

        # Cache for compiled conditions
        self._condition_cache: Dict[str, Any] = {}

        # Initialize if rules provided
        if rules:
            self._rebuild_rule_structures()

        logger.info(f"Rule Engine initialized with {len(self.rules)} rules")

    # ========================================================================
    # Public API
    # ========================================================================

    async def evaluate_rules(
        self,
        agent: SocialAgent,
        context: BehaviorContext
    ) -> Optional[ManualAction]:
        """
        Evaluate all rules for an agent and return action if any rule triggers

        Args:
            agent: The agent
            context: Behavior context

        Returns:
            ManualAction if rule triggers, None otherwise
        """
        try:
            # Update statistics
            self.total_evaluations += 1

            # Evaluate rules in priority order
            for rule in self._sorted_rules:
                # Skip disabled rules
                if not rule.enabled:
                    continue

                # Update rule evaluation count
                self._update_rule_evaluation_count(rule.rule_id)

                # Evaluate rule conditions
                if self._evaluate_rule_conditions(rule, context):
                    # Rule triggered!
                    self._update_rule_trigger_count(rule.rule_id)

                    logger.debug(
                        f"Rule '{rule.name}' triggered for agent {agent.social_agent_id}"
                    )

                    # Generate action with arguments
                    action = self._create_action_from_rule(rule, agent, context)
                    return action

            # No rules triggered
            logger.debug(f"No rules triggered for agent {agent.social_agent_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to evaluate rules for agent {agent.social_agent_id}: {e}")
            raise RuleEvaluationError(f"Rule evaluation failed: {str(e)}")

    async def batch_evaluate_rules(
        self,
        agents: List[SocialAgent],
        context: BehaviorContext
    ) -> Dict[SocialAgent, Optional[ManualAction]]:
        """
        Evaluate rules for multiple agents

        Args:
            agents: List of agents
            context: Behavior context

        Returns:
            Dictionary mapping agents to actions (None if no rule triggered)
        """
        results = {}

        for agent in agents:
            try:
                action = await self.evaluate_rules(agent, context)
                results[agent] = action
            except Exception as e:
                logger.error(f"Failed to evaluate rules for agent {agent.social_agent_id}: {e}")
                results[agent] = None

        return results

    def update_rules(self, new_rules: List[BehaviorRule]) -> None:
        """
        Update rules in the engine

        Args:
            new_rules: New list of rules
        """
        # Validate rules
        self._validate_rules(new_rules)

        # Update rules
        self.rules = new_rules
        self._rebuild_rule_structures()

        logger.info(f"Rule engine updated with {len(new_rules)} rules")

    def add_rule(self, rule: BehaviorRule) -> None:
        """
        Add a single rule to the engine

        Args:
            rule: Rule to add
        """
        # Validate rule
        self._validate_single_rule(rule)

        # Check for duplicate rule_id
        if rule.rule_id in self._rule_index:
            logger.warning(f"Rule with ID {rule.rule_id} already exists, replacing")

        # Add or replace rule
        self.rules = [r for r in self.rules if r.rule_id != rule.rule_id]
        self.rules.append(rule)

        self._rebuild_rule_structures()
        logger.info(f"Rule '{rule.name}' added to engine")

    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a rule from the engine

        Args:
            rule_id: ID of rule to remove

        Returns:
            True if rule was removed, False otherwise
        """
        original_count = len(self.rules)
        self.rules = [r for r in self.rules if r.rule_id != rule_id]

        if len(self.rules) < original_count:
            self._rebuild_rule_structures()
            logger.info(f"Rule {rule_id} removed from engine")
            return True
        else:
            logger.warning(f"Rule {rule_id} not found in engine")
            return False

    def get_rule(self, rule_id: str) -> Optional[BehaviorRule]:
        """
        Get rule by ID

        Args:
            rule_id: Rule ID

        Returns:
            BehaviorRule or None if not found
        """
        return self._rule_index.get(rule_id)

    def enable_rule(self, rule_id: str) -> bool:
        """
        Enable a rule

        Args:
            rule_id: Rule ID

        Returns:
            True if rule was enabled, False otherwise
        """
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = True
            logger.info(f"Rule {rule_id} enabled")
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """
        Disable a rule

        Args:
            rule_id: Rule ID

        Returns:
            True if rule was disabled, False otherwise
        """
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = False
            logger.info(f"Rule {rule_id} disabled")
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine statistics

        Returns:
            Statistics dictionary
        """
        total_evaluations = self.total_evaluations

        # Calculate rule statistics
        rule_stats = {}
        for rule_id, eval_count in self.rule_evaluation_counts.items():
            trigger_count = self.rule_trigger_counts.get(rule_id, 0)
            rule = self._rule_index.get(rule_id)

            stats = {
                "evaluation_count": eval_count,
                "trigger_count": trigger_count,
                "enabled": rule.enabled if rule else False,
                "priority": rule.priority if rule else 0,
            }

            # Calculate trigger rate
            if eval_count > 0:
                trigger_rate = (trigger_count / eval_count) * 100
                stats["trigger_rate_percent"] = round(trigger_rate, 2)
            else:
                stats["trigger_rate_percent"] = 0.0

            rule_stats[rule_id] = stats

        # Calculate overall statistics
        enabled_rules = sum(1 for r in self.rules if r.enabled)
        disabled_rules = len(self.rules) - enabled_rules

        return {
            "total_rules": len(self.rules),
            "enabled_rules": enabled_rules,
            "disabled_rules": disabled_rules,
            "total_evaluations": total_evaluations,
            "total_triggers": sum(self.rule_trigger_counts.values()),
            "rule_statistics": rule_stats,
            "last_updated": datetime.now(),
        }

    def reset_statistics(self) -> None:
        """Reset engine statistics"""
        self.rule_evaluation_counts.clear()
        self.rule_trigger_counts.clear()
        self.total_evaluations = 0
        logger.info("Rule engine statistics reset")

    # ========================================================================
    # Rule Evaluation
    # ========================================================================

    def _evaluate_rule_conditions(
        self,
        rule: BehaviorRule,
        context: BehaviorContext
    ) -> bool:
        """
        Evaluate all conditions for a rule

        Args:
            rule: Rule to evaluate
            context: Behavior context

        Returns:
            True if all conditions are met
        """
        if not rule.conditions:
            # Rule with no conditions always triggers
            return True

        context_dict = context.dict()

        for condition in rule.conditions:
            if not self._evaluate_condition(condition, context_dict):
                return False

        # All conditions passed
        return True

    def _evaluate_condition(
        self,
        condition: RuleCondition,
        context_dict: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single condition

        Args:
            condition: Condition to evaluate
            context_dict: Context as dictionary

        Returns:
            True if condition is met
        """
        field = condition.field
        operator = condition.operator
        value = condition.value

        # Check if field exists in context
        field_value = context_dict.get(field)

        # Handle EXISTS and NOT_EXISTS operators
        if operator == ConditionOperator.EXISTS:
            return field in context_dict and context_dict[field] is not None

        elif operator == ConditionOperator.NOT_EXISTS:
            return field not in context_dict or context_dict[field] is None

        # For other operators, field must exist
        if field not in context_dict:
            return False

        # Evaluate based on operator
        try:
            if operator == ConditionOperator.EQUALS:
                return field_value == value

            elif operator == ConditionOperator.NOT_EQUALS:
                return field_value != value

            elif operator == ConditionOperator.GREATER_THAN:
                return self._compare_values(field_value, value) > 0

            elif operator == ConditionOperator.LESS_THAN:
                return self._compare_values(field_value, value) < 0

            elif operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
                return self._compare_values(field_value, value) >= 0

            elif operator == ConditionOperator.LESS_THAN_OR_EQUAL:
                return self._compare_values(field_value, value) <= 0

            elif operator == ConditionOperator.CONTAINS:
                if isinstance(field_value, str) and isinstance(value, str):
                    return value in field_value
                elif isinstance(field_value, list):
                    return value in field_value
                else:
                    return False

            elif operator == ConditionOperator.NOT_CONTAINS:
                if isinstance(field_value, str) and isinstance(value, str):
                    return value not in field_value
                elif isinstance(field_value, list):
                    return value not in field_value
                else:
                    return True

            elif operator == ConditionOperator.STARTS_WITH:
                if isinstance(field_value, str) and isinstance(value, str):
                    return field_value.startswith(value)
                return False

            elif operator == ConditionOperator.ENDS_WITH:
                if isinstance(field_value, str) and isinstance(value, str):
                    return field_value.endswith(value)
                return False

            elif operator == ConditionOperator.IN:
                if isinstance(value, list):
                    return field_value in value
                return False

            elif operator == ConditionOperator.NOT_IN:
                if isinstance(value, list):
                    return field_value not in value
                return True

            else:
                logger.warning(f"Unknown operator: {operator}")
                return False

        except Exception as e:
            logger.warning(f"Failed to evaluate condition {field} {operator} {value}: {e}")
            return False

    def _compare_values(self, a: Any, b: Any) -> int:
        """
        Compare two values for ordering operations

        Args:
            a: First value
            b: Second value

        Returns:
            -1 if a < b, 0 if a == b, 1 if a > b
        """
        try:
            # Try numeric comparison first
            a_num = float(a) if not isinstance(a, (int, float)) else a
            b_num = float(b) if not isinstance(b, (int, float)) else b
            if a_num < b_num:
                return -1
            elif a_num > b_num:
                return 1
            else:
                return 0
        except (ValueError, TypeError):
            # Fall back to string comparison
            a_str = str(a)
            b_str = str(b)
            if a_str < b_str:
                return -1
            elif a_str > b_str:
                return 1
            else:
                return 0

    # ========================================================================
    # Action Creation
    # ========================================================================

    def _create_action_from_rule(
        self,
        rule: BehaviorRule,
        agent: SocialAgent,
        context: BehaviorContext
    ) -> ManualAction:
        """
        Create ManualAction from triggered rule

        Args:
            rule: Triggered rule
            agent: The agent
            context: Behavior context

        Returns:
            ManualAction
        """
        # Start with rule's action arguments
        action_args = rule.action_args.copy() if rule.action_args else {}

        # Add agent context
        action_args['agent_id'] = agent.social_agent_id
        action_args['step'] = context.current_step
        action_args['platform'] = context.platform.value
        action_args['rule_id'] = rule.rule_id

        # Map OASISActionType to ActionType
        try:
            oasis_action_type = getattr(ActionType, rule.action.value)
        except AttributeError:
            logger.error(f"Action type {rule.action.value} not found in OASIS ActionType")
            raise RuleEvaluationError(f"Invalid action type: {rule.action.value}")

        # Create and return ManualAction
        return ManualAction(
            action_type=oasis_action_type,
            action_args=action_args
        )

    # ========================================================================
    # Rule Management
    # ========================================================================

    def _rebuild_rule_structures(self) -> None:
        """Rebuild internal rule structures after rule updates"""
        # Sort rules by priority (higher priority first)
        self._sorted_rules = sorted(
            self.rules,
            key=lambda r: r.priority,
            reverse=True  # Higher priority first
        )

        # Rebuild index
        self._rule_index = {rule.rule_id: rule for rule in self.rules}

        # Clear condition cache
        self._condition_cache.clear()

        logger.debug(f"Rule structures rebuilt, {len(self.rules)} rules sorted by priority")

    def _validate_rules(self, rules: List[BehaviorRule]) -> None:
        """
        Validate list of rules

        Args:
            rules: Rules to validate

        Raises:
            InvalidRuleError: If validation fails
        """
        seen_ids = set()

        for rule in rules:
            self._validate_single_rule(rule)

            # Check for duplicate IDs
            if rule.rule_id in seen_ids:
                raise InvalidRuleError(f"Duplicate rule ID: {rule.rule_id}")
            seen_ids.add(rule.rule_id)

    def _validate_single_rule(self, rule: BehaviorRule) -> None:
        """
        Validate a single rule

        Args:
            rule: Rule to validate

        Raises:
            InvalidRuleError: If validation fails
        """
        # Basic validation
        if not rule.rule_id or not isinstance(rule.rule_id, str):
            raise InvalidRuleError("Rule must have a non-empty string rule_id")

        if not rule.name or not isinstance(rule.name, str):
            raise InvalidRuleError("Rule must have a non-empty string name")

        if rule.priority < 1 or rule.priority > 10:
            raise InvalidRuleError(f"Rule priority must be between 1 and 10, got {rule.priority}")

        # Validate conditions (if any)
        if rule.conditions:
            for condition in rule.conditions:
                self._validate_condition(condition)

        # Validate action
        try:
            # Check if action type exists
            OASISActionType(rule.action.value)
        except ValueError:
            raise InvalidRuleError(f"Invalid action type: {rule.action}")

    def _validate_condition(self, condition: RuleCondition) -> None:
        """
        Validate a condition

        Args:
            condition: Condition to validate

        Raises:
            InvalidRuleError: If validation fails
        """
        if not condition.field or not isinstance(condition.field, str):
            raise InvalidRuleError("Condition must have a non-empty string field")

        try:
            ConditionOperator(condition.operator)
        except ValueError:
            raise InvalidRuleError(f"Invalid condition operator: {condition.operator}")

        # For EXISTS/NOT_EXISTS, value should be None
        if condition.operator in [ConditionOperator.EXISTS, ConditionOperator.NOT_EXISTS]:
            if condition.value is not None:
                logger.warning(f"Value should be None for {condition.operator} operator")
        else:
            # For other operators, value should not be None
            if condition.value is None:
                raise InvalidRuleError(f"Value cannot be None for {condition.operator} operator")

    # ========================================================================
    # Statistics
    # ========================================================================

    def _update_rule_evaluation_count(self, rule_id: str) -> None:
        """Update evaluation count for a rule"""
        if rule_id not in self.rule_evaluation_counts:
            self.rule_evaluation_counts[rule_id] = 0
        self.rule_evaluation_counts[rule_id] += 1

    def _update_rule_trigger_count(self, rule_id: str) -> None:
        """Update trigger count for a rule"""
        if rule_id not in self.rule_trigger_counts:
            self.rule_trigger_counts[rule_id] = 0
        self.rule_trigger_counts[rule_id] += 1

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_enabled_rules(self) -> List[BehaviorRule]:
        """Get list of enabled rules"""
        return [r for r in self.rules if r.enabled]

    def get_disabled_rules(self) -> List[BehaviorRule]:
        """Get list of disabled rules"""
        return [r for r in self.rules if not r.enabled]

    def clear_rules(self) -> None:
        """Clear all rules from engine"""
        self.rules.clear()
        self._rebuild_rule_structures()
        logger.info("All rules cleared from engine")


# ============================================================================
# Factory Function
# ============================================================================

_rule_engines: Dict[str, RuleEngine] = {}


def get_rule_engine(rules: Optional[List[BehaviorRule]] = None) -> RuleEngine:
    """
    Get rule engine instance (singleton for default rule set)

    Args:
        rules: Optional initial rules

    Returns:
        RuleEngine instance
    """
    global _rule_engines

    # Use "default" as key for singleton
    engine_key = "default"

    if engine_key not in _rule_engines:
        _rule_engines[engine_key] = RuleEngine(rules)
        logger.info(f"Rule Engine created with key '{engine_key}'")

    # Update rules if provided
    if rules is not None:
        _rule_engines[engine_key].update_rules(rules)

    return _rule_engines[engine_key]


def reset_rule_engines() -> None:
    """Reset all rule engines (mainly for testing)"""
    global _rule_engines
    _rule_engines.clear()
    logger.info("Rule engines reset")