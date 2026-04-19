"""
FastAPI 依赖注入配置

提供应用程序的依赖注入设置，确保单例模式和服务生命周期管理。
"""

import logging
from functools import lru_cache
from typing import AsyncGenerator, Optional

from app.core.config import get_settings
from app.core.oasis_manager import OASISManager, get_oasis_manager

logger = logging.getLogger(__name__)


# ============================================================================
# 服务单例管理
# ============================================================================

_simulation_service = None
_topic_service = None
_metrics_manager = None
_behavior_controller = None
_controlled_agents_service = None


async def get_simulation_service():
    """
    获取模拟服务单例

    Returns:
        SimulationService: 模拟服务实例

    Note:
        这个函数将在实现 SimulationService 后更新
    """
    from app.services.simulation_service import SimulationService

    global _simulation_service

    if _simulation_service is None:
        oasis_manager = await get_oasis_manager()
        _simulation_service = SimulationService(oasis_manager)
        logger.info("Simulation Service singleton created")

    return _simulation_service


# ============================================================================
# OASIS 管理器依赖
# ============================================================================

async def get_oasis_manager_dependency() -> AsyncGenerator[OASISManager, None]:
    """
    OASIS 管理器依赖注入

    Yields:
        OASISManager: OASIS 管理器实例

    Example:
        @router.get("/status")
        async def get_status(manager: OASISManager = Depends(get_oasis_manager_dependency)):
            return manager.get_state_info()
    """
    manager = await get_oasis_manager()
    try:
        yield manager
    except Exception as e:
        logger.error(f"Error in OASIS manager dependency: {e}")
        raise


# ============================================================================
# 模拟服务依赖
# ============================================================================

async def get_simulation_service_dependency():
    """
    模拟服务依赖注入

    Yields:
        SimulationService: 模拟服务实例

    Example:
        @router.post("/step")
        async def execute_step(
            request: StepRequest,
            service: SimulationService = Depends(get_simulation_service_dependency)
        ):
            return await service.step(request)
    """
    service = await get_simulation_service()
    try:
        yield service
    except Exception as e:
        logger.error(f"Error in simulation service dependency: {e}")
        raise


# ============================================================================
# Behavior Controller
# ============================================================================

async def get_behavior_controller():
    """
    获取行为控制器单例

    Returns:
        BehaviorController: 行为控制器实例
    """
    from app.core.behavior_controller import get_behavior_controller as get_bc

    global _behavior_controller

    if _behavior_controller is None:
        _behavior_controller = await get_bc()
        logger.info("Behavior Controller singleton created")

    return _behavior_controller


async def get_behavior_controller_dependency():
    """
    行为控制器依赖注入

    Yields:
        BehaviorController: 行为控制器实例

    Example:
        @router.post("/behavior/config")
        async def update_behavior_config(
            config: BehaviorConfigRequest,
            controller: BehaviorController = Depends(get_behavior_controller_dependency)
        ):
            return await controller.update_agent_behavior(config.agent_id, config.behavior_config)
    """
    controller = await get_behavior_controller()
    try:
        yield controller
    except Exception as e:
        logger.error(f"Error in behavior controller dependency: {e}")
        raise


# ============================================================================
# Topic Service
# ============================================================================

async def get_topic_service():
    """
    获取主题服务单例

    Returns:
        TopicService: 主题服务实例
    """
    from app.services.topic_service import TopicService

    global _topic_service

    if _topic_service is None:
        oasis_manager = await get_oasis_manager()
        _topic_service = TopicService(oasis_manager)
        logger.info("Topic Service singleton created")

    return _topic_service


async def get_topic_service_dependency():
    """
    主题服务依赖注入

    Yields:
        TopicService: 主题服务实例

    Example:
        @router.get("/topics")
        async def list_topics(
            service: TopicService = Depends(get_topic_service_dependency)
        ):
            return service.list_topics()
    """
    service = await get_topic_service()
    try:
        yield service
    except Exception as e:
        logger.error(f"Error in topic service dependency: {e}")
        raise


# ============================================================================
# Metrics Manager
# ============================================================================

async def get_metrics_manager():
    """
    获取指标管理器单例

    Returns:
        MetricsManager: 指标管理器实例

    Note:
        提供集中化的指标计算和缓存功能
    """
    from app.core.config import get_settings
    from app.services.metrics.metrics_manager import MetricsManager

    global _metrics_manager

    if _metrics_manager is None:
        oasis_manager = await get_oasis_manager()
        db_path = oasis_manager._db_path

        if db_path:
            settings = get_settings()
            _metrics_manager = MetricsManager(
                db_path,
                enable_db_persistence=settings.METRICS_ENABLE_DB_PERSISTENCE
            )
            logger.info("Metrics Manager singleton created")
        else:
            logger.debug("Cannot create Metrics Manager: no database path")
            return None

    return _metrics_manager


async def reset_metrics_manager():
    """
    重置指标管理器单例

    在重新配置模拟时调用，确保使用新的数据库路径。
    """
    global _metrics_manager

    if _metrics_manager is not None:
        logger.info("Resetting MetricsManager singleton")
        _metrics_manager = None
    else:
        logger.debug("MetricsManager singleton is None, nothing to reset")


