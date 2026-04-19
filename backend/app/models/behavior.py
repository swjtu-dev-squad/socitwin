"""
Behavior Models - Pydantic schemas for agent behavior control system

Defines models for behavior scheduling, probability distributions, and rule-based control.
This module extends the existing LLM autonomous decision-making with structured control mechanisms.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.simulation import OASISActionType, PlatformType

# ============================================================================
# Behavior Strategy Enums
# ============================================================================

class BehaviorStrategy(str, Enum):
    """Behavior decision strategy types"""
    LLM_AUTONOMOUS = "llm_autonomous"      # Original LLM autonomous decision
    PROBABILISTIC = "probabilistic"        # Probability distribution model
    RULE_BASED = "rule_based"              # Rule engine based decision
    SCHEDULED = "scheduled"                # Timeline-based scheduling
    MIXED = "mixed"                        # Mixed strategy with weights


class ConditionOperator(str, Enum):
    """Operators for rule conditions"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


# ============================================================================
# Probability Distribution Models
# ============================================================================

class ActionProbability(BaseModel):
    """Probability distribution for a single action type"""
    action_type: OASISActionType = Field(
        ...,
        description="Type of action"
    )
    probability: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Probability weight (0-1)"
    )
    conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional conditions for when this probability applies"
    )
    action_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass when executing this action"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this probability rule"
    )

    @field_validator('probability')
    @classmethod
    def validate_probability(cls, v: float) -> float:
        """Ensure probability is within valid range"""
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Probability must be between 0.0 and 1.0, got {v}")
        return v


class ProbabilityDistribution(BaseModel):
    """Complete probability distribution for all actions"""
    name: str = Field(
        ...,
        description="Name of this probability distribution profile"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of this distribution"
    )
    actions: List[ActionProbability] = Field(
        default_factory=list,
        description="List of action probabilities"
    )
    platform: Optional[PlatformType] = Field(
        default=None,
        description="Platform this distribution is designed for"
    )

    @field_validator('actions')
    @classmethod
    def validate_probabilities_sum(cls, v: List[ActionProbability]) -> List[ActionProbability]:
        """Validate that probabilities sum to 1.0 (with tolerance)"""
        if not v:
            return v

        total = sum(action.probability for action in v)
        tolerance = 0.01  # 1% tolerance

        if abs(total - 1.0) > tolerance:
            # Normalize probabilities
            if total > 0:
                for action in v:
                    action.probability /= total
            else:
                # Equal distribution if all zero
                equal_prob = 1.0 / len(v)
                for action in v:
                    action.probability = equal_prob

        return v


# ============================================================================
# Rule Engine Models
# ============================================================================

class RuleCondition(BaseModel):
    """Single condition in a rule"""
    field: str = Field(
        ...,
        description="Field name to evaluate"
    )
    operator: ConditionOperator = Field(
        ...,
        description="Comparison operator"
    )
    value: Optional[Any] = Field(
        default=None,
        description="Value to compare against (not needed for EXISTS/NOT_EXISTS)"
    )


class BehaviorRule(BaseModel):
    """Rule for rule-based behavior control"""
    rule_id: str = Field(
        ...,
        description="Unique identifier for this rule"
    )
    name: str = Field(
        ...,
        description="Human-readable rule name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Rule description"
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Rule priority (higher = more important)"
    )
    conditions: List[RuleCondition] = Field(
        default_factory=list,
        description="List of conditions that must all be true"
    )
    action: OASISActionType = Field(
        ...,
        description="Action to execute when rule triggers"
    )
    action_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the action"
    )
    enabled: bool = Field(
        default=True,
        description="Whether this rule is enabled"
    )

    @field_validator('rule_id')
    @classmethod
    def validate_rule_id(cls, v: str) -> str:
        """Validate rule ID format"""
        if not v or not isinstance(v, str):
            raise ValueError("Rule ID must be a non-empty string")
        # Only allow alphanumeric, underscore, and hyphen
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                "Rule ID must only contain alphanumeric characters, underscores, and hyphens"
            )
        return v.lower()


class RuleSet(BaseModel):
    """Collection of related rules"""
    name: str = Field(
        ...,
        description="Name of this rule set"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of this rule set"
    )
    rules: List[BehaviorRule] = Field(
        default_factory=list,
        description="Rules in this set"
    )
    platform: Optional[PlatformType] = Field(
        default=None,
        description="Platform this rule set is designed for"
    )


# ============================================================================
# Scheduling Models
# ============================================================================

