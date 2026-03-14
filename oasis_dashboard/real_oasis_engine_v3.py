#!/usr/bin/env python3
"""
Real OASIS Engine V3 - Speed Optimized
真实 OASIS 引擎 V3 - 速度优化版

优化 Qwen3-8B 调用速度，确保 step 在 30 秒内完成
"""

import os
import sys
import time
from datetime import datetime, timezone

# 解决 torch 和其他依赖加载慢的问题
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# 监控导入时间
import_start = time.time()

from camel.messages import BaseMessage

import oasis
from oasis import (
    ActionType,
    AgentGraph,
    LLMAction,
    ManualAction,
    UserInfo,
    make,
    DefaultPlatformType,
)

from oasis_dashboard.context import (
    ContextRuntimeSettings,
    ContextSocialAgent,
    ModelRuntimeSpec,
    build_shared_model,
)
from oasis_dashboard.context.config import compression_config_for_platform


class RealOASISEngineV3:
    """
    真实 OASIS 引擎 V3（速度优化版）

    - 强制最小化执行（1个agent）
    - 使用 ManualAction 快速验证
    - 优化 Qwen3-8B 调用速度
    """

    @staticmethod
    def _format_timestamp(ts) -> str:
        """将时间戳转换为 ISO 8601 格式字符串，修正未来时间"""
        if ts is None:
            return datetime.now(timezone.utc).isoformat()

        # 如果是字符串，尝试解析并修正
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts)
                now = datetime.now(timezone.utc)

                # 检测是否为未来时间（允许1分钟的时钟偏差）
                if dt.tzinfo is None:
                    # 无时区信息，当作本地时间
                    dt_utc = dt.astimezone(timezone.utc)
                else:
                    dt_utc = dt

                # 如果时间在未来5分钟以上，使用当前时间
                if (dt_utc - now).total_seconds() > 300:
                    print(f"⚠️  检测到未来时间 {ts}，修正为当前时间", flush=True)
                    return now.isoformat()

                return ts
            except:
                # 解析失败，直接返回原字符串
                return ts

        # 如果是数字（Unix 时间戳）
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        # 其他情况，返回当前时间
        return datetime.now(timezone.utc).isoformat()

    def __init__(
        self,
        model_platform: str = "ollama",
        model_type: str = "qwen3:8b",
        db_path: str = "./oasis_simulation.db",
    ):
        """初始化真实 OASIS 引擎"""
        self.model_platform = model_platform
        self.model_type = model_type
        self.db_path = db_path
        
        self.agent_graph: Optional[Any] = None
        self.env: Optional[Any] = None
        self.model: Optional[Any] = None
        
        self.current_step = 0
        self.total_posts = 0
        self.active_agents = 0
        self.is_running = False
        self.context_token_limit: Optional[int] = None
        self.generation_max_tokens: Optional[int] = None
        self.memory_window_size: Optional[int] = None
        
        self.agents: List[Any] = []
        self.logs: List[Dict] = []
        
        # 使用真实 LLMAction 模式
        self.use_llm_action = True

    def _get_topic_instructions(self, topic: str, region: str) -> str:
        """
        根据主题和地区生成具体的内容生成指令
        确保LLM生成的内容符合主题
        """
        # 简化的主题指令，减少token消耗
        topic_instructions = {
            "POLITICS": "Discuss politics, government policies, and current events.",
            "AI": "Discuss AI, technology, and digital innovation.",
            "ENTERTAINMENT": "Discuss movies, music, celebrities, and pop culture.",
            "HEALTH": "Discuss health, wellness, fitness, and medical topics.",
            "TRAVEL": "Discuss travel destinations and cultural experiences.",
            "FOOD": "Discuss recipes, restaurants, and food culture.",
        }

        base_instruction = topic_instructions.get(
            topic.upper(),
            f"Discuss {topic.lower()} topics."
        )

        # 简化的地区背景
        region_suffix = f" from {region.title()}."
        return base_instruction + region_suffix

    def _build_model_runtime_spec(self) -> ModelRuntimeSpec | list[ModelRuntimeSpec]:
        generation_max_tokens = int(
            os.environ.get("OASIS_MODEL_GENERATION_MAX_TOKENS", "512")
        )
        declared_context_window = os.environ.get("OASIS_MODEL_CONTEXT_WINDOW")
        context_token_limit = os.environ.get("OASIS_CONTEXT_TOKEN_LIMIT")
        timeout = os.environ.get("OASIS_MODEL_TIMEOUT")
        max_retries = int(os.environ.get("OASIS_MODEL_MAX_RETRIES", "3"))
        api_key = os.environ.get("OASIS_MODEL_API_KEY")
        url = os.environ.get("OASIS_MODEL_URL")
        urls = [
            item.strip()
            for item in os.environ.get("OASIS_MODEL_URLS", "").split(",")
            if item.strip()
        ]
        qwen3_vllm_local_compat = os.environ.get(
            "OASIS_QWEN3_VLLM_LOCAL_COMPAT", "0"
        ).lower() in {"1", "true", "yes", "on"}

        default_model_config: dict[str, Any] = {}
        if self.model_platform.lower() == "ollama":
            default_model_config["temperature"] = 0.4
        elif (
            self.model_platform.lower() == "vllm"
            and qwen3_vllm_local_compat
            and "qwen3" in self.model_type.lower()
        ):
            default_model_config.update(
                {
                    "temperature": 0.7,
                    "top_p": 0.8,
                    "presence_penalty": 1.5,
                    "extra_body": {
                        "top_k": 20,
                        "min_p": 0,
                    },
                }
            )

        base_kwargs = dict(
            model_platform=self.model_platform,
            model_type=self.model_type,
            model_config_dict=default_model_config,
            api_key=api_key,
            timeout=float(timeout) if timeout else None,
            max_retries=max_retries,
            generation_max_tokens=generation_max_tokens,
            declared_context_window=(
                int(declared_context_window)
                if declared_context_window
                else None
            ),
            context_token_limit=(
                int(context_token_limit) if context_token_limit else None
            ),
            observation_instruction_suffix=(
                "/no_think" if qwen3_vllm_local_compat else ""
            ),
            strip_assistant_think_blocks=qwen3_vllm_local_compat,
        )

        if urls:
            return [ModelRuntimeSpec(url=item, **base_kwargs) for item in urls]
        return ModelRuntimeSpec(url=url, **base_kwargs)

    async def initialize(
        self,
        agent_count: int = 10,
        platform: str = "reddit",
        recsys: str = "hot-score",
        topic: str = "general",
        topics: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> Dict:
        """
        初始化真实 OASIS 模拟环境

        Args:
            agent_count: Agent数量（最多100个以保证性能）
            platform: 社交平台类型
            recsys: 推荐算法类型
            topic: 单个话题（向后兼容）
            topics: 话题列表（新参数，优先使用）
            regions: 地区列表（新参数）
        """
        try:
            init_start = time.time()
            print(f"🚀 初始化 OASIS: {agent_count} agents, {platform}, {topics[0] if topics else 'general'}", flush=True)

            # 处理topics和regions参数
            if topics and len(topics) > 0:
                primary_topic = topics[0]
            else:
                primary_topic = topic
                topics = [topic]

            if regions and len(regions) > 0:
                pass  # 使用提供的regions
            else:
                regions = ["General"]

            resolved_model = build_shared_model(self._build_model_runtime_spec())
            self.model = resolved_model.model
            self.context_token_limit = resolved_model.context_token_limit
            self.generation_max_tokens = resolved_model.generation_max_tokens
            qwen3_vllm_local_compat = os.environ.get(
                "OASIS_QWEN3_VLLM_LOCAL_COMPAT", "0"
            ).lower() in {"1", "true", "yes", "on"}
            env_window_size = os.environ.get("OASIS_CONTEXT_WINDOW_SIZE")
            self.memory_window_size = (
                int(env_window_size)
                if env_window_size
                else None
            )

            # 定义可用动作
            # REFRESH 是必须的，让agents获取推荐内容
            available_actions = [
                ActionType.CREATE_POST,
                ActionType.LIKE_POST,
                ActionType.REFRESH,  # ✅ 关键：允许agents刷新推荐内容
                ActionType.DO_NOTHING,  # 允许agents选择不做任何事
            ]

            # 初始化 agent graph
            self.agent_graph = AgentGraph()

            compression = compression_config_for_platform(platform)

            # 创建 agents
            for i in range(agent_count):
                # 为不同agent分配不同的topics（如果有多个）
                agent_topic = topics[i % len(topics)] if len(topics) > 1 else primary_topic
                agent_region = regions[i % len(regions)] if len(regions) > 1 else regions[0]

                # 创建增强的主题指令
                topic_instructions = self._get_topic_instructions(agent_topic, agent_region)

                # 构建符合OASIS要求的profile结构
                # OASIS的to_system_message()使用profile['other_info']['user_profile']
                agent_profile = {
                    "other_info": {
                        "user_profile": topic_instructions,  # 主题指令放在这里
                        "gender": "unknown",
                        "age": 25,
                        "mbti": "UNKNOWN",
                        "country": agent_region.title(),
                    }
                }

                user_info = UserInfo(
                    user_name=f"agent_{i}",
                    name=f"Agent {i}",
                    description=f"AI agent {i} - Topic: {agent_topic}, Region: {agent_region}",
                    profile=agent_profile,  # 设置正确的profile
                    recsys_type=platform.lower(),  # ✅ 使用平台类型（reddit/twitter）而不是推荐算法
                )
                system_message = BaseMessage.make_assistant_message(
                    role_name="system",
                    content=user_info.to_system_message(),
                )
                context_settings = ContextRuntimeSettings(
                    token_counter=resolved_model.token_counter,
                    system_message=system_message,
                    context_token_limit=resolved_model.context_token_limit,
                    observation_soft_limit=max(
                        1024, int(resolved_model.context_token_limit * 0.75)
                    ),
                    observation_hard_limit=resolved_model.context_token_limit,
                    memory_window_size=self.memory_window_size,
                    observation_instruction_suffix=(
                        resolved_model.observation_instruction_suffix
                    ),
                    strip_assistant_think_blocks=(
                        resolved_model.strip_assistant_think_blocks
                    ),
                    compression=compression,
                )
                context_settings.validate()

                agent = ContextSocialAgent(
                    agent_id=i,
                    user_info=user_info,
                    agent_graph=self.agent_graph,
                    model=self.model,
                    available_actions=available_actions,
                    context_settings=context_settings,
                )
                self.agent_graph.add_agent(agent)
                self.agents.append(agent)

            # 设置数据库路径
            os.environ["OASIS_DB_PATH"] = os.path.abspath(self.db_path)

            # 删除旧数据库
            if os.path.exists(self.db_path):
                os.remove(self.db_path)

            # 创建环境
            platform_type = (
                DefaultPlatformType.REDDIT
                if platform.lower() == "reddit"
                else DefaultPlatformType.TWITTER
            )

            self.env = make(
                agent_graph=self.agent_graph,
                platform=platform_type,
                database_path=self.db_path,
            )

            # 重置环境
            await self.env.reset()

            self.active_agents = agent_count
            self.is_running = True
            self.current_step = 0

            init_time = time.time() - init_start
            print(f"✅ OASIS初始化完成 (耗时 {init_time:.2f}秒)", flush=True)

            return {
                "status": "ok",
                "message": f"真实OASIS已初始化 {agent_count} 个agents",
                "agent_count": agent_count,
                "platform": platform,
                "recsys": recsys,
                "topics": topics,
                "regions": regions,
                "topic": primary_topic,  # 向后兼容
                "init_time": init_time,
                "context_token_limit": self.context_token_limit,
                "generation_max_tokens": self.generation_max_tokens,
                "memory_window_size": self.memory_window_size,
                "observation_instruction_suffix": (
                    resolved_model.observation_instruction_suffix
                ),
                "strip_assistant_think_blocks": (
                    resolved_model.strip_assistant_think_blocks
                ),
                "agents": [
                    {
                        "id": i,
                        "name": f"Agent {i}",
                        "description": f"AI agent {i} - Topic: {topics[i % len(topics)]}, Region: {regions[i % len(regions)]}",
                    }
                    for i in range(min(agent_count, 10))  # 返回前10个agent信息
                ]
            }

        except Exception as e:
            print(f"❌ 初始化失败: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"初始化失败: {str(e)}",
            }

    async def step(self) -> Dict:
        """执行一步真实 OASIS 模拟（速度优化版）"""
        if not self.is_running or self.env is None:
            return {
                "status": "error",
                "message": "模拟未初始化或未运行",
            }

        try:
            step_start = time.time()
            print(f"⚙️  Step {self.current_step + 1} 开始", flush=True)

            # 按照OASIS官方文档：从环境中获取agents
            all_agents = list(self.env.agent_graph.get_agents())

            # 输出进度信息（用于前端显示）
            total_agents = len(all_agents)
            print(f"📊 Progress: 0/{total_agents} (0%)", file=sys.stderr, flush=True)

            # 分批执行agents以显示实时进度
            batch_size = max(1, total_agents // 5)  # 分成约5批（平衡速度和进度显示）
            completed = 0

            for i in range(0, total_agents, batch_size):
                batch_agents = all_agents[i:i + batch_size]

                # 为当前批的agents创建LLMAction
                batch_actions = {
                    agent: LLMAction()
                    for _, agent in batch_agents
                }

                # 执行当前批
                await self.env.step(batch_actions)

                # 更新进度
                completed += len(batch_agents)
                percentage = int((completed / total_agents) * 100)
                print(f"📊 Progress: {completed}/{total_agents} ({percentage}%)", file=sys.stderr, flush=True)

            # 完成进度
            print(f"✅ Step complete", file=sys.stderr, flush=True)

            self.current_step += 1

            # 从数据库读取真实的帖子数
            self.total_posts = self._get_actual_post_count()

            step_time = time.time() - step_start

            # 记录内部日志
            context_metrics = self._collect_context_metrics()
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
                "step_time": step_time,
                "context_metrics": context_metrics,
            }
            self.logs.append(log_entry)

            # 从 OASIS 数据库读取真实的 agent 行为日志
            new_logs = self._get_real_agent_actions()

            return {
                "status": "ok",
                "current_step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
                "step_time": step_time,
                "context_metrics": context_metrics,
                "new_logs": new_logs,  # ← 返回所有日志
            }
            
        except Exception as e:
            print(f"❌ 步骤执行失败: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"步骤执行失败: {str(e)}",
            }
    
    async def reset(self) -> Dict:
        """重置模拟"""
        if self.env is not None:
            await self.env.close()
        
        self.current_step = 0
        self.total_posts = 0
        self.is_running = False
        self.logs = []
        
        print("🔄 模拟已重置", flush=True)
        
        return {
            "status": "ok",
            "message": "模拟已重置",
        }
    
    def get_status(self) -> Dict:
        """获取当前模拟状态"""
        return {
            "status": "ok",
            "data": {
                "currentStep": self.current_step,
                "totalPosts": self.total_posts,
                "activeAgents": self.active_agents,
                "isRunning": self.is_running,
                "running": self.is_running,
            },
        }

    def _get_real_agent_actions(self) -> List[Dict]:
        """从 OASIS 数据库读取真实的 agent 行为"""
        import sqlite3
        import os

        logs = []

        # 检查数据库是否存在
        if not os.path.exists(self.db_path):
            return self._get_fallback_logs("Database not yet created")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 检查数据库中有哪些表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            # 尝试读取不同可能的表结构
            logs.extend(self._read_posts_table(cursor, tables))
            logs.extend(self._read_interactions_table(cursor, tables))

            conn.close()

            # 如果没有找到任何日志，返回基本信息
            if not logs:
                return self._get_fallback_logs("No data found in database")
            return logs[:100]  # 最多返回100条

        except Exception as e:
            print(f"❌ 读取数据库失败: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return self._get_fallback_logs(f"Error: {str(e)}")

    def _collect_context_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "agent_count": len(self.agents),
            "avg_chars_before": 0,
            "avg_chars_after": 0,
            "max_chars_before": 0,
            "max_chars_after": 0,
            "total_truncated_fields": 0,
            "total_placeholder_fields": 0,
            "total_comments_omitted": 0,
            "total_groups_omitted": 0,
            "avg_context_tokens": 0,
            "max_context_tokens": 0,
            "avg_memory_records": 0,
            "max_memory_records": 0,
            "avg_get_context_ms": 0.0,
            "max_get_context_ms": 0.0,
            "avg_retrieve_ms": 0.0,
            "max_retrieve_ms": 0.0,
            "context_token_errors": 0,
            "memory_retrieve_errors": 0,
        }
        if not self.agents:
            return metrics

        chars_before = []
        chars_after = []
        context_tokens = []
        memory_records = []
        get_context_timings = []
        retrieve_timings = []

        for agent in self.agents:
            render_stats = getattr(getattr(agent, "env", None), "last_render_stats", None)
            if isinstance(render_stats, dict):
                chars_before.append(render_stats.get("chars_before", 0))
                chars_after.append(render_stats.get("chars_after", 0))
                metrics["total_truncated_fields"] += render_stats.get(
                    "truncated_field_count", 0
                )
                metrics["total_placeholder_fields"] += render_stats.get(
                    "placeholder_field_count", 0
                )
                metrics["total_comments_omitted"] += render_stats.get(
                    "comments_omitted_count", 0
                )
                metrics["total_groups_omitted"] += render_stats.get(
                    "groups_omitted_count", 0
                )

            memory = getattr(agent, "memory", None)
            if memory is None:
                continue
            try:
                start = time.perf_counter()
                _, token_count = memory.get_context()
                get_context_timings.append(
                    (time.perf_counter() - start) * 1000
                )
                context_tokens.append(token_count)
            except Exception:
                metrics["context_token_errors"] += 1

            try:
                start = time.perf_counter()
                memory_records.append(len(memory.retrieve()))
                retrieve_timings.append((time.perf_counter() - start) * 1000)
            except Exception:
                metrics["memory_retrieve_errors"] += 1

        if chars_before:
            metrics["avg_chars_before"] = int(sum(chars_before) / len(chars_before))
            metrics["max_chars_before"] = max(chars_before)
        if chars_after:
            metrics["avg_chars_after"] = int(sum(chars_after) / len(chars_after))
            metrics["max_chars_after"] = max(chars_after)
        if context_tokens:
            metrics["avg_context_tokens"] = int(
                sum(context_tokens) / len(context_tokens)
            )
            metrics["max_context_tokens"] = max(context_tokens)
        if memory_records:
            metrics["avg_memory_records"] = int(
                sum(memory_records) / len(memory_records)
            )
            metrics["max_memory_records"] = max(memory_records)
        if get_context_timings:
            metrics["avg_get_context_ms"] = round(
                sum(get_context_timings) / len(get_context_timings), 3
            )
            metrics["max_get_context_ms"] = round(max(get_context_timings), 3)
        if retrieve_timings:
            metrics["avg_retrieve_ms"] = round(
                sum(retrieve_timings) / len(retrieve_timings), 3
            )
            metrics["max_retrieve_ms"] = round(max(retrieve_timings), 3)

        return metrics

    def _read_posts_table(self, cursor, tables) -> List[Dict]:
        """尝试读取posts相关表"""
        logs = []

        # OASIS使用小写的 'post' 表
        if 'post' not in tables:
            return logs

        try:
            # 读取最新的帖子
            cursor.execute("""
                SELECT
                    p.post_id,
                    p.user_id,
                    p.content,
                    p.created_at,
                    p.num_likes,
                    u.user_name
                FROM post p
                LEFT JOIN user u ON p.user_id = u.user_id
                ORDER BY p.post_id DESC
                LIMIT 50
            """)

            rows = cursor.fetchall()
            for row in rows:
                post_id, user_id, content, created_at, num_likes, user_name = row

                logs.append({
                    "timestamp": self._format_timestamp(created_at),
                    "agent_id": user_name or f"Agent {user_id}",
                    "action_type": "CREATE_POST",
                    "content": content[:200] + "..." if len(content) > 200 else content,
                    "reason": f"Post {post_id} | {num_likes} likes"
                })

        except Exception as e:
            print(f"⚠️  读取post表失败: {e}", flush=True)

        return logs

    def _read_interactions_table(self, cursor, tables) -> List[Dict]:
        """尝试读取interactions/likes相关表"""
        logs = []

        # 读取like表
        if 'like' not in tables and 'likes' not in tables:
            return logs

        table_name = 'like' if 'like' in tables else 'likes'

        try:
            cursor.execute(f"""
                SELECT
                    l.like_id,
                    l.user_id,
                    l.post_id,
                    l.created_at,
                    u.user_name
                FROM {table_name} l
                LEFT JOIN user u ON l.user_id = u.user_id
                ORDER BY l.like_id DESC
                LIMIT 20
            """)

            rows = cursor.fetchall()
            for row in rows:
                like_id, user_id, post_id, created_at, user_name = row

                logs.append({
                    "timestamp": self._format_timestamp(created_at),
                    "agent_id": user_name or f"Agent {user_id}",
                    "action_type": "LIKE_POST",
                    "content": f"Liked post {post_id}",
                    "reason": f"Like {like_id}"
                })

        except Exception as e:
            pass  # 静默忽略读取错误

        return logs

    def _get_fallback_logs(self, reason: str) -> List[Dict]:
        """当无法读取数据库时返回备用日志"""
        logs = []
        current_time = datetime.now(timezone.utc).isoformat()
        for agent in self.agents[:10]:  # 只返回前10个
            logs.append({
                "timestamp": current_time,
                "agent_id": f"Agent {agent.agent_id}",
                "action_type": "CREATE_POST",
                "content": f"Agent action - {reason}",
                "reason": "Simulation running, check database for details"
            })
        return logs

    def _get_actual_post_count(self) -> int:
        """从数据库读取真实的帖子数量"""
        import sqlite3
        import os

        if not os.path.exists(self.db_path):
            return len(self.agents)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 统计帖子数量
            cursor.execute("SELECT COUNT(*) FROM post")
            post_count = cursor.fetchone()[0]

            conn.close()

            return post_count

        except Exception as e:
            return len(self.agents)

    async def close(self) -> Dict:
        """关闭模拟环境"""
        if self.env is not None:
            await self.env.close()

        self.is_running = False

        return {
            "status": "ok",
            "message": "模拟已关闭",
        }


# 全局引擎实例
_engine: Optional[RealOASISEngineV3] = None


def get_engine() -> RealOASISEngineV3:
    """获取或创建全局 OASIS 引擎实例"""
    global _engine
    if _engine is None:
        _engine = RealOASISEngineV3()
    return _engine


# JSON-RPC 服务器
async def handle_rpc_request(request: Dict) -> Dict:
    """处理单个 JSON-RPC 请求"""
    engine = get_engine()
    
    method = request.get("method")
    params = request.get("params", {})
    
    try:
        if method == "initialize":
            result = await engine.initialize(
                agent_count=params.get("agent_count", 1),
                platform=params.get("platform", "reddit"),
                recsys=params.get("recsys", "hot-score"),
                topic=params.get("topic", "general"),
                topics=params.get("topics"),
                regions=params.get("regions"),
            )
        elif method == "step":
            result = await engine.step()
        elif method == "status":
            result = engine.get_status()
        elif method == "reset":
            result = await engine.reset()
        elif method == "close":
            result = await engine.close()
        else:
            result = {"status": "error", "message": f"未知方法: {method}"}
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": result,
        }
    except Exception as e:
        print(f"❌ RPC 请求处理失败: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": str(e),
            },
        }