async def get_metrics_manager_dependency():
    """
    指标管理器依赖注入

    Yields:
        MetricsManager: 指标管理器实例

    Example:
        @router.get("/metrics/summary")
        async def get_metrics_summary(
            manager: MetricsManager = Depends(get_metrics_manager_dependency)
        ):
            return await manager.get_metrics_summary()
    """
    manager = await get_metrics_manager()

    if manager is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Metrics manager not available"
        )

    try:
        yield manager
    except Exception as e:
        logger.error(f"Error in metrics manager dependency: {e}")
        raise


# ============================================================================
# 生命周期管理
# ============================================================================

async def startup_event():
    """
    应用启动事件

    在应用启动时执行初始化操作
    """
    settings = get_settings()
    logger.info(f"Starting {settings.PROJECT_NAME}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # 预初始化 OASIS 管理器（延迟加载）
    logger.info("OASIS Manager will be initialized on first use")


async def shutdown_event():
    """
    应用关闭事件

    在应用关闭时执行清理操作
    """
    logger.info("Shutting down application...")

    # 清理主题服务
    global _topic_service
    if _topic_service:
        try:
            # TopicService doesn't have cleanup method, just clear reference
            logger.info("Topic Service reference cleared")
        except Exception as e:
            logger.error(f"Error cleaning up topic service: {e}")
        finally:
            _topic_service = None

    # 清理模拟服务
    global _simulation_service
    if _simulation_service:
        try:
            await _simulation_service.cleanup()
            logger.info("Simulation Service cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up simulation service: {e}")
        finally:
            _simulation_service = None

    # 清理指标管理器
    global _metrics_manager
    if _metrics_manager:
        try:
            # MetricsManager doesn't have cleanup method
            logger.info("Metrics Manager reference cleared")
        except Exception as e:
            logger.error(f"Error cleaning up metrics manager: {e}")
        finally:
            _metrics_manager = None

    # 清理行为控制器
    global _behavior_controller
    if _behavior_controller:
        try:
            # BehaviorController doesn't have cleanup method
            logger.info("Behavior Controller reference cleared")
        except Exception as e:
            logger.error(f"Error cleaning up behavior controller: {e}")
        finally:
            _behavior_controller = None

    # 清理 OASIS 管理器
    try:
        manager = await get_oasis_manager()
        await manager.close()
        logger.info("OASIS Manager cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up OASIS manager: {e}")

    logger.info("Application shutdown complete")


# ============================================================================
# 配置依赖
# ============================================================================

@lru_cache()
def get_settings_cached():
    """
    获取缓存的配置对象

    Returns:
        Settings: 应用配置对象
    """
    return get_settings()


# ============================================================================
# 验证和授权依赖（占位符）
# ============================================================================

async def verify_api_key(api_key: Optional[str] = None) -> bool:
    """
    验证 API 密钥（占位符）

    Args:
        api_key: API 密钥

    Returns:
        bool: 验证结果

    Note:
        这是一个占位符函数，未来可以实现实际的 API 密钥验证
    """
    # TODO: 实现实际的 API 密钥验证
    return True


async def get_current_user(token: Optional[str] = None):
    """
    获取当前用户（占位符）

    Args:
        token: 认证令牌

    Returns:
        用户信息

    Note:
        这是一个占位符函数，未来可以实现实际的用户认证
    """
    # TODO: 实现实际的用户认证
    return {"user_id": "anonymous", "permissions": []}


# ============================================================================
# Controlled Agents Service
# ============================================================================

async def get_controlled_agents_service():
    """
    获取受控agent服务单例

    Returns:
        ControlledAgentsService: 受控agent服务实例
    """
    from app.services.controlled_agents_service import ControlledAgentsService

    global _controlled_agents_service

    if _controlled_agents_service is None:
        oasis_manager = await get_oasis_manager()
        _controlled_agents_service = ControlledAgentsService(oasis_manager)
        logger.info("Controlled Agents Service singleton created")

    return _controlled_agents_service


async def get_controlled_agents_service_dependency():
    """
    受控agent服务依赖注入

    Yields:
        ControlledAgentsService: 受控agent服务实例

    Example:
        @router.post("/agents/controlled")
        async def add_controlled_agents(
            request: AddControlledAgentsRequest,
            service: ControlledAgentsService = Depends(get_controlled_agents_service_dependency)
        ):
            return await service.add_controlled_agents(request)
    """
    service = await get_controlled_agents_service()
    try:
        yield service
    except Exception as e:
        logger.error(f"Error in controlled agents service dependency: {e}")
        raise


# ============================================================================
# 辅助函数
# ============================================================================

def setup_dependencies(app):
    """
    设置应用依赖和生命周期事件

    Args:
        app: FastAPI 应用实例

    Note:
        生命周期事件在 main.py 的 lifespan 上下文管理器中处理
        这里只返回一个包含生命周期方法的对象
    """
    class LifecycleHandlers:
        async def startup_event(self):
            await startup_event()

        async def shutdown_event(self):
            await shutdown_event()

    logger.info("Application dependencies configured")
    return LifecycleHandlers()