class TimelineEvent(BaseModel):
    """Single event in a behavior timeline"""
    step: int = Field(
        ...,
        ge=0,
        description="Simulation step when this event occurs"
    )
    action: OASISActionType = Field(
        ...,
        description="Action to execute"
    )
    action_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the action"
    )
    repeat_interval: Optional[int] = Field(
        default=None,
        ge=1,
        description="Repeat interval in steps (None for one-time event)"
    )
    repeat_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of times to repeat (None for infinite)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Event description"
    )

    @field_validator('repeat_interval')
    @classmethod
    def validate_repeat_interval(cls, v: Optional[int], info) -> Optional[int]:
        """Validate repeat interval makes sense"""
        if v is not None and 'repeat_count' in info.data:
            repeat_count = info.data.get('repeat_count')
            if repeat_count is not None and repeat_count <= 1:
                # If repeat_count is 1 or less, repeat_interval doesn't matter
                return None
        return v


class BehaviorSchedule(BaseModel):
    """Schedule of events for an agent"""
    name: str = Field(
        ...,
        description="Schedule name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Schedule description"
    )
    timeline: List[TimelineEvent] = Field(
        default_factory=list,
        description="Timeline of events"
    )
    loop: bool = Field(
        default=False,
        description="Whether to loop the schedule after completion"
    )


# ============================================================================
# Mixed Strategy Models
# ============================================================================

