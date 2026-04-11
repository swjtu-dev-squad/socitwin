"""
模拟服务 - 业务逻辑协调层

负责协调 API 层和 OASIS 管理器之间的交互，
实现状态机管理、后台任务处理和业务逻辑。
"""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import json

import sqlite3

# OASIS framework imports
from oasis import SocialAgent, LLMAction, ManualAction

from app.core.oasis_manager import (
    OASISManager,
    get_oasis_manager,
    OASISException,
    OASISStateError,
    OASISOperationError,
)
from app.models.simulation import (
    SimulationConfig,
    SimulationStatus,
    SimulationState,
    StepRequest,
    StepType,
    ManualActionRequest,
    ConfigResult,
    StepResult,
    StatusResult,
    LogFilters,
    LogResult,
    LogEntry,
    OASISActionType,
    PlatformType,
)


logger = logging.getLogger(__name__)


class SimulationNotReadyError(Exception):
    """模拟未就绪异常"""
    pass


class SimulationService:
    """
    模拟服务 - 业务逻辑协调器

    职责：
    - 实现模拟状态机
    - 处理后台任务
    - 协调 API 和 OASIS 层
    - 提供数据查询功能
    - 错误恢复和日志记录
    """

    def __init__(self, oasis_manager: OASISManager):
        """
        初始化模拟服务

        Args:
            oasis_manager: OASIS 管理器实例
        """
        self.oasis_manager = oasis_manager

        # 后台任务管理
        self.background_tasks = set()
        self.task_results = {}  # task_id -> result

        # 统计信息
        self.total_posts = 0
        self.total_interactions = 0
        self.polarization = 0.0

        logger.info("Simulation Service initialized")

    # ========================================================================
    # 配置管理
    # ========================================================================

    async def configure(self, config: SimulationConfig) -> ConfigResult:
        """
        配置模拟环境

        Args:
            config: 模拟配置

        Returns:
            配置结果
        """
        try:
            logger.info(f"Configuring simulation: {config.platform.value}")

            # 初始化 OASIS 环境
            init_result = await self.oasis_manager.initialize(config)

            # 重置统计信息
            self.total_posts = 0
            self.total_interactions = 0
            self.polarization = 0.0

            return ConfigResult(
                success=True,
                message="Simulation configured successfully",
                simulation_id=init_result.get("simulation_id"),
                config=config,
                agents_created=init_result["agent_count"],
            )

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return ConfigResult(
                success=False,
                message=f"Configuration failed: {str(e)}",
                simulation_id=None,
                config=None,
                agents_created=0,
            )

    # ========================================================================
    # 步骤执行
    # ========================================================================

    async def step(self, request: StepRequest) -> StepResult:
        """
        执行模拟步骤

        Args:
            request: 步骤请求

        Returns:
            步骤结果
        """
        try:
            if not self.oasis_manager.is_ready:
                raise SimulationNotReadyError(
                    f"Simulation not ready: {self.oasis_manager.state.value}"
                )

            # 构建动作字典
            actions = await self._build_actions(request)

            # 执行步骤
            start_time = time.time()
            result = await self.oasis_manager.step(actions)
            execution_time = time.time() - start_time

            # 更新统计信息
            await self._update_statistics()

            return StepResult(
                success=True,
                message="Step executed successfully",
                step_executed=result["step_executed"],
                actions_taken=result.get("actions_count", 0),
                execution_time=execution_time,
            )

        except SimulationNotReadyError as e:
            logger.warning(f"Step execution failed: {e}")
            return StepResult(
                success=False,
                message=str(e),
                step_executed=0,
                actions_taken=0,
            )
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return StepResult(
                success=False,
                message=f"Step execution failed: {str(e)}",
                step_executed=0,
                actions_taken=0,
            )

    async def execute_step_async(
        self, task_id: str, request: StepRequest
    ) -> None:
        """
        在后台执行步骤

        Args:
            task_id: 任务 ID
            request: 步骤请求
        """
        try:
            logger.info(f"Executing background step: {task_id}")

            # 执行步骤
            result = await self.step(request)

            # 保存结果
            self.task_results[task_id] = {
                "result": result,
                "completed": True,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Background step completed: {task_id}")

        except Exception as e:
            logger.error(f"Background step failed: {task_id}, error: {e}")
            self.task_results[task_id] = {
                "result": None,
                "error": str(e),
                "completed": False,
                "timestamp": datetime.now().isoformat(),
            }

    async def _build_actions(
        self, request: StepRequest
    ) -> Dict[SocialAgent, Union[LLMAction, ManualAction]]:
        """构建动作字典"""
        from oasis import LLMAction, ManualAction, ActionType

        actions = {}

        # 获取智能体列表
        if request.agent_filter:
            agents = []
            for agent_id in request.agent_filter:
                agent = self.oasis_manager.get_agent(agent_id)
                if agent:
                    agents.append(agent)
        else:
            agents = self.oasis_manager.get_all_agents()

        # 根据步骤类型构建动作
        if request.step_type == StepType.AUTO:
            # LLM 自动决策
            for agent in agents:
                actions[agent] = LLMAction()

        elif request.step_type == StepType.MANUAL:
            # 手动控制
            for manual_action in request.manual_actions:
                agent = self.oasis_manager.get_agent(manual_action.agent_id)
                if agent:
                    action_type = getattr(ActionType, manual_action.action_type.value)
                    actions[agent] = ManualAction(
                        action=action_type,
                        args=manual_action.action_args
                    )

        return actions

    async def _update_statistics(self):
        """更新统计信息"""
        try:
            # 从数据库查询统计信息
            if self.oasis_manager._db_path and os.path.exists(self.oasis_manager._db_path):
                conn = sqlite3.connect(self.oasis_manager._db_path)
                cursor = conn.cursor()

                # 帖子总数
                cursor.execute("SELECT COUNT(*) FROM post")
                self.total_posts = cursor.fetchone()[0]

                # 互动总数
                cursor.execute("SELECT COUNT(*) FROM trace")
                self.total_interactions = cursor.fetchone()[0]

                conn.close()

                logger.debug(f"Statistics updated: {self.total_posts} posts, {self.total_interactions} interactions")

        except Exception as e:
            logger.warning(f"Failed to update statistics: {e}")

    # ========================================================================
    # 状态控制
    # ========================================================================

    async def pause(self) -> StatusResult:
        """暂停模拟"""
        try:
            result = await self.oasis_manager.pause()
            return StatusResult(
                success=result["success"],
                message=result["message"],
                current_state=self.oasis_manager.state,
            )
        except Exception as e:
            logger.error(f"Pause failed: {e}")
            return StatusResult(
                success=False,
                message=f"Pause failed: {str(e)}",
                current_state=self.oasis_manager.state,
            )

    async def resume(self) -> StatusResult:
        """恢复模拟"""
        try:
            result = await self.oasis_manager.resume()
            return StatusResult(
                success=result["success"],
                message=result["message"],
                current_state=self.oasis_manager.state,
            )
        except Exception as e:
            logger.error(f"Resume failed: {e}")
            return StatusResult(
                success=False,
                message=f"Resume failed: {str(e)}",
                current_state=self.oasis_manager.state,
            )

    async def reset(self) -> StatusResult:
        """重置模拟"""
        try:
            result = await self.oasis_manager.reset()

            # 清理后台任务
            await self._cleanup_background_tasks()

            # 重置统计信息
            self.total_posts = 0
            self.total_interactions = 0
            self.polarization = 0.0

            return StatusResult(
                success=result["success"],
                message=result["message"],
                current_state=self.oasis_manager.state,
            )
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return StatusResult(
                success=False,
                message=f"Reset failed: {str(e)}",
                current_state=self.oasis_manager.state,
            )

    # ========================================================================
    # 状态查询
    # ========================================================================

    async def get_status(self) -> SimulationStatus:
        """
        获取模拟状态

        Returns:
            模拟状态
        """
        state_info = self.oasis_manager.get_state_info()

        # 获取智能体信息
        agents = []
        for agent in self.oasis_manager.get_all_agents():
            from app.models.simulation import Agent
            profile = getattr(agent.user_info, 'profile', None) or {}
            agents.append(Agent(
                id=agent.social_agent_id,
                user_name=agent.user_info.user_name,
                name=agent.user_info.name,
                description=agent.user_info.description,
                bio=getattr(agent.user_info, 'bio', None),
                interests=profile.get('interests', []),
            ))

        return SimulationStatus(
            state=self.oasis_manager.state,
            current_step=state_info["current_step"],
            total_steps=state_info["max_steps"],
            agent_count=state_info["agent_count"],
            platform=PlatformType(state_info["platform"]),
            created_at=datetime.fromisoformat(state_info["created_at"]) if state_info["created_at"] else None,
            updated_at=datetime.fromisoformat(state_info["updated_at"]) if state_info["updated_at"] else None,
            total_posts=self.total_posts,
            total_interactions=self.total_interactions,
            polarization=self.polarization,
            active_agents=len(agents),
            agents=agents,
        )

    # ========================================================================
    # 日志查询
    # ========================================================================

    async def get_logs(self, filters: LogFilters) -> LogResult:
        """
        获取模拟日志

        Args:
            filters: 日志过滤器

        Returns:
            日志结果
        """
        try:
            if not self.oasis_manager._db_path or not os.path.exists(self.oasis_manager._db_path):
                return LogResult(
                    total_count=0,
                    filtered_count=0,
                    logs=[],
                    has_more=False,
                )

            conn = sqlite3.connect(self.oasis_manager._db_path)
            cursor = conn.cursor()

            # 构建查询
            query = "SELECT * FROM trace WHERE 1=1"
            params = []

            if filters.agent_id is not None:
                query += " AND user_id = ?"
                params.append(filters.agent_id)

            if filters.action_type:
                query += " AND action = ?"
                params.append(filters.action_type)

            if filters.start_time:
                query += " AND created_at >= ?"
                params.append(filters.start_time.isoformat())

            if filters.end_time:
                query += " AND created_at <= ?"
                params.append(filters.end_time.isoformat())

            # 获取总数
            count_query = query.replace("*", "COUNT(*)")
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # 添加分页
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([filters.limit, filters.offset])

            # 执行查询
            cursor.execute(query, params)
            rows = cursor.fetchall()

            # 转换为日志条目
            logs = []
            for row in rows:
                # 解析 trace 表结构
                # 假设结构: user_id, created_at, action, info
                user_id, created_at, action, info = row[:4]

                # 解析 info JSON
                info_data = None
                try:
                    if info:
                        info_data = json.loads(info)
                except json.JSONDecodeError:
                    pass

                # 获取智能体名称
                agent_name = None
                agent = self.oasis_manager.get_agent(user_id)
                if agent:
                    agent_name = agent.user_info.name

                logs.append(LogEntry(
                    timestamp=datetime.fromisoformat(created_at),
                    agent_id=user_id,
                    agent_name=agent_name,
                    action_type=action,
                    content=info_data.get("content") if info_data else None,
                    info=info_data,
                ))

            conn.close()

            return LogResult(
                total_count=total_count,
                filtered_count=len(logs),
                logs=logs,
                has_more=(filters.offset + len(logs)) < total_count,
            )

        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return LogResult(
                total_count=0,
                filtered_count=0,
                logs=[],
                has_more=False,
            )

    # ========================================================================
    # 后台任务管理
    # ========================================================================

    def create_background_task(
        self, request: StepRequest
    ) -> str:
        """
        创建后台任务

        Args:
            request: 步骤请求

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())

        # 创建后台任务
        task = asyncio.create_task(
            self.execute_step_async(task_id, request)
        )

        # 添加到任务集合
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

        logger.info(f"Created background task: {task_id}")

        return task_id

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取后台任务结果

        Args:
            task_id: 任务 ID

        Returns:
            任务结果或 None
        """
        return self.task_results.get(task_id)

    async def _cleanup_background_tasks(self):
        """清理后台任务"""
        # 取消所有运行中的任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # 等待任务取消
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # 清空集合
        self.background_tasks.clear()
        self.task_results.clear()

        logger.info("Background tasks cleaned up")

    # ========================================================================
    # 资源清理
    # ========================================================================

    async def cleanup(self):
        """清理服务资源"""
        try:
            await self._cleanup_background_tasks()
            logger.info("Simulation Service cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")