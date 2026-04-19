"""
受控Agent数据模型
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# 受控Agent配置模型
# ============================================================================

class ControlledAgentConfig(BaseModel):
    """受控agent配置"""
    user_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="用户名（唯一标识）"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="显示名称"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="agent描述"
    )
    bio: Optional[str] = Field(
        None,
        max_length=500,
        description="详细传记"
    )
    profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent profile (interests, political_leaning, mbti等)"
    )
    interests: List[str] = Field(
        default_factory=list,
        description="兴趣标签列表"
    )


class AddControlledAgentsRequest(BaseModel):
    """添加受控agent请求"""
    agents: List[ControlledAgentConfig] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="要添加的agent列表"
    )
    check_polarization: bool = Field(
        default=False,
        description="是否在添加前检查极化率阈值"
    )
    polarization_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="极化率阈值（仅当check_polarization=True时生效）"
    )


class AgentAddResult(BaseModel):
    """单个agent添加结果"""
    agent_id: int
    user_name: str
    success: bool
    error_message: Optional[str] = None


class AddControlledAgentsResponse(BaseModel):
    """添加受控agent响应"""
    success: bool
    message: str
    added_count: int = 0
    current_polarization: float = 0.0
    added_agent_ids: List[int] = Field(default_factory=list)
    results: List[AgentAddResult] = Field(default_factory=list)
