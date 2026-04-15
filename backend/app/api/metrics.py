"""
Metrics API - REST API endpoints for OASIS metrics

This module provides API endpoints for querying social network analysis metrics
including information propagation, group polarization, and herd effect.
"""

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_metrics_manager_dependency
from app.models.metrics import (
    HerdEffectMetrics,
    MetricsSummary,
    PolarizationMetrics,
    PropagationMetrics,
    Validator,
)
from app.services.metrics.metrics_manager import MetricsManager
from app.utils import metrics_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


# ============================================================================
# Metrics Endpoints
# ============================================================================

@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    service: MetricsManager = Depends(get_metrics_manager_dependency)
):
    """
    获取所有指标摘要

    返回传播、极化率和羊群效应的完整摘要。

    Returns:
        MetricsSummary: 包含所有三个指标的摘要
    """
    try:
        summary = await service.get_metrics_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics summary: {str(e)}"
        )


@router.get("/propagation", response_model=PropagationMetrics)
async def get_propagation_metrics(
    service: MetricsManager = Depends(get_metrics_manager_dependency),
    post_id: Optional[int] = Query(
        None,
        description="分析特定帖子的传播（可选）"
    )
):
    """
    获取信息传播指标

    衡量信息在网络中的扩散范围和深度。

    Args:
        post_id: 可选，特定帖子ID进行分析。如果不提供则返回聚合指标

    Returns:
        PropagationMetrics: 传播指标
    """
    try:
        metrics = await service.propagation_service.get_metrics(post_id)
        return metrics
    except ValueError as e:
        logger.warning(f"Invalid propagation request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get propagation metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve propagation metrics: {str(e)}"
        )


@router.get("/polarization", response_model=PolarizationMetrics)
async def get_polarization_metrics(
    service: MetricsManager = Depends(get_metrics_manager_dependency),
    agent_ids: Optional[str] = Query(
        None,
        description="逗号分隔的agent ID列表（例如：1,2,3）"
    )
):
    """
    获取群体极化指标

    使用LLM评估智能体观点的变化和极端化程度。

    Args:
        agent_ids: 可选，逗号分隔的agent ID。如果不提供则评估所有agent

    Returns:
        PolarizationMetrics: 极化率指标
    """
    try:
        # Parse agent IDs
        ids = Validator.validate_agent_ids(agent_ids)

        metrics = await service.polarization_service.get_metrics(
            agent_ids=ids
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to get polarization metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve polarization metrics: {str(e)}"
        )


@router.get("/herd-effect", response_model=HerdEffectMetrics)
async def get_herd_effect_metrics(
    service: MetricsManager = Depends(get_metrics_manager_dependency),
    time_window_seconds: Optional[int] = Query(
        None,
        description="分析时间窗口（秒），例如：3600表示最近1小时"
    )
):
    """
    获取羊群效应指标

    衡量从众行为和受欢迎度偏差。

    Args:
        time_window_seconds: 可选，时间窗口（秒）。如果不提供则分析所有数据

    Returns:
        HerdEffectMetrics: 羊群效应指标
    """
    try:
        time_window = (
            timedelta(seconds=time_window_seconds)
            if time_window_seconds is not None
            else None
        )

        metrics = await service.herd_service.get_metrics(
            time_window=time_window
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to get herd effect metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve herd effect metrics: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def metrics_health():
    """
    指标服务健康检查

    Returns:
        健康状态
    """
    return {
        "status": "healthy",
        "service": "metrics",
        "timestamp": "2024-01-01T00:00:00"
    }


# ============================================================================
# Metrics History
# ============================================================================

@router.get("/history")
async def get_metrics_history(
    metric_type: Optional[str] = Query(
        None,
        description="指标类型过滤: propagation, polarization, herd_effect"
    ),
    step_from: Optional[int] = Query(
        None,
        description="起始步骤编号"
    ),
    step_to: Optional[int] = Query(
        None,
        description="结束步骤编号"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="返回数量限制"
    ),
    service: MetricsManager = Depends(get_metrics_manager_dependency)
):
    """
    获取指标历史记录

    查询数据库中保存的历史指标数据。

    Args:
        metric_type: 可选，指标类型过滤
        step_from: 可选，起始步骤
        step_to: 可选，结束步骤
        limit: 返回数量限制

    Returns:
        指标历史列表

    Example:
        GET /api/metrics/history?metric_type=propagation&limit=10

        Response:
        {
            "history": [
                {
                    "id": 1,
                    "step_number": 5,
                    "metric_type": "propagation",
                    "metric_data": {...},
                    "calculated_at": "2024-01-01T12:00:00"
                }
            ],
            "total_count": 50
        }
    """
    try:
        # 查询历史记录
        history = metrics_db.get_metrics_history(
            service.db_path,
            metric_type=metric_type,
            step_from=step_from,
            step_to=step_to,
            limit=limit
        )

        # 获取总数
        all_history = metrics_db.get_metrics_history(
            service.db_path,
            metric_type=metric_type,
            step_from=step_from,
            step_to=step_to,
            limit=10000  # 大数字获取所有记录
        )

        return {
            "history": history,
            "total_count": len(all_history)
        }

    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics history: {str(e)}"
        )


@router.get("/history/latest")
async def get_latest_metrics(
    metric_type: str = Query(
        ...,
        description="指标类型: propagation, polarization, herd_effect"
    ),
    service: MetricsManager = Depends(get_metrics_manager_dependency)
):
    """
    获取最新的指标记录

    从数据库中获取指定类型的最新指标数据。

    Args:
        metric_type: 指标类型

    Returns:
        最新指标数据

    Example:
        GET /api/metrics/history/latest?metric_type=propagation

        Response:
        {
            "id": 10,
            "step_number": 50,
            "metric_type": "propagation",
            "metric_data": {...},
            "calculated_at": "2024-01-01T12:00:00"
        }
    """
    try:
        latest = metrics_db.get_latest_metrics(
            service.db_path,
            metric_type
        )

        if not latest:
            raise HTTPException(
                status_code=404,
                detail=f"No metrics found for type: {metric_type}"
            )

        return latest

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve latest metrics: {str(e)}"
        )
