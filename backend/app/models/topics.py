"""
Topic Models - File-driven topic configuration system

Defines Pydantic models for managing simulation topics with initial posts.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.simulation import PlatformType


# ============================================================================
# Topic Configuration Models
# ============================================================================

class TopicInitialPost(BaseModel):
    """Initial post configuration for a topic"""
    content: str = Field(..., description="Content of the initial post")
    agent_id: int = Field(..., ge=0, description="ID of the agent that will post this content")


class TopicSettings(BaseModel):
    """Optional settings for topic activation"""
    trigger_refresh: bool = Field(
        default=True,
        description="Whether to refresh all agents' feeds after initial post"
    )


class Topic(BaseModel):
    """A simulation topic with initial post"""
    id: str = Field(..., description="Unique topic identifier")
    name: str = Field(..., description="Human-readable topic name")
    description: str = Field(..., description="Topic description")
    initial_post: TopicInitialPost = Field(..., description="Initial post configuration")
    settings: TopicSettings = Field(
        default_factory=TopicSettings,
        description="Optional topic settings"
    )

    @field_validator('id')
    @classmethod
    def validate_topic_id(cls, v: str) -> str:
        """Validate topic ID format"""
        if not v or not isinstance(v, str):
            raise ValueError("Topic ID must be a non-empty string")
        # Only allow alphanumeric, underscore, and hyphen
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                "Topic ID must only contain alphanumeric characters, underscores, and hyphens"
            )
        return v.lower()


class TopicConfig(BaseModel):
    """Container for all topics"""
    topics: List[Topic] = Field(default_factory=list, description="List of available topics")

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """Get a topic by ID"""
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        return None

    def list_topics(self) -> List[Topic]:
        """Get all topics"""
        return self.topics

    def count(self) -> int:
        """Get total number of topics"""
        return len(self.topics)


# ============================================================================
# Request/Response Models
# ============================================================================

class TopicActivationRequest(BaseModel):
    """Request to activate a topic"""
    topic_id: str = Field(..., description="ID of the topic to activate")


class TopicActivationResult(BaseModel):
    """Result of topic activation"""
    success: bool
    message: str
    topic_id: Optional[str] = None
    initial_post_created: bool = False
    agents_refreshed: int = 0
    execution_time: Optional[float] = None
    error: Optional[str] = None


class TopicListItem(BaseModel):
    """Topic item for list views"""
    id: str
    name: str
    description: str
    has_initial_post: bool = True
    settings_trigger_refresh: bool = True


class TopicDetail(BaseModel):
    """Detailed topic information"""
    id: str
    name: str
    description: str
    initial_post: TopicInitialPost
    settings: TopicSettings
    available: bool = True  # Whether this topic can be activated


class TopicListResponse(BaseModel):
    """Response for topic list endpoint"""
    success: bool
    count: int
    topics: List[TopicListItem]


class TopicReloadResult(BaseModel):
    """Result of configuration reload"""
    success: bool
    message: str
    topics_loaded: int = 0
    reload_time: Optional[float] = None