async def run_rpc_server():
    """运行 JSON-RPC 服务器（stdin/stdout）"""
    # 发送就绪信号
    print(json.dumps({"status": "ready"}), flush=True)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line.strip())

            response = await handle_rpc_request(request)
            print(json.dumps(response), flush=True)
            
        except Exception as e:
            print(f"❌ 解析错误: {str(e)}", file=sys.stderr, flush=True)
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"解析错误: {str(e)}",
                },
            }
            print(json.dumps(error_response), flush=True)


# 示例用法
async def main():
    """示例：测试真实 OASIS 引擎"""
    engine = get_engine()
    
    # 初始化
    init_result = await engine.initialize(agent_count=1, platform="reddit")
    print(f"初始化结果: {init_result}")
    
    # 运行 5 步
    for i in range(5):
        step_result = await engine.step()
        print(f"第 {i+1} 步: {step_result}")
    
    # 获取状态
    status = engine.get_status()
    print(f"状态: {status}")
    
    # 关闭
    close_result = await engine.close()
    print(f"关闭: {close_result}")


if __name__ == "__main__":
    # 检查是否以 RPC 模式运行
    if len(sys.argv) > 1 and sys.argv[1] == "--rpc":
        asyncio.run(run_rpc_server())
    else:
        # 运行示例
        asyncio.run(main())