class StrategyWeight(BaseModel):
    """Weight for a strategy in mixed mode"""
    strategy: BehaviorStrategy = Field(
        ...,
        description="Strategy type"
    )
    weight: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weight for this strategy (0-1)"
    )

    @field_validator('weight')
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Ensure weight is within valid range"""
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {v}")
        return v


class MixedStrategyConfig(BaseModel):
    """Configuration for mixed strategy"""
    name: str = Field(
        ...,
        description="Mixed strategy name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Strategy description"
    )
    strategy_weights: List[StrategyWeight] = Field(
        default_factory=list,
        description="Weights for different strategies"
    )
    selection_mode: str = Field(
        default="weighted_random",
        description="How to select strategy: 'weighted_random', 'round_robin', 'priority'"
    )

    @field_validator('strategy_weights')
    @classmethod
    def validate_weights_sum(cls, v: List[StrategyWeight]) -> List[StrategyWeight]:
        """Validate that weights sum to 1.0 (with tolerance)"""
        if not v:
            return v

        total = sum(weight.weight for weight in v)
        tolerance = 0.01  # 1% tolerance

        if abs(total - 1.0) > tolerance:
            # Normalize weights
            if total > 0:
                for weight in v:
                    weight.weight /= total
            else:
                # Equal weights if all zero
                equal_weight = 1.0 / len(v)
                for weight in v:
                    weight.weight = equal_weight

        return v


# ============================================================================
# Complete Behavior Configuration
# ============================================================================

class AgentBehaviorConfig(BaseModel):
    """Complete behavior configuration for an agent"""
    strategy: BehaviorStrategy = Field(
        default=BehaviorStrategy.LLM_AUTONOMOUS,
        description="Primary behavior strategy"
    )

    # Strategy-specific configurations
    probability_distribution: Optional[ProbabilityDistribution] = Field(
        default=None,
        description="Probability distribution for probabilistic strategy"
    )
    rule_set: Optional[RuleSet] = Field(
        default=None,
        description="Rule set for rule-based strategy"
    )
    schedule: Optional[BehaviorSchedule] = Field(
        default=None,
        description="Schedule for scheduled strategy"
    )
    mixed_strategy: Optional[MixedStrategyConfig] = Field(
        default=None,
        description="Configuration for mixed strategy"
    )

    # Context and constraints
    enabled: bool = Field(
        default=True,
        description="Whether this behavior configuration is enabled"
    )
    platform_filter: Optional[PlatformType] = Field(
        default=None,
        description="Platform this configuration applies to"
    )
    step_range: Optional[tuple[int, int]] = Field(
        default=None,
        description="Step range where this configuration is active (inclusive)"
    )
    conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional conditions for when this configuration applies"
    )

    @field_validator('step_range')
    @classmethod
    def validate_step_range(cls, v: Optional[tuple[int, int]]) -> Optional[tuple[int, int]]:
        """Validate step range"""
        if v is not None:
            start, end = v
            if start < 0:
                raise ValueError(f"Start step must be >= 0, got {start}")
            if end < start:
                raise ValueError(f"End step must be >= start step, got {end} < {start}")
        return v

    def is_active(self, context: Dict[str, Any]) -> bool:
        """Check if this configuration is active given the current context"""
        if not self.enabled:
            return False

        # Check platform filter
        if self.platform_filter and context.get('platform') != self.platform_filter:
            return False

        # Check step range
        current_step = context.get('current_step', 0)
        if self.step_range:
            start, end = self.step_range
            if current_step < start or current_step > end:
                return False

        # Check additional conditions
        if self.conditions:
            # Simple condition checking - can be extended
            for key, value in self.conditions.items():
                if context.get(key) != value:
                    return False

        return True


class BehaviorProfile(BaseModel):
    """Reusable behavior profile that can be applied to multiple agents"""
    profile_id: str = Field(
        ...,
        description="Unique profile identifier"
    )
    name: str = Field(
        ...,
        description="Profile name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Profile description"
    )
    behavior_config: AgentBehaviorConfig = Field(
        ...,
        description="Behavior configuration"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this profile was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this profile was last updated"
    )


# ============================================================================
# Context Models
# ============================================================================

class BehaviorContext(BaseModel):
    """Context information for behavior decision making"""
    current_step: int = Field(
        default=0,
        description="Current simulation step"
    )
    platform: PlatformType = Field(
        ...,
        description="Current platform"
    )
    agent_id: int = Field(
        ...,
        description="Agent ID"
    )
    agent_state: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current agent state"
    )
    simulation_state: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Overall simulation state"
    )
    recent_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent actions taken by this agent"
    )
    environment_stats: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Environment statistics"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Context timestamp"
    )

    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True


# ============================================================================
# Request/Response Models for API
# ============================================================================

class BehaviorConfigRequest(BaseModel):
    """Request to update agent behavior configuration"""
    agent_id: int = Field(
        ...,
        description="Agent ID to configure"
    )
    behavior_config: AgentBehaviorConfig = Field(
        ...,
        description="Behavior configuration"
    )


class BehaviorProfileRequest(BaseModel):
    """Request to create/update a behavior profile"""
    profile: BehaviorProfile = Field(
        ...,
        description="Behavior profile"
    )


class ApplyProfileRequest(BaseModel):
    """Request to apply a profile to agents"""
    profile_id: str = Field(
        ...,
        description="Profile ID to apply"
    )
    agent_ids: List[int] = Field(
        default_factory=list,
        description="List of agent IDs to apply to (empty = all agents)"
    )


class BehaviorConfigResponse(BaseModel):
    """Response for behavior configuration operations"""
    success: bool = Field(
        default=True,
        description="Operation success status"
    )
    message: str = Field(
        ...,
        description="Response message"
    )
    agent_id: Optional[int] = Field(
        default=None,
        description="Agent ID (if applicable)"
    )
    profile_id: Optional[str] = Field(
        default=None,
        description="Profile ID (if applicable)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details (if any)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response timestamp"
    )


class BehaviorProfilesResponse(BaseModel):
    """Response listing behavior profiles"""
    success: bool = Field(
        default=True,
        description="Operation success status"
    )
    profiles: List[BehaviorProfile] = Field(
        default_factory=list,
        description="List of behavior profiles"
    )
    count: int = Field(
        default=0,
        description="Total number of profiles"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response timestamp"
    )


# ============================================================================
# Factory Functions
# ============================================================================

def create_default_behavior_config() -> AgentBehaviorConfig:
    """Create a default behavior configuration (LLM autonomous)"""
    return AgentBehaviorConfig(
        strategy=BehaviorStrategy.LLM_AUTONOMOUS,
        enabled=True
    )


def create_probabilistic_config(
    name: str = "balanced",
    platform: PlatformType = PlatformType.TWITTER
) -> AgentBehaviorConfig:
    """Create a default probabilistic behavior configuration"""

    # Default balanced probabilities for Twitter
    if platform == PlatformType.TWITTER:
        actions = [
            ActionProbability(
                action_type=OASISActionType.CREATE_POST,
                probability=0.2,
                description="Create new post"
            ),
            ActionProbability(
                action_type=OASISActionType.LIKE_POST,
                probability=0.3,
                description="Like a post"
            ),
            ActionProbability(
                action_type=OASISActionType.CREATE_COMMENT,
                probability=0.25,
                description="Comment on a post"
            ),
            ActionProbability(
                action_type=OASISActionType.REFRESH,
                probability=0.15,
                description="Refresh feed"
            ),
            ActionProbability(
                action_type=OASISActionType.DO_NOTHING,
                probability=0.1,
                description="Do nothing"
            ),
        ]
    else:
        # Default for Reddit
        actions = [
            ActionProbability(
                action_type=OASISActionType.CREATE_POST,
                probability=0.15,
                description="Create new post"
            ),
            ActionProbability(
                action_type=OASISActionType.LIKE_POST,
                probability=0.35,
                description="Upvote a post"
            ),
            ActionProbability(
                action_type=OASISActionType.CREATE_COMMENT,
                probability=0.3,
                description="Comment on a post"
            ),
            ActionProbability(
                action_type=OASISActionType.REFRESH,
                probability=0.1,
                description="Refresh feed"
            ),
            ActionProbability(
                action_type=OASISActionType.DISLIKE_POST,
                probability=0.05,
                description="Downvote a post"
            ),
            ActionProbability(
                action_type=OASISActionType.DO_NOTHING,
                probability=0.05,
                description="Do nothing"
            ),
        ]

    distribution = ProbabilityDistribution(
        name=name,
        description=f"Balanced {platform.value} behavior distribution",
        actions=actions,
        platform=platform
    )

    return AgentBehaviorConfig(
        strategy=BehaviorStrategy.PROBABILISTIC,
        probability_distribution=distribution,
        enabled=True
    )


def create_scheduled_config(
    name: str = "marketing_campaign",
    platform: PlatformType = PlatformType.TWITTER
) -> AgentBehaviorConfig:
    """Create a scheduled behavior configuration for marketing campaigns"""

    timeline = [
        TimelineEvent(
            step=0,
            action=OASISActionType.CREATE_POST,
            action_args={"content": "Campaign launch! Check out our new product."},
            description="Campaign launch post"
        ),
        TimelineEvent(
            step=5,
            action=OASISActionType.CREATE_COMMENT,
            action_args={"content": "Thanks for the support! Use code LAUNCH20 for 20% off."},
            description="Engagement comment"
        ),
        TimelineEvent(
            step=10,
            action=OASISActionType.CREATE_POST,
            action_args={"content": "Mid-campaign update: Amazing response so far!"},
            description="Mid-campaign update"
        ),
        TimelineEvent(
            step=15,
            action=OASISActionType.CREATE_POST,
            action_args={"content": "Final hours! Don't miss out on this offer."},
            description="Final reminder"
        ),
    ]

    schedule = BehaviorSchedule(
        name=name,
        description=f"{platform.value} marketing campaign schedule",
        timeline=timeline,
        loop=False
    )

    return AgentBehaviorConfig(
        strategy=BehaviorStrategy.SCHEDULED,
        schedule=schedule,
        enabled=True
    )


def create_rule_based_config(
    name: str = "customer_support",
    platform: PlatformType = PlatformType.TWITTER
) -> AgentBehaviorConfig:
    """Create a rule-based behavior configuration for customer support"""

    rules = [
        BehaviorRule(
            rule_id="respond_to_mentions",
            name="Respond to Mentions",
            description="Respond when mentioned with positive sentiment",
            priority=1,
            conditions=[
                RuleCondition(
                    field="event_type",
                    operator=ConditionOperator.EQUALS,
                    value="mentioned"
                ),
                RuleCondition(
                    field="sentiment",
                    operator=ConditionOperator.EQUALS,
                    value="positive"
                )
            ],
            action=OASISActionType.CREATE_COMMENT,
            action_args={"content": "Thank you for mentioning us! We're glad you're happy."}
        ),
        BehaviorRule(
            rule_id="handle_complaints",
            name="Handle Complaints",
            description="Respond to negative mentions with apology",
            priority=2,
            conditions=[
                RuleCondition(
                    field="event_type",
                    operator=ConditionOperator.EQUALS,
                    value="mentioned"
                ),
                RuleCondition(
                    field="sentiment",
                    operator=ConditionOperator.EQUALS,
                    value="negative"
                )
            ],
            action=OASISActionType.CREATE_COMMENT,
            action_args={"content": "We're sorry to hear about your experience. Please DM us so we can help."}
        ),
        BehaviorRule(
            rule_id="share_positive_feedback",
            name="Share Positive Feedback",
            description="Share positive mentions as quotes",
            priority=3,
            conditions=[
                RuleCondition(
                    field="event_type",
                    operator=ConditionOperator.EQUALS,
                    value="mentioned"
                ),
                RuleCondition(
                    field="sentiment",
                    operator=ConditionOperator.EQUALS,
                    value="very_positive"
                ),
                RuleCondition(
                    field="influence",
                    operator=ConditionOperator.GREATER_THAN,
                    value=1000
                )
            ],
            action=OASISActionType.QUOTE_POST,
            action_args={"content": "Great feedback from our community! 🎉"}
        ),
    ]

    rule_set = RuleSet(
        name=name,
        description=f"{platform.value} customer support rules",
        rules=rules,
        platform=platform
    )

    return AgentBehaviorConfig(
        strategy=BehaviorStrategy.RULE_BASED,
        rule_set=rule_set,
        enabled=True
    )


# Export commonly used types
__all__ = [
    'BehaviorStrategy',
    'ConditionOperator',
    'ActionProbability',
    'ProbabilityDistribution',
    'RuleCondition',
    'BehaviorRule',
    'RuleSet',
    'TimelineEvent',
    'BehaviorSchedule',
    'StrategyWeight',
    'MixedStrategyConfig',
    'AgentBehaviorConfig',
    'BehaviorProfile',
    'BehaviorContext',
    'create_default_behavior_config',
    'create_probabilistic_config',
    'create_scheduled_config',
    'create_rule_based_config',
]
