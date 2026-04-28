"""
受控Agent API端点
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_controlled_agents_service_dependency
from app.models.controlled_agents import (
    AddControlledAgentsRequest,
    AddControlledAgentsResponse,
)
from app.services.controlled_agents_service import ControlledAgentsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sim/agents", tags=["controlled-agents"])


# ============================================================================
# 受控Agent管理端点
# ============================================================================

@router.post(
    "/controlled",
    response_model=AddControlledAgentsResponse,
    status_code=200
)
async def add_controlled_agents(
    request: AddControlledAgentsRequest,
    service: ControlledAgentsService = Depends(get_controlled_agents_service_dependency)
):
    """
    手动添加受控agent用于舆论引导

    Args:
        request: 添加agent请求
        service: 受控agent服务实例

    Returns:
        添加结果

    Example:
        添加单个agent（不检查极化率）：
        POST /api/sim/agents/controlled
        {
            "agents": [
                {
                    "user_name": "moderator_alice",
                    "name": "Alice Moderator",
                    "description": "平衡观点的调解者",
                    "bio": "专注于促进理解和对话",
                    "profile": {
                        "political_leaning": "center",
                        "mbti": "INFJ"
                    },
                    "interests": ["dialogue", "understanding", "compromise"]
                }
            ],
            "check_polarization": false
        }

        批量添加agent（检查极化率阈值）：
        POST /api/sim/agents/controlled
        {
            "agents": [
                {
                    "user_name": "moderator_1",
                    "name": "Moderator One",
                    "description": "调解者1号",
                    "profile": {"political_leaning": "center"},
                    "interests": ["balance"]
                },
                {
                    "user_name": "moderator_2",
                    "name": "Moderator Two",
                    "description": "调解者2号",
                    "profile": {"political_leaning": "center"},
                    "interests": ["balance"]
                }
            ],
            "check_polarization": true,
            "polarization_threshold": 0.6
        }

    Response:
        {
            "success": true,
            "message": "成功添加 2 个受控agent",
            "added_count": 2,
            "current_polarization": 0.65,
            "added_agent_ids": [10, 11],
            "results": [
                {
                    "agent_id": 10,
                    "user_name": "moderator_1",
                    "success": true,
                    "error_message": null
                },
                {
                    "agent_id": 11,
                    "user_name": "moderator_2",
                    "success": true,
                    "error_message": null
                }
            ]
        }
    """
    try:
        logger.info(
            f"Adding {len(request.agents)} controlled agents, "
            f"check_polarization={request.check_polarization}"
        )
        return await service.add_controlled_agents(request)

    except Exception as e:
        logger.error(f"Failed to add controlled agents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add controlled agents: {str(e)}"
        )
