from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime
import uuid

from app.memory.config import MemoryMode

# ============================================================================
# 平台和状态枚举
# ============================================================================

class PlatformType(str, Enum):
    """社交媒体平台类型"""
    TWITTER = "twitter"
    REDDIT = "reddit"


class SimulationState(str, Enum):
    """模拟状态枚举"""
    UNINITIALIZED = "uninitialized"
    CONFIGURED = "configured"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETE = "complete"
    ERROR = "error"


class StepType(str, Enum):
    """步骤执行类型"""
    AUTO = "auto"  # LLM 自动决策
    MANUAL = "manual"  # 手动控制


# ============================================================================
# OASIS 动作类型扩展
# ============================================================================

class OASISActionType(str, Enum):
    """OASIS 支持的所有动作类型"""
    # 基础操作
    CREATE_POST = "CREATE_POST"
    CREATE_COMMENT = "CREATE_COMMENT"
    LIKE_POST = "LIKE_POST"
    UNLIKE_POST = "UNLIKE_POST"
    DISLIKE_POST = "DISLIKE_POST"
    UNDO_DISLIKE_POST = "UNDO_DISLIKE_POST"
    REPORT_POST = "REPORT_POST"

    # Twitter 特有
    REPOST = "REPOST"
    QUOTE_POST = "QUOTE_POST"

    # Reddit 特有
    LIKE_COMMENT = "LIKE_COMMENT"
    UNLIKE_COMMENT = "UNLIKE_COMMENT"
    DISLIKE_COMMENT = "DISLIKE_COMMENT"
    UNDO_DISLIKE_COMMENT = "UNDO_DISLIKE_COMMENT"

    # 社交操作
    FOLLOW = "FOLLOW"
    UNFOLLOW = "UNFOLLOW"
    MUTE = "MUTE"
    UNMUTE = "UNMUTE"

    # 搜索和发现
    SEARCH_POSTS = "SEARCH_POSTS"
    SEARCH_USER = "SEARCH_USER"
    TREND = "TREND"
    REFRESH = "REFRESH"

    # 高级功能
    DO_NOTHING = "DO_NOTHING"
    PURCHASE_PRODUCT = "PURCHASE_PRODUCT"
    INTERVIEW = "INTERVIEW"

    # 群组功能
    CREATE_GROUP = "CREATE_GROUP"
    JOIN_GROUP = "JOIN_GROUP"
    LEAVE_GROUP = "LEAVE_GROUP"
    SEND_TO_GROUP = "SEND_TO_GROUP"
    LISTEN_FROM_GROUP = "LISTEN_FROM_GROUP"

    # 系统操作
    EXIT = "EXIT"
    SIGNUP = "SIGNUP"
    UPDATE_REC_TABLE = "UPDATE_REC_TABLE"


# ============================================================================
# 模型配置
# ============================================================================

class ModelConfig(BaseModel):
    """LLM 模型配置"""
    model_platform: str = "DEEPSEEK"
    model_type: str = "DEEPSEEK_CHAT"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=128000)

    # 可选的代理配置
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # 从环境变量读取，不应硬编码


# ============================================================================
# 智能体配置
# ============================================================================

class AgentSource(BaseModel):
    """智能体来源配置"""
    source_type: str = "template"  # template, file, manual
    template_name: Optional[str] = None
    file_path: Optional[str] = None
    manual_config: Optional[List[Dict[str, Any]]] = None


class AgentConfig(BaseModel):
    """单个智能体配置"""
    agent_id: int
    user_name: str
    name: str
    description: str
    bio: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    interests: List[str] = Field(default_factory=list)
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None


# ============================================================================
# 模拟配置
# ============================================================================

class SimulationConfig(BaseModel):
    """模拟配置"""
    platform: PlatformType = PlatformType.TWITTER
    agent_count: int = 5
    memory_mode: MemoryMode = MemoryMode.UPSTREAM
    llm_config: ModelConfig = Field(default_factory=ModelConfig)
    recsys_type: str = "twitter"
    agent_source: AgentSource = Field(default_factory=AgentSource)

    # 模拟限制
    max_steps: int = 50

    # 数据库配置
    db_path: Optional[str] = None

    # 高级选项
    enable_tools: bool = False
    enable_interview: bool = False

    @field_validator('platform', mode='before')
    @classmethod
    def normalize_platform(cls, v):
        if isinstance(v, str):
            return PlatformType(v.lower())
        return v

    @field_validator("memory_mode", mode="before")
    @classmethod
    def normalize_memory_mode(cls, v):
        if isinstance(v, str):
            return MemoryMode(v.lower())
        return v


# ============================================================================
# 步骤执行配置
# ============================================================================

class ManualActionRequest(BaseModel):
    """手动动作请求"""
    agent_id: int
    action_type: OASISActionType
    action_args: Dict[str, Any] = Field(default_factory=dict)


class StepRequest(BaseModel):
    """步骤执行请求"""
    step_type: StepType = StepType.AUTO
    manual_actions: List[ManualActionRequest] = Field(default_factory=list)
    agent_filter: List[int] = Field(default_factory=list)


