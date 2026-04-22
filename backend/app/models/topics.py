"""
Topic and dataset models.

Defines API models for database-backed topic selection, activation,
preprocessed persona seeds, and simulation seed content.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.simulation import AgentConfig, PlatformType

# ============================================================================
# Topic Configuration Models
# ============================================================================

class TopicInitialPost(BaseModel):
    """Initial post configuration for a topic."""

    content: str = Field(..., description="Content of the initial post")
    agent_id: int = Field(..., ge=0, description="ID of the agent that will post this content")


class TopicSettings(BaseModel):
    """Optional settings for topic activation."""

    trigger_refresh: bool = Field(
        default=True,
        description="Whether to refresh all agents' feeds after initial post",
    )


class Topic(BaseModel):
    """Legacy topic model kept for compatibility."""

    id: str = Field(..., description="Unique topic identifier")
    name: str = Field(..., description="Human-readable topic name")
    description: str = Field(..., description="Topic description")
    initial_post: TopicInitialPost = Field(..., description="Initial post configuration")
    settings: TopicSettings = Field(
        default_factory=TopicSettings,
        description="Optional topic settings",
    )

    @field_validator("id")
    @classmethod
    def validate_topic_id(cls, value: str) -> str:
        """Validate topic ID format."""
        if not value or not isinstance(value, str):
            raise ValueError("Topic ID must be a non-empty string")

        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise ValueError(
                "Topic ID must only contain alphanumeric characters, underscores, and hyphens"
            )
        return value.lower()


class TopicConfig(BaseModel):
    """Container for legacy file-driven topics."""

    topics: List[Topic] = Field(default_factory=list, description="List of available topics")

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        return None

    def list_topics(self) -> List[Topic]:
        return self.topics

    def count(self) -> int:
        return len(self.topics)


# ============================================================================
# Request/Response Models
# ============================================================================

class TopicActivationRequest(BaseModel):
    """Request to activate a topic."""

    topic_id: str = Field(..., description="ID of the topic to activate")


class TopicActivationResult(BaseModel):
    """Result of topic activation."""

    success: bool
    message: str
    topic_id: Optional[str] = None
    initial_post_created: bool = False
    agents_refreshed: int = 0
    execution_time: Optional[float] = None
    error: Optional[str] = None


class TopicListItem(BaseModel):
    """Topic item for list views."""

    id: str
    name: str
    description: str
    platform: PlatformType = PlatformType.TWITTER
    topic_key: Optional[str] = None
    topic_type: str = "trend"
    trend_rank: Optional[int] = None
    post_count: int = 0
    reply_count: int = 0
    user_count: int = 0
    news_external_id: Optional[str] = None
    has_initial_post: bool = True
    settings_trigger_refresh: bool = True


class TopicDetail(BaseModel):
    """Detailed topic information."""

    id: str
    name: str
    description: str
    platform: PlatformType = PlatformType.TWITTER
    topic_key: Optional[str] = None
    topic_type: str = "trend"
    trend_rank: Optional[int] = None
    post_count: int = 0
    reply_count: int = 0
    user_count: int = 0
    news_external_id: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    initial_post: TopicInitialPost
    settings: TopicSettings = Field(default_factory=TopicSettings)
    available: bool = True


class TopicListResponse(BaseModel):
    """Response for topic list endpoint."""

    success: bool
    count: int
    topics: List[TopicListItem]


class TopicReloadResult(BaseModel):
    """Result of refreshing topic metadata."""

    success: bool
    message: str
    topics_loaded: int = 0
    reload_time: Optional[float] = None


class TopicProfileItem(BaseModel):
    """Preprocessed topic participant profile ready for simulation seeding."""

    external_user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    verified: bool = False
    follower_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    role: str
    content_count: int = 0
    influence_score: float = 0.0
    activity_score: float = 0.0
    interests: List[str] = Field(default_factory=list)
    agent_config: AgentConfig


class TopicProfilesResponse(BaseModel):
    """Response for preprocessed topic participant profiles."""

    success: bool
    topic: TopicDetail
    count: int
    profiles: List[TopicProfileItem]


class TopicContentItem(BaseModel):
    """Content seed item for situational inference."""

    external_content_id: str
    content_type: str
    author_external_user_id: Optional[str] = None
    author_username: Optional[str] = None
    author_display_name: Optional[str] = None
    parent_external_content_id: Optional[str] = None
    root_external_content_id: Optional[str] = None
    text: Optional[str] = None
    language: Optional[str] = None
    created_at: Optional[datetime] = None
    like_count: int = 0
    reply_count: int = 0
    share_count: int = 0
    view_count: int = 0
    relevance_score: float = 1.0


class TopicSimulationResponse(BaseModel):
    """Simulation-ready data response for a selected topic."""

    success: bool
    topic: TopicDetail
    participant_count: int
    content_count: int
    profiles: List[TopicProfileItem]
    contents: List[TopicContentItem]


# ============================================================================
# Live trending (X News search, not persisted)
# ============================================================================


class TwitterTrendingTopicItem(BaseModel):
    """单条热点新闻（与 fetch_twitter_data.fetch_trending_news_topic_rows 字段对齐）。"""

    news_id: str
    name: str
    axis: str = Field(description="politics | economy | society 检索轴")
    search_query: str
    trend_rank: int
    summary: Optional[str] = None
    category: Optional[str] = None


class TwitterTrendingTopicsResponse(BaseModel):
    """GET /api/topics/twitter/trending-topics 响应。"""

    success: bool
    source: str = Field(default="x_news_search", description="数据来源：X API v2 /news/search")
    collected_at: str
    count: int
    topics: List[TwitterTrendingTopicItem]
