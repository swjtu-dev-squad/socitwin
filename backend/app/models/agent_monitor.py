from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

AgentStatus = Literal["active", "idle", "thinking"]
AgentMemoryContentSource = Literal["system_prompt", "retrieval"]
AgentMemoryRetrievalStatus = Literal["not_configured", "ready", "empty", "error"]


class AgentMemoryRetrievalItem(BaseModel):
    id: str
    content: str
    score: Optional[float] = None
    source: Optional[str] = None
    createdAt: Optional[str] = None


class AgentMemoryRetrieval(BaseModel):
    length: int = 0
    enabled: bool = False
    status: AgentMemoryRetrievalStatus = "not_configured"
    content: str = ""
    items: List[AgentMemoryRetrievalItem] = Field(default_factory=list)


class AgentMemorySystemPrompt(BaseModel):
    length: int = 0
    content: str = ""


class AgentMemorySnapshot(BaseModel):
    length: int = 0
    content: str = ""
    contentSource: AgentMemoryContentSource = "system_prompt"
    systemPrompt: AgentMemorySystemPrompt = Field(default_factory=AgentMemorySystemPrompt)
    retrieval: AgentMemoryRetrieval = Field(default_factory=AgentMemoryRetrieval)
    debug: Dict[str, Any] = Field(default_factory=dict)


class AgentGraphNode(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    influence: float = 0.0
    activity: float = 0.0
    status: AgentStatus = "idle"
    country: Optional[str] = None
    city: Optional[str] = None
    followerCount: int = 0
    followingCount: int = 0
    interactionCount: int = 0


class AgentGraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["follow", "interaction"]
    actionType: Optional[str] = None
    weight: Optional[float] = None
    active: Optional[bool] = None


class AgentActionSummary(BaseModel):
    type: str
    content: str
    reason: str = ""
    timestamp: Optional[str] = None


class AgentOverview(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    bio: str = ""
    status: AgentStatus = "idle"
    influence: float = 0.0
    activity: float = 0.0
    lastAction: Optional[AgentActionSummary] = None
    actionContent: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    occupation: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    following: List[str] = Field(default_factory=list)
    followerCount: int = 0
    followingCount: int = 0
    interactionCount: int = 0
    memory: AgentMemorySnapshot = Field(default_factory=AgentMemorySnapshot)


class AgentMonitorSimulation(BaseModel):
    running: bool = False
    paused: bool = False
    currentStep: int = 0
    currentRound: Optional[int] = None
    platform: Optional[str] = None
    recsys: Optional[str] = None
    topic: Optional[str] = None
    polarization: Optional[float] = None
    propagationScale: Optional[float] = None
    propagationDepth: Optional[float] = None
    propagationBreadth: Optional[float] = None
    herdIndex: Optional[float] = None
    memoryMode: Optional[str] = None


class AgentMonitorGraph(BaseModel):
    nodes: List[AgentGraphNode] = Field(default_factory=list)
    edges: List[AgentGraphEdge] = Field(default_factory=list)


class AgentMonitorResponse(BaseModel):
    simulation: AgentMonitorSimulation
    graph: AgentMonitorGraph
    agents: List[AgentOverview] = Field(default_factory=list)
    updatedAt: str


class AgentDetailProfile(BaseModel):
    id: str
    name: str
    user_name: Optional[str] = None
    bio: str = ""
    personaKey: str = "neutral"
    personaDescription: str = ""
    roleLabel: str = "中立观察者"
    gender: Optional[str] = None
    age: Optional[int] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    occupation: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class AgentDetailStatus(BaseModel):
    state: AgentStatus = "idle"
    influence: float = 0.0
    activity: float = 0.0
    followerCount: int = 0
    followingCount: int = 0
    interactionCount: int = 0
    polarization: Optional[float] = None
    contextTokens: Optional[int] = None
    retrievedMemories: Optional[int] = None
    seenAgentsCount: Optional[int] = None


class AgentTimelineItem(BaseModel):
    timestamp: str
    type: str
    content: str = ""
    reason: Optional[str] = None


class AgentSeenPost(BaseModel):
    postId: str
    author: str
    content: str
    timestamp: str
    numLikes: Optional[int] = None


class AgentDetailResponse(BaseModel):
    profile: AgentDetailProfile
    status: AgentDetailStatus
    currentViewpoint: Optional[str] = None
    lastAction: Optional[AgentActionSummary] = None
    recentTimeline: List[AgentTimelineItem] = Field(default_factory=list)
    seenPosts: List[AgentSeenPost] = Field(default_factory=list)
    memory: AgentMemorySnapshot = Field(default_factory=AgentMemorySnapshot)
