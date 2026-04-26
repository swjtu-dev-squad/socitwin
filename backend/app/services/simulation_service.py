"""
模拟服务 - 业务逻辑协调层

负责协调 API 层和 OASIS 管理器之间的交互，
实现状态机管理、后台任务处理和业务逻辑。
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union

# OASIS framework imports
from oasis import LLMAction, ManualAction, SocialAgent

from app.core.oasis_manager import OASISManager
from app.models.simulation import (
    ConfigResult,
    LogEntry,
    LogFilters,
    LogResult,
    MemoryDebugStatus,
    PlatformType,
    SimulationConfig,
    SimulationStatus,
    StatusResult,
    StepRequest,
    StepResult,
    StepType,
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

            # 重置 MetricsManager 单例（使用新数据库）
            from app.core.dependencies import reset_metrics_manager
            await reset_metrics_manager()
            logger.info("MetricsManager singleton reset for new simulation")

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
            if result.success:
                from app.core.simulation_events import simulation_event_bus

                await simulation_event_bus.publish(
                    "simulation_step_completed",
                    {
                        "step_executed": result.step_executed,
                        "actions_taken": result.actions_taken,
                        "task_id": task_id,
                    },
                )

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
        from oasis import ActionType, LLMAction, ManualAction

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
                        action_type=action_type,
                        action_args=manual_action.action_args
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

                # 触发异步高级指标计算（非阻塞）
                await self._calculate_advanced_metrics()

        except Exception as e:
            logger.warning(f"Failed to update statistics: {e}")

    async def _calculate_advanced_metrics(self):
        """计算高级指标（信息传播、极化率、羊群效应）"""
        try:
            from app.core.config import get_settings
            from app.core.dependencies import get_metrics_manager

            metrics_manager = await get_metrics_manager()
            if not metrics_manager:
                logger.debug("Metrics manager not available, skipping advanced metrics")
                return

            current_step = self.oasis_manager._current_step
            settings = get_settings()

            # 每5步计算一次极化率（根据配置）
            force_polarization = (
                current_step % getattr(settings, 'POLARIZATION_CALCULATION_INTERVAL', 5) == 0
            )

            # 非阻塞计算指标
            logger.info(f"🔄 Triggering metrics update at step {current_step}, force_polarization={force_polarization}")
            await metrics_manager.update_all_metrics(
                current_step=current_step,
                force_polarization=force_polarization
            )
            logger.info(f"✅ Metrics update completed at step {current_step}")

        except Exception as e:
            logger.warning(f"Failed to schedule advanced metrics calculation: {e}")

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

        logger.info(f"📊 get_status called: db_path={self.oasis_manager._db_path}, current_step={state_info['current_step']}")

        # 获取智能体统计数据（从数据库）
        agent_stats = await self._get_agents_with_stats()

        logger.info(f"📊 agent_stats result: {agent_stats}")

        # 获取智能体信息
        agents = []
        for agent in self.oasis_manager.get_all_agents():
            from app.models.simulation import Agent
            profile = getattr(agent.user_info, 'profile', None) or {}

            # 获取该智能体的统计数据
            stats = agent_stats.get(agent.social_agent_id, {})
            post_count = stats.get('post_count', 0)
            interaction_count = stats.get('interaction_count', 0)
            action_count = stats.get('action_count', 0)

            # 计算影响力和活跃度
            influence = self._calculate_influence(post_count, interaction_count)
            activity = self._calculate_activity(action_count, state_info["current_step"])

            logger.info(f"Agent {agent.social_agent_id}: posts={post_count}, interactions={interaction_count}, actions={action_count}, influence={influence}, activity={activity}")

            # 查询关注列表
            following = []
            if self.oasis_manager._db_path and os.path.exists(self.oasis_manager._db_path):
                try:
                    conn = sqlite3.connect(self.oasis_manager._db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT followee_id FROM follow WHERE follower_id = ?", (agent.social_agent_id,))
                    following = [str(row[0]) for row in cursor.fetchall()]
                    cursor.execute("SELECT follower_id FROM follow WHERE followee_id = ?", (agent.social_agent_id,))
                    [str(row[0]) for row in cursor.fetchall()]
                    conn.close()
                except Exception as e:
                    logger.warning(f"Failed to query follow relationships for agent {agent.social_agent_id}: {e}")

            agents.append(Agent(
                id=agent.social_agent_id,
                user_name=agent.user_info.user_name or "Unknown",
                name=agent.user_info.name or "",
                description=agent.user_info.description or "",
                bio=getattr(agent.user_info, 'bio', None),
                interests=profile.get('interests', []),
                influence=influence,
                activity=activity,
                following=following,
            ))

        # 只获取缓存的metrics，不触发重新计算（保持status响应快速）
        metrics_summary = None
        try:
            from app.core.dependencies import get_metrics_manager
            metrics_manager = await get_metrics_manager()
            if metrics_manager:
                # 只从缓存获取，如果没有缓存就返回None，不触发计算
                try:
                    propagation = await metrics_manager.caches['propagation'].get('propagation')
                    polarization = await metrics_manager.caches['polarization'].get('polarization')
                    herd_effect = await metrics_manager.caches['herd_effect'].get('herd_effect')
                    sentiment_tendency = await metrics_manager.caches['sentiment_tendency'].get(
                        'sentiment_tendency'
                    )

                    # 只有当核心 metrics 都有缓存时才返回
                    if propagation and polarization and herd_effect:
                        from app.models.metrics import MetricsSummary

                        metrics_summary = MetricsSummary(
                            propagation=propagation,
                            polarization=polarization,
                            herd_effect=herd_effect,
                            sentiment_tendency=sentiment_tendency,
                            current_step=state_info["current_step"],
                            timestamp=datetime.now()
                        )
                        logger.debug("Using cached metrics for status endpoint")
                    else:
                        logger.debug(
                            "Metrics not all cached: P=%s, Pol=%s, H=%s, S=%s",
                            bool(propagation),
                            bool(polarization),
                            bool(herd_effect),
                            bool(sentiment_tendency),
                        )
                except Exception as cache_error:
                    logger.warning(f"Failed to get metrics from cache: {cache_error}")

                # 更新polarization字段以保持兼容性
                if metrics_summary and metrics_summary.polarization:
                    self.polarization = metrics_summary.polarization.average_magnitude
        except Exception as e:
            logger.debug(f"Could not fetch metrics summary: {e}")

        return SimulationStatus(
            state=self.oasis_manager.state,
            current_step=state_info["current_step"],
            total_steps=state_info["max_steps"],
            agent_count=state_info["agent_count"],
            platform=PlatformType(state_info["platform"]),
            memory_mode=state_info["memory_mode"],
            context_token_limit=state_info.get("context_token_limit"),
            generation_max_tokens=state_info.get("generation_max_tokens"),
            model_backend_token_limit=state_info.get("model_backend_token_limit"),
            created_at=datetime.fromisoformat(state_info["created_at"]) if state_info["created_at"] else None,
            updated_at=datetime.fromisoformat(state_info["updated_at"]) if state_info["updated_at"] else None,
            total_posts=self.total_posts,
            total_interactions=self.total_interactions,
            polarization=self.polarization,
            active_agents=len(agents),
            agents=agents,
            metrics_summary=metrics_summary,
            error_message=state_info.get("error_message"),
        )

    async def get_memory_debug_status(self) -> MemoryDebugStatus:
        """获取 memory monitor/debug 摘要。"""
        payload = self.oasis_manager.get_memory_debug_info()
        return MemoryDebugStatus.model_validate(payload)

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

    def _calculate_influence(self, post_count: int, total_interactions: int) -> float:
        """
        计算影响力值

        Args:
            post_count: 帖子数
            total_interactions: 总互动数（点赞、评论、分享）

        Returns:
            影响力值 (0-1)
        """
        if post_count == 0 and total_interactions == 0:
            return 0.0

        # 归一化计算
        # 假设：10个帖子 + 50个互动 = 1.0 (最大影响力)
        max_posts = 10.0
        max_interactions = 50.0

        post_score = min(post_count / max_posts, 1.0)
        interaction_score = min(total_interactions / max_interactions, 1.0)

        # 加权平均：帖子权重 0.4，互动权重 0.6
        influence = (post_score * 0.4 + interaction_score * 0.6)

        # 保留两位小数
        return round(min(influence, 1.0), 2)

    async def _get_agents_with_stats(self) -> Dict[int, Dict[str, Any]]:
        """
        从数据库查询每个智能体的统计数据

        Returns:
            字典: {agent_id: {post_count, interaction_count, action_count}}
        """
        if not self.oasis_manager._db_path or not os.path.exists(self.oasis_manager._db_path):
            logger.debug(f"Database not found at: {self.oasis_manager._db_path}")
            return {}

        logger.info(f"📊 Querying agent stats from database: {self.oasis_manager._db_path}")

        conn = sqlite3.connect(self.oasis_manager._db_path)
        cursor = conn.cursor()

        agent_stats = {}

        try:
            # 获取所有智能体ID
            cursor.execute("SELECT DISTINCT user_id FROM user")
            agent_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(agent_ids)} agents in database")

            for agent_id in agent_ids:
                # 帖子数量
                cursor.execute("SELECT COUNT(*) FROM post WHERE user_id = ?", (agent_id,))
                post_count = cursor.fetchone()[0]

                # 互动总数（点赞、评论等）
                cursor.execute("""
                    SELECT COUNT(*) FROM trace
                    WHERE user_id = ? AND action IN ('like_post', 'create_comment', 'repost', 'quote_post', 'share_post')
                """, (agent_id,))
                interaction_count = cursor.fetchone()[0]

                # 有意义的社交行为总数（排除初始化和被动行为）
                cursor.execute("""
                    SELECT COUNT(*) FROM trace
                    WHERE user_id = ? AND action IN (
                        'create_post', 'create_comment',
                        'like_post', 'unlike_post', 'dislike_post',
                        'repost', 'quote_post',
                        'follow', 'unfollow',
                        'share_post'
                    )
                """, (agent_id,))
                action_count = cursor.fetchone()[0]

                agent_stats[agent_id] = {
                    'post_count': post_count,
                    'interaction_count': interaction_count,
                    'action_count': action_count,
                }

            logger.info(f"Agent stats computed: {agent_stats}")

        except Exception as e:
            logger.warning(f"Failed to query agent stats: {e}")
        finally:
            conn.close()

        return agent_stats

    def _calculate_activity(self, action_count: int, current_step: int) -> float:
        """
        计算活跃度值（排除 DO_NOTHING 动作）

        Args:
            action_count: 有意义的行为总数（排除 DO_NOTHING）
            current_step: 当前步数

        Returns:
            活跃度值 (0-100)
        """
        if current_step == 0:
            return 0.0

        # 计算每步平均行为数
        actions_per_step = action_count / current_step

        # 归一化：假设每步 1 个有意义行为 = 100% (最高活跃度)
        max_actions_per_step = 1.0

        activity = min(actions_per_step / max_actions_per_step, 1.0)

        # 转换为百分比 (0-100)
        return round(activity * 100, 1)

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