# ============================================================================
# 响应模型
# ============================================================================

class Agent(BaseModel):
    """智能体信息"""
    id: int
    user_name: str
    name: str
    description: str
    bio: Optional[str] = None
    status: str = "idle"
    polarization: float = 0.0
    influence: float = 0.0
    activity: float = 0.0
    interests: List[str] = Field(default_factory=list)
    following: List[str] = Field(default_factory=list)  # 新增：关注列表


class SimulationStatus(BaseModel):
    """模拟状态响应"""
    state: SimulationState
    current_step: int
    total_steps: int
    agent_count: int
    platform: PlatformType
    memory_mode: MemoryMode = MemoryMode.UPSTREAM
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    background_task_id: Optional[str] = None

    # 统计信息
    total_posts: int = 0
    total_interactions: int = 0
    polarization: float = 0.0

    # 智能体状态
    active_agents: int = 0
    agents: List[Agent] = Field(default_factory=list)

    # 高级指标摘要（可选）
    metrics_summary: Optional['MetricsSummary'] = None

    # 错误信息
    error_message: Optional[str] = None


class MemoryDebugAgentStatus(BaseModel):
    """单个智能体的 memory 调试摘要。"""

    agent_id: int
    user_name: str
    name: str
    memory_runtime: str
    memory_supported: bool = False
    recent_retained_step_count: int = 0
    recent_retained_step_ids: List[int] = Field(default_factory=list)
    compressed_action_block_count: int = 0
    compressed_heartbeat_count: int = 0
    compressed_retained_step_count: int = 0
    total_retained_step_count: int = 0
    last_observation_stage: str = ""
    last_observation_prompt_tokens: int = 0
    last_prompt_tokens: int = 0
    last_recall_gate: Optional[bool] = None
    last_recall_gate_reason_flags: Dict[str, bool] = Field(default_factory=dict)
    last_recall_query_source: str = ""
    last_recall_query_text: str = ""
    last_recalled_count: int = 0
    last_injected_count: int = 0
    last_recalled_step_ids: List[int] = Field(default_factory=list)
    last_injected_step_ids: List[int] = Field(default_factory=list)
    last_recall_reason_trace: str = ""
    last_runtime_failure_category: str = ""
    last_runtime_failure_stage: str = ""
    last_prompt_budget_status: str = ""
    last_selected_recent_step_ids: List[int] = Field(default_factory=list)
    last_selected_compressed_keys: List[str] = Field(default_factory=list)
    last_selected_recall_step_ids: List[int] = Field(default_factory=list)


class MemoryDebugStatus(BaseModel):
    """memory monitor/debug 接口响应。"""

    state: SimulationState
    memory_mode: MemoryMode = MemoryMode.UPSTREAM
    current_step: int = 0
    total_steps: int = 0
    agent_count: int = 0
    platform: PlatformType
    context_token_limit: Optional[int] = None
    generation_max_tokens: Optional[int] = None
    longterm_enabled: bool = False
    agents: List[MemoryDebugAgentStatus] = Field(default_factory=list)


class ConfigResult(BaseModel):
    """配置更新结果"""
    success: bool
    message: str
    simulation_id: Optional[str] = None
    config: Optional[SimulationConfig] = None
    agents_created: int = 0


class StepResult(BaseModel):
    """步骤执行结果"""
    success: bool
    message: str
    task_id: Optional[str] = None
    step_executed: int = 0
    actions_taken: int = 0
    execution_time: Optional[float] = None


class StatusResult(BaseModel):
    """状态操作结果"""
    success: bool
    message: str
    current_state: SimulationState
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# 日志和查询模型
# ============================================================================

class LogEntry(BaseModel):
    """日志条目"""
    timestamp: datetime
    agent_id: int
    agent_name: Optional[str] = None
    action_type: str
    content: Optional[str] = None
    info: Optional[Dict[str, Any]] = None


class LogFilters(BaseModel):
    """日志查询过滤器"""
    agent_id: Optional[int] = None
    action_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class LogResult(BaseModel):
    """日志查询结果"""
    total_count: int
    filtered_count: int
    logs: List[LogEntry]
    has_more: bool


# ============================================================================
# 导出配置
# ============================================================================

class ExportConfig(BaseModel):
    """数据导出配置"""
    format: str = "json"
    include_agents: bool = True
    include_posts: bool = True
    include_interactions: bool = True
    include_comments: bool = False
    include_follows: bool = False

    # 时间范围过滤
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ExportResult(BaseModel):
    """导出结果"""
    success: bool
    message: str
    file_path: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    export_time: Optional[float] = None


# Resolve forward references for MetricsSummary
# This must be called after MetricsSummary is defined in metrics.py
def resolve_simulation_forward_refs():
    """Resolve forward references in simulation models"""
    from app.models.metrics import MetricsSummary
    SimulationStatus.model_rebuild()


# Auto-resolve on import
try:
    resolve_simulation_forward_refs()
except ImportError:
    # Metrics module not imported yet, will be resolved when metrics is imported
    pass
