"""
受控Agent服务 - 管理受控agents的业务逻辑
"""
import logging

from app.core.oasis_manager import OASISManager
from app.models.controlled_agents import (
    AddControlledAgentsRequest,
    AddControlledAgentsResponse,
    AgentAddResult,
    ControlledAgentConfig,
)


logger = logging.getLogger(__name__)


class SimulationNotReadyError(Exception):
    """模拟未就绪异常"""
    pass


class ControlledAgentsService:
    """
    受控Agent服务 - 管理受控agents的生命周期

    职责：
    - 添加受控agents到模拟
    - 检查极化率阈值
    - 协调OASIS Manager进行agent创建
    - 错误处理和日志记录
    """

    def __init__(self, oasis_manager: OASISManager):
        """
        初始化受控agent服务

        Args:
            oasis_manager: OASIS管理器实例
        """
        self.oasis_manager = oasis_manager
        logger.info("Controlled Agents Service initialized")

    # ========================================================================
    # 受控Agent管理
    # ========================================================================

    async def add_controlled_agents(
        self,
        request: AddControlledAgentsRequest
    ) -> AddControlledAgentsResponse:
        """
        添加受控agent到模拟中

        Args:
            request: 添加agent请求

        Returns:
            添加结果

        Raises:
            SimulationNotReadyError: 模拟未就绪
        """
        try:
            # 检查模拟状态
            if not self.oasis_manager.is_ready:
                raise SimulationNotReadyError(
                    f"Simulation not ready: {self.oasis_manager.state.value}"
                )

            # 检查极化率（如果需要）
            current_polarization = 0.0

            if request.check_polarization:
                current_polarization = await self._get_polarization()

                if current_polarization < request.polarization_threshold:
                    logger.info(
                        f"Polarization check failed: {current_polarization:.3f} < {request.polarization_threshold:.3f}"
                    )
                    return AddControlledAgentsResponse(
                        success=False,
                        message=(
                            f"当前极化率 {current_polarization:.3f} 低于阈值 "
                            f"{request.polarization_threshold:.3f}，不允许添加受控agent"
                        ),
                        added_count=0,
                        current_polarization=current_polarization,
                        added_agent_ids=[],
                        results=[],
                    )

            # 添加agents
            added_ids = []
            results = []

            for agent_config in request.agents:
                try:
                    agent_id = await self._add_single_controlled_agent(agent_config)
                    added_ids.append(agent_id)
                    results.append(AgentAddResult(
                        agent_id=agent_id,
                        user_name=agent_config.user_name,
                        success=True,
                        error_message=None,
                    ))
                    logger.info(
                        f"Successfully added controlled agent: {agent_id} - {agent_config.user_name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to add agent {agent_config.user_name}: {e}")
                    results.append(AgentAddResult(
                        agent_id=-1,
                        user_name=agent_config.user_name,
                        success=False,
                        error_message=str(e),
                    ))

            return AddControlledAgentsResponse(
                success=len(added_ids) > 0,
                message=f"成功添加 {len(added_ids)} 个受控agent",
                added_count=len(added_ids),
                current_polarization=current_polarization,
                added_agent_ids=added_ids,
                results=results,
            )

        except SimulationNotReadyError:
            raise
        except Exception as e:
            logger.error(f"Failed to add controlled agents: {e}")
            return AddControlledAgentsResponse(
                success=False,
                message=f"添加受控agent失败: {str(e)}",
                added_count=0,
                current_polarization=current_polarization,
                added_agent_ids=[],
                results=[],
            )

    async def _add_single_controlled_agent(
        self,
        config: ControlledAgentConfig
    ) -> int:
        """
        添加单个受控agent

        Args:
            config: Agent配置

        Returns:
            分配的agent ID

        Raises:
            Exception: 添加失败
        """
        from oasis import SocialAgent, UserInfo

        # 获取现有agents以分配新的ID
        existing_agents = self.oasis_manager.get_all_agents()
        max_id = max(
            [agent.social_agent_id for agent in existing_agents],
            default=-1
        )
        agent_id = max_id + 1

        # 构建profile字典，包含interests
        profile = config.profile.copy()
        if config.interests:
            profile['interests'] = config.interests

        # 创建UserInfo
        user_info = UserInfo(
            user_name=config.user_name,
            name=config.name,
            description=config.description,
            profile=profile,
            recsys_type=self.oasis_manager._platform_type.value,
        )

        # 获取可用动作
        available_actions = self.oasis_manager._get_default_actions(
            self.oasis_manager._platform_type
        )

        # 创建SocialAgent
        agent = SocialAgent(
            agent_id=agent_id,
            user_info=user_info,
            agent_graph=self.oasis_manager._agent_graph,
            model=self.oasis_manager._model,
            available_actions=available_actions,
        )

        # 添加到agent graph
        self.oasis_manager._agent_graph.add_agent(agent)

        # 在平台上注册
        await self.oasis_manager._env.platform.sign_up(
            agent_id,
            (config.user_name, config.name, config.description)
        )

        logger.info(f"Added controlled agent {agent_id}: {config.user_name}")
        return agent_id

    async def _get_polarization(self) -> float:
        """
        获取当前极化率

        Returns:
            极化率值 (0.0-1.0)
        """
        try:
            from app.core.dependencies import get_metrics_manager

            metrics_manager = await get_metrics_manager()
            if not metrics_manager:
                logger.warning("MetricsManager not available, returning polarization=0.0")
                return 0.0

            metrics = await metrics_manager.get_metrics_summary()
            if metrics and metrics.polarization:
                return metrics.polarization.average_magnitude

            return 0.0

        except Exception as e:
            logger.error(f"Failed to get polarization: {e}")
            return 0.0
