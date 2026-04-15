"""
OASIS 模拟 API 端点

提供完整的 REST API 来控制和管理 OASIS 多智能体社交网络模拟。
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from fastapi.responses import JSONResponse

from app.models.simulation import (
    SimulationStatus,
    SimulationConfig,
    StepRequest,
    StepType,
    ConfigResult,
    StepResult,
    StatusResult,
    LogFilters,
    LogResult,
)
from app.services.simulation_service import SimulationService
from app.core.dependencies import get_simulation_service_dependency


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sim", tags=["simulation"])


# ============================================================================
# 状态查询端点
# ============================================================================

@router.get("/status", response_model=SimulationStatus)
async def get_status(
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    获取当前模拟状态

    Returns:
        SimulationStatus: 当前模拟的详细状态信息

    Example:
        GET /api/sim/status

        Response:
        {
            "state": "ready",
            "current_step": 5,
            "total_steps": 100,
            "agent_count": 10,
            "platform": "twitter",
            "total_posts": 25,
            "total_interactions": 150,
            "active_agents": 10,
            "agents": [...]
        }
    """
    try:
        return await service.get_status()
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/health")
async def health_check(
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    健康检查端点

    Returns:
        系统健康状态
    """
    try:
        status = await service.get_status()
        return {
            "status": "healthy",
            "simulation_state": status.state.value,
            "oasis_manager_initialized": service.oasis_manager.is_initialized,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


# ============================================================================
# 配置管理端点
# ============================================================================

@router.post("/config", response_model=ConfigResult)
async def update_config(
    config: SimulationConfig,
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    更新模拟配置

    Args:
        config: 新的模拟配置

    Returns:
        ConfigResult: 配置结果

    Example:
        POST /api/sim/config
        {
            "platform": "twitter",
            "agent_count": 20,
            "model_config": {
                "model_platform": "OPENAI",
                "model_type": "GPT_4O_MINI"
            }
        }

        Response:
        {
            "success": true,
            "message": "Simulation configured successfully",
            "simulation_id": "abc123",
            "agents_created": 20
        }
    """
    try:
        logger.info(f"Updating simulation config: {config.platform.value}, {config.agent_count} agents")
        return await service.configure(config)
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        return ConfigResult(
            success=False,
            message=f"Configuration failed: {str(e)}",
            simulation_id=None,
            config=None,
            agents_created=0,
        )


# ============================================================================
# 模拟控制端点
# ============================================================================

@router.post("/step", response_model=StepResult)
async def execute_step(
    request: StepRequest,
    background_tasks: BackgroundTasks,
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    执行模拟步骤

    Args:
        request: 步骤执行请求
        background_tasks: FastAPI 后台任务管理器

    Returns:
        StepResult: 步骤执行结果

    Example:
        自动模式（所有智能体 AI 决策）：
        POST /api/sim/step
        {
            "step_type": "auto"
        }

        手动模式（指定智能体动作）：
        POST /api/sim/step
        {
            "step_type": "manual",
            "manual_actions": [
                {
                    "agent_id": 0,
                    "action_type": "CREATE_POST",
                    "action_args": {"content": "Hello World!"}
                }
            ]
        }

        过滤模式（指定智能体执行）：
        POST /api/sim/step
        {
            "step_type": "auto",
            "agent_filter": [0, 1, 2]
        }
    """
    try:
        # 检查是否需要后台执行
        estimated_duration = _estimate_step_duration(request, service)

        if estimated_duration > 10:  # 超过10秒使用后台任务
            task_id = service.create_background_task(request)
            return StepResult(
                success=True,
                message=f"Step started in background (task_id: {task_id})",
                task_id=task_id,
                step_executed=0,
                actions_taken=0,
            )
        else:
            # 同步执行
            return await service.step(request)

    except Exception as e:
        logger.error(f"Failed to execute step: {e}")
        return StepResult(
            success=False,
            message=f"Step execution failed: {str(e)}",
            step_executed=0,
            actions_taken=0,
        )


@router.get("/step/{task_id}")
async def get_step_result(
    task_id: str,
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    获取后台步骤执行结果

    Args:
        task_id: 任务 ID

    Returns:
        任务执行结果
    """
    result = service.get_task_result(task_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return result


@router.post("/pause", response_model=StatusResult)
async def pause_simulation(
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    暂停模拟

    Returns:
        StatusResult: 操作结果

    Example:
        POST /api/sim/pause

        Response:
        {
            "success": true,
            "message": "Simulation paused",
            "current_state": "paused",
            "timestamp": "2024-01-01T12:00:00"
        }
    """
    try:
        return await service.pause()
    except Exception as e:
        logger.error(f"Failed to pause simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause: {str(e)}")


@router.post("/resume", response_model=StatusResult)
async def resume_simulation(
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    恢复模拟

    Returns:
        StatusResult: 操作结果

    Example:
        POST /api/sim/resume

        Response:
        {
            "success": true,
            "message": "Simulation resumed",
            "current_state": "ready",
            "timestamp": "2024-01-01T12:00:00"
        }
    """
    try:
        return await service.resume()
    except Exception as e:
        logger.error(f"Failed to resume simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume: {str(e)}")


@router.post("/reset", response_model=StatusResult)
async def reset_simulation(
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    重置模拟

    Returns:
        StatusResult: 操作结果

    Example:
        POST /api/sim/reset

        Response:
        {
            "success": true,
            "message": "Simulation reset successfully",
            "current_state": "uninitialized",
            "timestamp": "2024-01-01T12:00:00"
        }
    """
    try:
        return await service.reset()
    except Exception as e:
        logger.error(f"Failed to reset simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")


# ============================================================================
# 日志查询端点
# ============================================================================

@router.get("/logs", response_model=LogResult)
async def get_logs(
    agent_id: Optional[int] = Query(None, description="过滤特定智能体的日志"),
    action_type: Optional[str] = Query(None, description="过滤特定动作类型"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    获取模拟日志

    Args:
        agent_id: 智能体 ID 过滤器
        action_type: 动作类型过滤器
        start_time: 开始时间过滤器
        end_time: 结束时间过滤器
        limit: 返回数量限制
        offset: 分页偏移量

    Returns:
        LogResult: 日志查询结果

    Example:
        GET /api/sim/logs?agent_id=0&action_type=CREATE_POST&limit=50

        Response:
        {
            "total_count": 150,
            "filtered_count": 50,
            "logs": [
                {
                    "timestamp": "2024-01-01T12:00:00",
                    "agent_id": 0,
                    "agent_name": "Alice",
                    "action_type": "CREATE_POST",
                    "content": "Hello World!",
                    "info": {...}
                }
            ],
            "has_more": true
        }
    """
    try:
        from datetime import datetime

        # 构建过滤器
        filters = LogFilters(
            agent_id=agent_id,
            action_type=action_type,
            start_time=datetime.fromisoformat(start_time) if start_time else None,
            end_time=datetime.fromisoformat(end_time) if end_time else None,
            limit=limit,
            offset=offset,
        )

        return await service.get_logs(filters)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


# ============================================================================
# 辅助端点
# ============================================================================

@router.get("/actions")
async def get_available_actions():
    """
    获取可用的动作类型

    Returns:
        可用动作类型列表

    Example:
        GET /api/sim/actions

        Response:
        {
            "twitter_actions": ["CREATE_POST", "LIKE_POST", ...],
            "reddit_actions": ["CREATE_POST", "DISLIKE_POST", ...],
            "all_actions": ["CREATE_POST", "LIKE_POST", ...]
        }
    """
    from oasis import ActionType

    return {
        "twitter_actions": [action.value for action in ActionType.get_default_twitter_actions()],
        "reddit_actions": [action.value for action in ActionType.get_default_reddit_actions()],
        "all_actions": [action.value for action in ActionType],
    }


@router.get("/agents")
async def get_agents(
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    获取所有智能体信息

    Returns:
        智能体列表

    Example:
        GET /api/sim/agents

        Response:
        {
            "agents": [
                {
                    "id": 0,
                    "user_name": "alice",
                    "name": "Alice",
                    "description": "Tech enthusiast",
                    "bio": "...",
                    "interests": ["AI", "technology"]
                }
            ],
            "total_count": 10
        }
    """
    try:
        status = await service.get_status()
        return {
            "agents": status.agents,
            "total_count": len(status.agents),
        }
    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agents: {str(e)}")


@router.get("/agents/{agent_id}")
async def get_agent_detail(
    agent_id: int,
    service: SimulationService = Depends(get_simulation_service_dependency)
):
    """
    获取单个智能体的详细信息

    Args:
        agent_id: 智能体ID

    Returns:
        智能体详细信息，包括档案、统计数据、最近行为等

    Example:
        GET /api/sim/agents/0

        Response:
        {
            "profile": {
                "id": 0,
                "name": "Alice",
                "user_name": "alice",
                "bio": "...",
                "interests": ["AI", "technology"],
                "description": "Tech enthusiast"
            },
            "status": {
                "influence": 0.156,
                "activity": 1.0,
                "follower_count": 5,
                "following_count": 3,
                "interaction_count": 28
            },
            "recent_actions": [
                {
                    "timestamp": "2024-01-01T12:00:00",
                    "action_type": "CREATE_POST",
                    "content": "...",
                    "reason": "..."
                }
            ],
            "recent_posts": [
                {
                    "post_id": 1,
                    "content": "...",
                    "created_at": "2024-01-01T12:00:00",
                    "num_likes": 5
                }
            ]
        }
    """
    try:
        import sqlite3
        import json

        # 获取基本档案信息
        status = await service.get_status()
        agent = next((a for a in status.agents if a.id == agent_id), None)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        # 从数据库获取详细信息
        detail_data = {
            "profile": {
                "id": agent.id,
                "name": agent.name,
                "user_name": agent.user_name,
                "bio": agent.bio or agent.description,
                "interests": agent.interests,
                "description": agent.description,
            },
            "status": {
                "influence": agent.influence,
                "activity": agent.activity,
                "polarization": agent.polarization,
            },
            "recent_actions": [],
            "recent_posts": [],
            "following": [],  # 新增：关注列表
            "followers": [],   # 新增：粉丝列表
        }

        # 查询数据库统计信息
        if service.oasis_manager._db_path and os.path.exists(service.oasis_manager._db_path):
            try:
                conn = sqlite3.connect(service.oasis_manager._db_path)
                cursor = conn.cursor()

                # 查询社交统计
                cursor.execute("SELECT COUNT(DISTINCT follower_id) FROM follow WHERE followee_id = ?", (agent_id,))
                follower_count = cursor.fetchone()[0] or 0

                cursor.execute("SELECT COUNT(DISTINCT followee_id) FROM follow WHERE follower_id = ?", (agent_id,))
                following_count = cursor.fetchone()[0] or 0

                cursor.execute("SELECT COUNT(*) FROM trace WHERE user_id = ?", (agent_id,))
                interaction_count = cursor.fetchone()[0] or 0

                detail_data["status"]["follower_count"] = follower_count
                detail_data["status"]["following_count"] = following_count
                detail_data["status"]["interaction_count"] = interaction_count

                # 查询关注关系（新增）
                cursor.execute("""
                    SELECT followee_id
                    FROM follow
                    WHERE follower_id = ?
                """, (agent_id,))
                detail_data["following"] = [str(row[0]) for row in cursor.fetchall()]

                # 查询粉丝关系（新增）
                cursor.execute("""
                    SELECT follower_id
                    FROM follow
                    WHERE followee_id = ?
                """, (agent_id,))
                detail_data["followers"] = [str(row[0]) for row in cursor.fetchall()]

                # 查询最近行为（最近10条）
                cursor.execute("""
                    SELECT created_at, action, info
                    FROM trace
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (agent_id,))

                for created_at, action, info in cursor.fetchall():
                    try:
                        info_dict = json.loads(info) if info else {}
                        content = info_dict.get("content", "")
                        reason = info_dict.get("reason", "")
                    except:
                        content = ""
                        reason = ""

                    detail_data["recent_actions"].append({
                        "timestamp": created_at,
                        "action_type": action.upper(),
                        "content": content,
                        "reason": reason
                    })

                # 查询最近帖子（最近5条）
                cursor.execute("""
                    SELECT post_id, content, created_at, num_likes, num_dislikes, num_shares
                    FROM post
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (agent_id,))

                for post_id, content, created_at, num_likes, num_dislikes, num_shares in cursor.fetchall():
                    detail_data["recent_posts"].append({
                        "post_id": post_id,
                        "content": content,
                        "created_at": created_at,
                        "num_likes": num_likes or 0,
                        "num_dislikes": num_dislikes or 0,
                        "num_shares": num_shares or 0
                    })

                conn.close()

            except Exception as e:
                logger.warning(f"Failed to query agent details from database: {e}")

        return detail_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent detail: {str(e)}")


# ============================================================================
# 辅助函数
# ============================================================================

def _estimate_step_duration(request: StepRequest, service: SimulationService) -> int:
    """
    估算步骤执行时间（秒）

    Args:
        request: 步骤请求
        service: 模拟服务

    Returns:
        预计执行时间（秒）
    """
    try:
        agent_count = len(request.agent_filter) if request.agent_filter else service.oasis_manager.get_agent_count()

        # 基础时间：每个智能体约 0.5 秒
        base_time = agent_count * 0.5

        # 手动动作更快
        if request.step_type == StepType.MANUAL:
            base_time = len(request.manual_actions) * 0.1

        # 加上网络延迟
        network_delay = 2.0

        return int(base_time + network_delay)

    except Exception:
        # 默认估算：10 秒
        return 10
