"""
行为控制 API 端点

提供 REST API 来管理和配置智能体行为控制系统。
支持概率分布、规则引擎、调度系统和混合策略配置。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query

from app.models.behavior import (
    BehaviorConfigRequest,
    BehaviorProfileRequest,
    ApplyProfileRequest,
    BehaviorConfigResponse,
    BehaviorProfilesResponse,
    AgentBehaviorConfig,
    BehaviorProfile,
    BehaviorStrategy,
    create_default_behavior_config,
    create_probabilistic_config,
    create_scheduled_config,
    create_rule_based_config,
)
from app.core.dependencies import get_behavior_controller_dependency
from app.core.behavior_controller import BehaviorController


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/behavior", tags=["behavior"])


# ============================================================================
# 智能体行为配置端点
# ============================================================================

@router.post("/config", response_model=BehaviorConfigResponse)
async def update_agent_behavior(
    request: BehaviorConfigRequest,
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    更新智能体行为配置

    Args:
        request: 行为配置请求
        controller: 行为控制器实例

    Returns:
        BehaviorConfigResponse: 配置操作结果

    Example:
        POST /api/behavior/config
        {
            "agent_id": 0,
            "behavior_config": {
                "strategy": "probabilistic",
                "probability_distribution": {
                    "name": "balanced",
                    "actions": [
                        {"action_type": "CREATE_POST", "probability": 0.2},
                        {"action_type": "LIKE_POST", "probability": 0.3},
                        {"action_type": "CREATE_COMMENT", "probability": 0.25},
                        {"action_type": "REFRESH", "probability": 0.15},
                        {"action_type": "DO_NOTHING", "probability": 0.1}
                    ]
                },
                "enabled": true
            }
        }

        Response:
        {
            "success": true,
            "message": "Behavior configuration updated for agent 0",
            "agent_id": 0,
            "timestamp": "2024-01-01T12:00:00"
        }
    """
    try:
        success = await controller.update_agent_behavior(
            agent_id=request.agent_id,
            behavior_config=request.behavior_config
        )

        if success:
            return BehaviorConfigResponse(
                success=True,
                message=f"Behavior configuration updated for agent {request.agent_id}",
                agent_id=request.agent_id,
                timestamp=datetime.now()
            )
        else:
            return BehaviorConfigResponse(
                success=False,
                message=f"Failed to update behavior configuration for agent {request.agent_id}",
                agent_id=request.agent_id,
                error="Agent not found or configuration invalid",
                timestamp=datetime.now()
            )

    except Exception as e:
        logger.error(f"Failed to update behavior config for agent {request.agent_id}: {e}")
        return BehaviorConfigResponse(
            success=False,
            message=f"Failed to update behavior configuration: {str(e)}",
            agent_id=request.agent_id,
            error=str(e),
            timestamp=datetime.now()
        )


