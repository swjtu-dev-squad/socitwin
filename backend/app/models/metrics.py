"""
Metrics Models - Pydantic schemas for OASIS social network analysis metrics

This module defines data models for three key metrics:
1. Information Propagation - How information spreads through the network
2. Group Polarization - Opinion shift and extremification using LLM evaluation
3. Herd Effect - Conformity and popularity-biased behavior patterns
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class PolarizationDirection(str, Enum):
    """Polarization direction categories"""
    EXTREME_CONSERVATIVE = "EXTREME_CONSERVATIVE"
    MODERATE_CONSERVATIVE = "MODERATE_CONSERVATIVE"
    NEUTRAL = "NEUTRAL"
    MODERATE_PROGRESSIVE = "MODERATE_PROGRESSIVE"
    EXTREME_PROGRESSIVE = "EXTREME_PROGRESSIVE"


# ============================================================================
# Information Propagation Metrics
# ============================================================================

class PropagationMetrics(BaseModel):
    """
    Information propagation metrics

    Measures how information spreads through the social network.

    Attributes:
        scale: Number of unique users who participated in propagation
        depth: Maximum depth of propagation chain (root = 0)
        max_breadth: Maximum users at any single depth level
        post_id: Original post ID if analyzing specific post
        calculated_at: When metrics were calculated
    """
    scale: int = Field(
        ...,
        ge=0,
        description="Number of unique users in propagation"
    )
    depth: int = Field(
        ...,
        ge=0,
        description="Maximum propagation depth"
    )
    max_breadth: int = Field(
        ...,
        ge=0,
        description="Maximum users at single depth level"
    )
    post_id: Optional[int] = Field(
        None,
        description="Post ID if specific post, None for aggregate"
    )
    calculated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of calculation"
    )


# ============================================================================
# Group Polarization Metrics
# ============================================================================

class AgentPolarization(BaseModel):
    """Per-agent polarization details"""
    agent_id: int = Field(..., description="Agent user ID")
    agent_name: str = Field(..., description="Agent username")
    direction: PolarizationDirection = Field(..., description="Polarization direction")
    magnitude: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Degree of opinion shift (0=no shift, 1=extreme)"
    )
    reasoning: Optional[str] = Field(
        None,
        description="LLM explanation for polarization assessment"
    )


class PolarizationMetrics(BaseModel):
    """
    Group polarization metrics using LLM evaluation

    Measures opinion shift and extremification by comparing
    initial opinions to current opinions.

    Attributes:
        average_direction: Most common polarization direction
        average_magnitude: Average degree of opinion shift
        agent_polarization: Per-agent polarization scores
        total_agents_evaluated: Number of agents evaluated
        evaluation_method: Method used (llm or heuristic)
        calculated_at: When metrics were calculated
    """
    average_direction: PolarizationDirection = Field(
        ...,
        description="Average polarization direction across all agents"
    )
    average_magnitude: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average magnitude of opinion shift (0-1)"
    )
    agent_polarization: List[AgentPolarization] = Field(
        default_factory=list,
        description="Per-agent polarization details"
    )
    total_agents_evaluated: int = Field(
        ...,
        ge=0,
        description="Total number of agents evaluated"
    )
    evaluation_method: str = Field(
        default="llm",
        description="Evaluation method (llm or heuristic)"
    )
    calculated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of calculation"
    )


# ============================================================================
# Herd Effect Metrics
# ============================================================================

class HotPost(BaseModel):
    """Hot post with Reddit-style score"""
    post_id: int
    user_id: int
    content: str
    net_score: int  # likes - dislikes
    hot_score: float  # Reddit hot formula
    created_at: datetime


class HerdEffectMetrics(BaseModel):
    """
    Herd effect metrics

    Measures conformity and popularity-biased behavior patterns.

    Attributes:
        average_post_score: Average (likes - dislikes) across posts
        disagree_score: Variance in opinion (disagreement level)
        hot_posts: Top posts by Reddit hot score
        conformity_index: Degree of herd behavior (0=diverse, 1=herd)
        calculated_at: When metrics were calculated
    """
    average_post_score: float = Field(
        ...,
        description="Average (likes - dislikes) across posts"
    )
    disagree_score: float = Field(
        ...,
        ge=0.0,
        description="Opinion variance (disagreement level)"
    )
    hot_posts: List[HotPost] = Field(
        default_factory=list,
        description="Top posts by Reddit hot score"
    )
    conformity_index: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Degree of herd behavior (0=diverse opinions, 1=strong herd)"
    )
    calculated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of calculation"
    )


# ============================================================================
# Combined Metrics Summary
# ============================================================================

class MetricsSummary(BaseModel):
    """
    Combined metrics summary

    Provides a complete overview of all OASIS metrics at a point in time.

    Attributes:
        propagation: Information propagation metrics
        polarization: Group polarization metrics
        herd_effect: Herd effect metrics
        current_step: Current simulation step
        timestamp: When summary was generated
    """
    propagation: Optional[PropagationMetrics] = Field(
        None,
        description="Information propagation metrics"
    )
    polarization: Optional[PolarizationMetrics] = Field(
        None,
        description="Group polarization metrics"
    )
    herd_effect: Optional[HerdEffectMetrics] = Field(
        None,
        description="Herd effect metrics"
    )
    current_step: int = Field(
        ...,
        ge=0,
        description="Current simulation step"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When summary was generated"
    )


# ============================================================================
# Request/Response Models for API
# ============================================================================

class MetricsRequest(BaseModel):
    """Base request for metrics queries"""
    post_id: Optional[int] = Field(
        None,
        description="Specific post ID for propagation analysis"
    )
    agent_ids: Optional[str] = Field(
        None,
        description="Comma-separated agent IDs for polarization analysis"
    )
    time_window_seconds: Optional[int] = Field(
        None,
        ge=1,
        description="Time window in seconds for herd effect analysis"
    )


class MetricsResponse(BaseModel):
    """Standard metrics response"""
    success: bool = True
    metric_type: str
    data: Dict[str, Any]
    calculated_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None


# ============================================================================
# Validation
# ============================================================================

class Validator:
    """Common validation utilities for metrics"""

    @staticmethod
    def validate_agent_ids(agent_ids_str: Optional[str]) -> Optional[List[int]]:
        """Validate and parse comma-separated agent IDs"""
        if not agent_ids_str:
            return None

        try:
            ids = [int(x.strip()) for x in agent_ids_str.split(',')]
            return ids if ids else None
        except ValueError:
            return None