@router.get("/config/{agent_id}", response_model=AgentBehaviorConfig)
async def get_agent_behavior(
    agent_id: int,
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    获取智能体行为配置

    Args:
        agent_id: 智能体ID
        controller: 行为控制器实例

    Returns:
        AgentBehaviorConfig: 智能体行为配置

    Example:
        GET /api/behavior/config/0

        Response:
        {
            "strategy": "probabilistic",
            "probability_distribution": {...},
            "enabled": true,
            ...
        }
    """
    try:
        config = await controller.get_agent_behavior(agent_id)

        if config is None:
            # 返回默认配置
            config = create_default_behavior_config()

        return config

    except Exception as e:
        logger.error(f"Failed to get behavior config for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get behavior configuration: {str(e)}"
        )


@router.delete("/config/{agent_id}", response_model=BehaviorConfigResponse)
async def reset_agent_behavior(
    agent_id: int,
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    重置智能体行为配置为默认值

    Args:
        agent_id: 智能体ID
        controller: 行为控制器实例

    Returns:
        BehaviorConfigResponse: 重置操作结果
    """
    try:
        # 创建默认配置
        default_config = create_default_behavior_config()

        # 更新为默认配置
        success = await controller.update_agent_behavior(agent_id, default_config)

        if success:
            return BehaviorConfigResponse(
                success=True,
                message=f"Behavior configuration reset to default for agent {agent_id}",
                agent_id=agent_id,
                timestamp=datetime.now()
            )
        else:
            return BehaviorConfigResponse(
                success=False,
                message=f"Failed to reset behavior configuration for agent {agent_id}",
                agent_id=agent_id,
                error="Agent not found",
                timestamp=datetime.now()
            )

    except Exception as e:
        logger.error(f"Failed to reset behavior config for agent {agent_id}: {e}")
        return BehaviorConfigResponse(
            success=False,
            message=f"Failed to reset behavior configuration: {str(e)}",
            agent_id=agent_id,
            error=str(e),
            timestamp=datetime.now()
        )


# ============================================================================
# 批量操作端点
# ============================================================================

@router.post("/config/batch", response_model=List[BehaviorConfigResponse])
async def batch_update_agent_behavior(
    requests: List[BehaviorConfigRequest],
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    批量更新智能体行为配置

    Args:
        requests: 批量行为配置请求列表
        controller: 行为控制器实例

    Returns:
        List[BehaviorConfigResponse]: 批量操作结果列表
    """
    results = []

    for request in requests:
        try:
            success = await controller.update_agent_behavior(
                agent_id=request.agent_id,
                behavior_config=request.behavior_config
            )

            if success:
                results.append(BehaviorConfigResponse(
                    success=True,
                    message=f"Behavior configuration updated for agent {request.agent_id}",
                    agent_id=request.agent_id,
                    timestamp=datetime.now()
                ))
            else:
                results.append(BehaviorConfigResponse(
                    success=False,
                    message=f"Failed to update behavior configuration for agent {request.agent_id}",
                    agent_id=request.agent_id,
                    error="Agent not found or configuration invalid",
                    timestamp=datetime.now()
                ))

        except Exception as e:
            logger.error(f"Failed to update behavior config for agent {request.agent_id}: {e}")
            results.append(BehaviorConfigResponse(
                success=False,
                message=f"Failed to update behavior configuration: {str(e)}",
                agent_id=request.agent_id,
                error=str(e),
                timestamp=datetime.now()
            ))

    return results


@router.post("/config/apply-profile", response_model=List[BehaviorConfigResponse])
async def apply_behavior_profile(
    request: ApplyProfileRequest,
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    应用行为配置模板到智能体

    Args:
        request: 应用模板请求
        controller: 行为控制器实例

    Returns:
        List[BehaviorConfigResponse]: 应用结果列表

    Note:
        这是一个占位端点，实际实现需要行为配置模板存储系统
    """
    # TODO: 实现行为配置模板存储和检索
    # 目前返回未实现错误
    raise HTTPException(
        status_code=501,
        detail="Behavior profile system not yet implemented"
    )


# ============================================================================
# 行为配置模板端点（占位符）
# ============================================================================

@router.post("/profiles", response_model=BehaviorConfigResponse)
async def create_behavior_profile(
    request: BehaviorProfileRequest,
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    创建行为配置模板

    Args:
        request: 行为模板请求
        controller: 行为控制器实例

    Returns:
        BehaviorConfigResponse: 创建结果

    Note:
        这是一个占位端点，实际实现需要行为配置模板存储系统
    """
    # TODO: 实现行为配置模板存储
    raise HTTPException(
        status_code=501,
        detail="Behavior profile system not yet implemented"
    )


@router.get("/profiles", response_model=BehaviorProfilesResponse)
async def list_behavior_profiles(
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    列出所有行为配置模板

    Args:
        controller: 行为控制器实例

    Returns:
        BehaviorProfilesResponse: 模板列表

    Note:
        这是一个占位端点，实际实现需要行为配置模板存储系统
    """
    # TODO: 实现行为配置模板存储
    raise HTTPException(
        status_code=501,
        detail="Behavior profile system not yet implemented"
    )


@router.delete("/profiles/{profile_id}", response_model=BehaviorConfigResponse)
async def delete_behavior_profile(
    profile_id: str,
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    删除行为配置模板

    Args:
        profile_id: 模板ID
        controller: 行为控制器实例

    Returns:
        BehaviorConfigResponse: 删除结果

    Note:
        这是一个占位端点，实际实现需要行为配置模板存储系统
    """
    # TODO: 实现行为配置模板存储
    raise HTTPException(
        status_code=501,
        detail="Behavior profile system not yet implemented"
    )


# ============================================================================
# 预定义配置端点
# ============================================================================

@router.post("/config/preset/{agent_id}", response_model=BehaviorConfigResponse)
async def apply_preset_config(
    agent_id: int,
    preset: str = Query(..., description="预定义配置名称: default, probabilistic, scheduled, rule_based"),
    platform: str = Query("twitter", description="平台类型: twitter, reddit"),
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    应用预定义行为配置

    Args:
        agent_id: 智能体ID
        preset: 预定义配置名称
        platform: 平台类型
        controller: 行为控制器实例

    Returns:
        BehaviorConfigResponse: 应用结果

    Available presets:
        - default: 默认LLM自主决策
        - probabilistic: 概率分布模型
        - scheduled: 时间线调度模型
        - rule_based: 规则引擎模型
    """
    try:
        from app.models.simulation import PlatformType

        platform_type = PlatformType(platform.lower())

        # 根据预设名称创建配置
        if preset == "default":
            config = create_default_behavior_config()
        elif preset == "probabilistic":
            config = create_probabilistic_config(platform=platform_type)
        elif preset == "scheduled":
            config = create_scheduled_config(platform=platform_type)
        elif preset == "rule_based":
            config = create_rule_based_config(platform=platform_type)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown preset: {preset}. Available: default, probabilistic, scheduled, rule_based"
            )

        # 应用配置
        success = await controller.update_agent_behavior(agent_id, config)

        if success:
            return BehaviorConfigResponse(
                success=True,
                message=f"Preset '{preset}' applied to agent {agent_id}",
                agent_id=agent_id,
                timestamp=datetime.now()
            )
        else:
            return BehaviorConfigResponse(
                success=False,
                message=f"Failed to apply preset '{preset}' to agent {agent_id}",
                agent_id=agent_id,
                error="Agent not found",
                timestamp=datetime.now()
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply preset {preset} to agent {agent_id}: {e}")
        return BehaviorConfigResponse(
            success=False,
            message=f"Failed to apply preset configuration: {str(e)}",
            agent_id=agent_id,
            error=str(e),
            timestamp=datetime.now()
        )


# ============================================================================
# 统计信息端点
# ============================================================================

@router.get("/stats")
async def get_behavior_statistics(
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    获取行为控制统计信息

    Args:
        controller: 行为控制器实例

    Returns:
        Dict: 行为控制统计信息
    """
    try:
        stats = controller.get_strategy_stats()

        # 添加控制器状态信息
        return {
            "strategy_statistics": stats,
            "total_agents_with_config": len(controller.agent_behavior_state),
            "controller_initialized": controller._probabilistic_engine is not None or
                                    controller._rule_engine is not None or
                                    controller._scheduling_engine is not None,
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Failed to get behavior statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get behavior statistics: {str(e)}"
        )


# ============================================================================
# 引擎状态端点
# ============================================================================

@router.get("/engine/probabilistic")
async def get_probabilistic_engine_stats(
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    获取概率引擎统计信息

    Args:
        controller: 行为控制器实例

    Returns:
        Dict: 概率引擎统计信息
    """
    try:
        if controller._probabilistic_engine:
            stats = controller._probabilistic_engine.get_statistics()
            return {
                "engine_type": "probabilistic",
                "available": True,
                "statistics": stats,
                "timestamp": datetime.now(),
            }
        else:
            return {
                "engine_type": "probabilistic",
                "available": False,
                "message": "Probabilistic engine not initialized",
                "timestamp": datetime.now(),
            }

    except Exception as e:
        logger.error(f"Failed to get probabilistic engine stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get probabilistic engine statistics: {str(e)}"
        )


@router.get("/engine/rule")
async def get_rule_engine_stats(
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    获取规则引擎统计信息

    Args:
        controller: 行为控制器实例

    Returns:
        Dict: 规则引擎统计信息
    """
    try:
        if controller._rule_engine:
            stats = controller._rule_engine.get_statistics()
            return {
                "engine_type": "rule",
                "available": True,
                "statistics": stats,
                "timestamp": datetime.now(),
            }
        else:
            return {
                "engine_type": "rule",
                "available": False,
                "message": "Rule engine not initialized",
                "timestamp": datetime.now(),
            }

    except Exception as e:
        logger.error(f"Failed to get rule engine stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rule engine statistics: {str(e)}"
        )


@router.get("/engine/scheduling")
async def get_scheduling_engine_stats(
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    获取调度引擎统计信息

    Args:
        controller: 行为控制器实例

    Returns:
        Dict: 调度引擎统计信息
    """
    try:
        if controller._scheduling_engine:
            stats = controller._scheduling_engine.get_statistics()
            return {
                "engine_type": "scheduling",
                "available": True,
                "statistics": stats,
                "timestamp": datetime.now(),
            }
        else:
            return {
                "engine_type": "scheduling",
                "available": False,
                "message": "Scheduling engine not initialized",
                "timestamp": datetime.now(),
            }

    except Exception as e:
        logger.error(f"Failed to get scheduling engine stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduling engine statistics: {str(e)}"
        )


# ============================================================================
# 辅助端点
# ============================================================================

@router.get("/strategies")
async def get_available_strategies():
    """
    获取可用的行为策略类型

    Returns:
        List[Dict]: 可用策略列表
    """
    strategies = []
    for strategy in BehaviorStrategy:
        strategies.append({
            "value": strategy.value,
            "label": strategy.value.replace("_", " ").title(),
            "description": _get_strategy_description(strategy)
        })

    return {"strategies": strategies}


@router.get("/status")
async def get_behavior_controller_status(
    controller: BehaviorController = Depends(get_behavior_controller_dependency)
):
    """
    获取行为控制器状态

    Args:
        controller: 行为控制器实例

    Returns:
        Dict: 行为控制器状态信息
    """
    try:
        # 获取各引擎状态
        def check_engine_available(engine_instance, engine_module, engine_class):
            """检查引擎是否可用（实例存在或可以导入）"""
            if engine_instance is not None:
                return True
            try:
                # 尝试导入引擎类，如果成功则认为引擎可用
                module = __import__(engine_module, fromlist=[engine_class])
                getattr(module, engine_class)
                return True
            except ImportError:
                return False
            except Exception:
                return False

        engines = {
            "probabilistic": check_engine_available(
                controller._probabilistic_engine,
                "app.core.probabilistic_engine",
                "ProbabilisticEngine"
            ),
            "rule": check_engine_available(
                controller._rule_engine,
                "app.core.rule_engine",
                "RuleEngine"
            ),
            "scheduling": check_engine_available(
                controller._scheduling_engine,
                "app.core.scheduling_engine",
                "SchedulingEngine"
            ),
        }

        # 获取策略统计
        strategy_stats = controller.get_strategy_stats()

        return {
            "available": True,
            "engines": engines,
            "strategy_statistics": strategy_stats,
            "agent_config_count": len(controller.agent_behavior_state),
            "oasis_manager_connected": controller.oasis_manager is not None,
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Failed to get behavior controller status: {e}")
        return {
            "available": False,
            "error": str(e),
            "timestamp": datetime.now(),
        }


# ============================================================================
# 辅助函数
# ============================================================================

def _get_strategy_description(strategy: BehaviorStrategy) -> str:
    """获取策略描述"""
    descriptions = {
        BehaviorStrategy.LLM_AUTONOMOUS: "原始LLM自主决策，智能体完全由AI模型控制",
        BehaviorStrategy.PROBABILISTIC: "概率分布模型，基于配置的概率选择动作",
        BehaviorStrategy.RULE_BASED: "规则引擎模型，基于条件和规则触发动作",
        BehaviorStrategy.SCHEDULED: "时间线调度模型，按预定义时间线执行动作",
        BehaviorStrategy.MIXED: "混合策略模型，结合多种策略按权重分配",
    }
    return descriptions.get(strategy, "未知策略")