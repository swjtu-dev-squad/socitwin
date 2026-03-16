#!/usr/bin/env python3
"""
Real OASIS Engine V3 - Speed Optimized
真实 OASIS 引擎 V3 - 速度优化版

优化 Qwen3-8B 调用速度，确保 step 在 30 秒内完成
"""

import os
import random
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
from camel.types import OpenAIBackendRole

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

# 🔧 Monkey-patch CAMEL to handle multiple messages from DeepSeek API
# DeepSeek API returns multiple candidate responses during tool calling,
# but CAMEL's _record_final_output only handles single response.
import camel.agents.chat_agent as chat_agent_module
original_record_final_output = chat_agent_module.ChatAgent._record_final_output

def patched_record_final_output(self, output_messages):
    """Patched version that handles the first message when multiple are returned"""
    if len(output_messages) == 0:
        return
    elif len(output_messages) == 1:
        self.record_message(output_messages[0])
    else:
        # 🔧 FIX: When multiple messages returned, record the FIRST one
        # This allows tool calls to execute properly
        self.record_message(output_messages[0])
        print(f"⚡ Patched: Recording first of {len(output_messages)} messages (tool calling enabled)", flush=True)

chat_agent_module.ChatAgent._record_final_output = patched_record_final_output


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
        model_platform: Optional[str] = None,
        model_type: Optional[str] = None,
        db_path: str = "./oasis_simulation.db",
    ):
        """初始化真实 OASIS 引擎"""
        self.model_platform = model_platform or os.environ.get(
            "OASIS_MODEL_PLATFORM", "ollama"
        )
        self.model_type = model_type or os.environ.get(
            "OASIS_MODEL_TYPE", "qwen3:8b"
        )
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

        # 初始化阶段状态跟踪 (Phase 2.1)
        # 🔧 禁用渐进式激活，让所有 agents 从第一步就全部参与
        self.initialization_phase = False
        self.initial_seeded_agents = set()
        self.activation_step = 0

        # 极化率分析器（延迟初始化）
        self.polarization_analyzer: Optional[Any] = None
        self.polarization_topic: Optional[str] = None
        self.last_polarization: float = 0.0

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

        # 温度配置
        # 优先级：环境变量 > 平台默认值
        temperature_env = os.environ.get("OASIS_MODEL_TEMPERATURE")

        # 平台默认温度配置
        platform_default_temperatures = {
            "ollama": 0.4,
            "deepseek": 0.8,  # OASIS 推荐值
            "openai": 0.7,
            "openrouter": 0.7,
            "vllm": 0.7,
        }

        default_temperature = platform_default_temperatures.get(
            self.model_platform.lower(),
            0.7  # 通用默认值
        )

        # 初始化模型配置字典
        default_model_config: dict[str, Any] = {}

        # 设置温度
        if temperature_env:
            try:
                default_model_config["temperature"] = float(temperature_env)
                print(f"🌡️  使用环境变量温度: {temperature_env}")
            except ValueError:
                print(f"⚠️  温度值无效: {temperature_env}，使用默认值: {default_temperature}")
                default_model_config["temperature"] = default_temperature
        else:
            default_model_config["temperature"] = default_temperature
            print(f"🌡️  使用默认温度 ({self.model_platform}): {default_temperature}")

        # 🔧 显式启用tool calling（针对DeepSeek API）
        if self.model_platform.lower() == "deepseek":
            default_model_config["tool_choice"] = "auto"
            print(f"🔧 已启用 DeepSeek tool calling (tool_choice=auto) + Multi-message patch")

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
            env_window_size = os.environ.get("OASIS_CONTEXT_WINDOW_SIZE")
            self.memory_window_size = (
                int(env_window_size)
                if env_window_size
                else None
            )

            # 定义可用动作
            # 🔥 移除DO_NOTHING以防止agents选择什么都不做
            # 这样agents必须选择：创建帖子、点赞或刷新
            available_actions = [
                ActionType.CREATE_POST,
                ActionType.LIKE_POST,
                ActionType.REFRESH,
            ]

            # 🔥 多样化属性集合（增加agent多样性）
            age_range = [18, 22, 25, 28, 32, 35, 40, 45, 50, 55, 60, 65]
            genders = ["male", "female", "non-binary", "unknown"]
            mbti_types = [
                "INTJ", "INTP", "ENTJ", "ENTP",
                "INFJ", "INFP", "ENFJ", "ENFP",
                "ISTJ", "ISFJ", "ESTJ", "ESFJ",
                "ISTP", "ISFP", "ESTP", "ESFP"
            ]
            countries = ["Thailand", "Cambodia", "Indonesia", "Vietnam", "Malaysia", "Philippines", "Singapore", "Myanmar", "Laos", "Brunei"]

            # 针对不同话题的多样化profile
            topic_profiles = {
                "POLITICS": [
                    "Conservative political views, support traditional values and limited government",
                    "Liberal political views, support progressive policies and social justice",
                    "Moderate centrist, believe in balanced approaches and compromise",
                    "Libertarian views, support individual freedom and free markets",
                    "Green politics, focus on environmental protection and sustainability",
                    "Nationalist views, prioritize country's interests above all else",
                    "Socialist views, support wealth redistribution and social programs",
                ],
                "AI": [
                    "AI optimist, excited about technological progress and automation",
                    "AI skeptic, concerned about job displacement and ethical implications",
                    "AI researcher, focused on technical capabilities and limitations",
                    "AI ethicist, worried about bias, fairness, and alignment",
                    "Tech entrepreneur, sees AI as a business opportunity",
                    "AI artist, explores creative applications of AI tools",
                ],
                "ENTERTAINMENT": [
                    "Movie enthusiast, loves cinema and film analysis",
                    "Music lover, follows artists and attends concerts",
                    "Gaming fan, plays video games and follows esports",
                    "TV series binge-watcher, discusses plot twists and characters",
                    "Celebrity news follower, keeps up with entertainment industry",
                    "Pop culture critic, analyzes trends and media influence",
                ],
                "HEALTH": [
                    "Fitness enthusiast, works out regularly and follows diet trends",
                    "Mental health advocate, promotes therapy and mindfulness",
                    "Medical professional, shares evidence-based health information",
                    "Alternative medicine supporter, believes in holistic approaches",
                    "Nutrition focused, interested in supplements and healthy eating",
                    "Yoga and wellness practitioner, emphasizes mind-body connection",
                ],
                "TRAVEL": [
                    "Adventure traveler, seeks hiking, diving, and extreme sports",
                    "Cultural tourist, interested in history, art, and local traditions",
                    "Luxury traveler, prefers high-end resorts and fine dining",
                    "Budget backpacker, looks for affordable and authentic experiences",
                    "Digital nomad, combines work and travel while working remotely",
                    "Food tourist, travels primarily to try local cuisines",
                ],
                "FOOD": [
                    "Home cook, enjoys trying new recipes and cooking techniques",
                    "Restaurant reviewer, critiques dining experiences and ambiance",
                    "Food photographer, focuses on presentation and aesthetics",
                    "Health-conscious eater, follows specific diets (vegan, keto, etc.)",
                    "Street food lover, seeks authentic local food experiences",
                    "Baker and pastry enthusiast, loves desserts and baking",
                ],
            }

            # 初始化 agent graph
            self.agent_graph = AgentGraph()

            compression = compression_config_for_platform(platform)

            # 创建 agents
            for i in range(agent_count):
                # 为不同agent分配不同的topics（如果有多个）
                agent_topic = topics[i % len(topics)] if len(topics) > 1 else primary_topic
                agent_region = regions[i % len(regions)] if len(regions) > 1 else regions[0]

                # 🔥 随机选择多样化的属性（使用agent_id作为种子确保可重现）
                random.seed(i + 42)  # 使用固定种子确保每次运行结果一致
                agent_age = random.choice(age_range)
                agent_gender = random.choice(genders)
                agent_mbti = random.choice(mbti_types)
                agent_country = random.choice(countries)

                # 从话题对应的profile集合中随机选择一个，如果没有则使用默认的
                topic_profiles_list = topic_profiles.get(agent_topic, [f"Discuss {agent_topic.lower()} and related topics"])
                agent_user_profile = random.choice(topic_profiles_list)

                # 构建符合OASIS要求的profile结构
                # OASIS的to_system_message()使用profile['other_info']['user_profile']
                agent_profile = {
                    "other_info": {
                        "user_profile": agent_user_profile,  # 🔥 多样化的profile
                        "gender": agent_gender,
                        "age": agent_age,
                        "mbti": agent_mbti,
                        "country": agent_country,
                    }
                }

                user_info = UserInfo(
                    user_name=f"agent_{i}",
                    name=f"Agent {i}",
                    description=f"AI agent {i} - {agent_gender}, {agent_age}yo, {agent_mbti}, {agent_country}, {agent_topic}",
                    profile=agent_profile,  # 设置正确的profile
                    recsys_type=platform.lower(),  # ✅ 使用平台类型（reddit/twitter）而不是推荐算法
                )

                # 🔥 打印agent属性（用于调试和验证多样性）
                print(f"{agent_profile}", flush=True)
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

            # 初始化极化率分析器
            self.polarization_topic = primary_topic
            if primary_topic and primary_topic != "general":
                try:
                    from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

                    self.polarization_analyzer = PolarizationAnalyzer(
                        db_path=self.db_path,
                        model_spec=self._build_model_runtime_spec(),
                        topic=primary_topic,
                        sample_size=30,
                        cache_size=500
                    )

                    print(f"✅ 极化率分析器已初始化，topic: {primary_topic}", flush=True)

                except Exception as e:
                    print(f"⚠️  极化率分析器初始化失败: {e}", flush=True)
                    self.polarization_analyzer = None

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

    async def _seed_initial_content(self) -> Dict:
        """Step 1: 创建初始内容 (ManualAction) - 按照OASIS官方文档"""
        try:
            print("🌱 Seeding initial content...", flush=True)

            all_agents = list(self.env.agent_graph.get_agents())
            seed_agents = all_agents[:5]  # 前5个agent

            # 多样化的种子内容
            seed_contents = [
                f"Welcome to our {self.polarization_topic or 'general'} discussion! What are your thoughts?",
                f"I'm excited to discuss {self.polarization_topic or 'this topic'}!",
                f"Let's have a productive conversation about {self.polarization_topic or 'this'}.",
                "What does everyone think about the current situation?",
                f"I've been thinking about {self.polarization_topic or 'this topic'} a lot lately.",
            ]

            actions = {}
            for idx, (agent_id, agent) in enumerate(seed_agents):
                actions[agent] = ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": seed_contents[idx % len(seed_contents)]}
                )
                self.initial_seeded_agents.add(agent_id)

            await self.env.step(actions)
            self.total_posts = self._get_actual_post_count()

            # 🔄 刷新推荐系统，让agents可以看到新创建的帖子
            print("🔄 Refreshing recommendation system...", flush=True)
            await self.env.platform.update_rec_table()

            print(f"✅ Seeded {len(actions)} initial posts", flush=True)
            print("✅ Step complete", file=sys.stderr, flush=True)  # 触发前端 WebSocket 事件

            return {
                "status": "ok",
                "seeded_posts": len(actions),
                "total_posts": self.total_posts,
            }
        except Exception as e:
            print(f"❌ Failed to seed initial content: {e}", flush=True)
            return {"status": "error", "message": str(e)}

    async def _activate_agents_gradually(self) -> Dict:
        """Step 2: 逐步激活agents (LLMAction) - 按照OASIS官方文档"""
        try:
            all_agents = list(self.env.agent_graph.get_agents())
            total_agents = len(all_agents)

            # 计算当前阶段应该激活多少agents
            if self.activation_step == 0:
                target_count = max(5, int(total_agents * 0.2))  # 20%
            elif self.activation_step == 1:
                target_count = int(total_agents * 0.5)  # 50%
            else:
                target_count = total_agents  # 100%

            available_agents = [
                (aid, agent) for aid, agent in all_agents
                if aid not in self.initial_seeded_agents
            ]

            agents_to_activate = available_agents[:target_count]

            print(f"⚡ Activating {len(agents_to_activate)}/{total_agents} agents (phase {self.activation_step + 1})", flush=True)

            actions = {
                agent: LLMAction()
                for _, agent in agents_to_activate
            }

            # 🐛 调试：打印推荐表状态
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rec")
            rec_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM post")
            post_count = cursor.fetchone()[0]
            conn.close()
            print(f"📊 推荐: {rec_count} 条, 帖子: {post_count} 条", flush=True)

            # 🐛 调试：打印第一个激活agent的memory内容
            if agents_to_activate:
                first_agent_id, first_agent = agents_to_activate[0]
                if hasattr(first_agent, 'memory'):
                    memory = first_agent.memory
                    if hasattr(memory, 'get_context'):
                        context, tokens = memory.get_context()
                        print(f"🧠 Agent {first_agent_id} memory: {len(context)} 条消息, {tokens} tokens", flush=True)
                        # 打印最后3条消息
                        for msg in context[-3:]:
                            if isinstance(msg, dict):
                                role = msg.get('role', 'unknown')
                                content = str(msg.get('content', ''))[:200]
                                print(f"  [{role}]: {content}...", flush=True)

            await self.env.step(actions)

            # 🐛 调试：立即检查agents实际执行的操作
            conn_check = sqlite3.connect(self.db_path)
            cursor_check = conn_check.cursor()
            # 查看最新执行的操作（排除refresh和sign_up）
            cursor_check.execute(
                "SELECT user_id, action FROM trace "
                "WHERE action NOT IN ('refresh', 'sign_up') "
                "ORDER BY created_at DESC LIMIT 10"
            )
            recent_actions = cursor_check.fetchall()
            if recent_actions:
                print(f"🎯 Agents执行了 {len(recent_actions)} 个非refresh操作:", flush=True)
                for user_id, action in recent_actions[:5]:  # 只打印前5个
                    print(f"  Agent {user_id}: {action}", flush=True)
            else:
                print(f"⚠️  Agents没有执行任何social actions！", flush=True)
            conn_check.close()

            # 🔄 刷新推荐系统，让agents可以看到新内容
            print("🔄 Refreshing recommendation system...", flush=True)
            await self.env.platform.update_rec_table()

            print("✅ Step complete", file=sys.stderr, flush=True)  # 触发前端 WebSocket 事件

            if len(agents_to_activate) < total_agents:
                self.activation_step += 1
            else:
                self.initialization_phase = False
                print("✅ All agents activated", flush=True)

            return {
                "status": "ok",
                "activated_agents": len(agents_to_activate),
                "phase": self.activation_step,
                "initialization_complete": not self.initialization_phase,
            }
        except Exception as e:
            print(f"❌ Failed to activate agents: {e}", flush=True)
            return {"status": "error", "message": str(e)}

    async def step(self) -> Dict:
        """执行一步真实 OASIS 模拟（速度优化版）"""
        if not self.is_running or self.env is None:
            return {
                "status": "error",
                "message": "模拟未初始化或未运行",
            }

        try:
            step_start = time.time()

            # 🔧 直接运行所有 agents（禁用渐进式激活）
            print(f"⚙️  Step {self.current_step + 1} 开始", flush=True)

            # 按照OASIS官方文档：从环境中获取agents
            all_agents = list(self.env.agent_graph.get_agents())

            # 输出进度信息（用于前端显示）
            total_agents = len(all_agents)
            print(f"📊 Progress: 0/{total_agents} (0%)", file=sys.stderr, flush=True)

            # 🚀 并发执行每个agent，真正并行调用LLM API
            # 默认并发8，可通过 OASIS_STEP_CONCURRENCY 调整
            configured_concurrency = int(
                os.environ.get("OASIS_STEP_CONCURRENCY", "8")
            )
            step_concurrency = max(1, min(configured_concurrency, total_agents))
            print(
                f"🚀 Step concurrency: {step_concurrency}/{total_agents}",
                flush=True,
            )

            completed = 0
            agent_observations = []
            semaphore = asyncio.Semaphore(step_concurrency)

            async def _run_single_agent(agent):
                async with semaphore:
                    actions = {agent: LLMAction()}
                    await self.env.step(actions)
                    return self._collect_agent_observation(agent, actions[agent])

            tasks = [
                asyncio.create_task(_run_single_agent(agent))
                for _, agent in all_agents
            ]

            try:
                for finished_task in asyncio.as_completed(tasks):
                    obs_data = await finished_task
                    completed += 1
                    percentage = int((completed / total_agents) * 100)
                    print(
                        f"📊 Progress: {completed}/{total_agents} ({percentage}%)",
                        file=sys.stderr,
                        flush=True,
                    )
                    if obs_data:
                        agent_observations.append(obs_data)
            except Exception:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise

            # 🔄 所有agent完成后统一刷新推荐系统
            await self.env.platform.update_rec_table()

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

            # 计算极化率（每一步都检查）
            polarization_result = await self._update_polarization()

            # 新增：计算 Console 数据摘要统计
            total_interactions = sum(
                1 for obs in agent_observations
                if obs['action']['type'] in ['LIKE_POST', 'CREATE_COMMENT', 'FOLLOW']
            )
            posts_created = sum(
                1 for obs in agent_observations
                if obs['action']['type'] == 'CREATE_POST'
            )
            avg_context_tokens = (
                sum(obs['observations']['contextTokens'] for obs in agent_observations) / len(agent_observations)
                if agent_observations else 0
            )

            return {
                "status": "ok",
                "current_step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
                "step_time": step_time,
                "context_metrics": context_metrics,
                "new_logs": new_logs,  # ← 返回所有日志
                "polarization": polarization_result.get("polarization", 0.0),  # ← 极化率
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

        # 🆕 重置初始化状态 (Phase 3)
        # 🔧 禁用渐进式激活，让所有 agents 从第一步就全部参与
        self.initialization_phase = False
        self.initial_seeded_agents = set()
        self.activation_step = 0

        print("🔄 模拟已重置", flush=True)

        return {
            "status": "ok",
            "message": "模拟已重置",
        }

    async def _update_polarization(self) -> Dict:
        """
        更新极化率（每一步都调用）

        Returns:
            极化率指标字典
        """
        # 如果没有初始化分析器，返回0
        if not hasattr(self, 'polarization_analyzer') or self.polarization_analyzer is None:
            return {"polarization": 0.0}

        try:
            # 执行分析
            result = await self.polarization_analyzer.analyze()

            # 更新缓存
            self.last_polarization = result.get("polarization", 0.0)

            # 记录到历史（用于降级）
            if "polarization" in result:
                self.polarization_analyzer.history.append(result["polarization"])
                # 保留最近100次
                if len(self.polarization_analyzer.history) > 100:
                    self.polarization_analyzer.history.pop(0)

            return result

        except Exception as e:
            print(f"⚠️  极化率分析失败: {e}，使用历史平均值", flush=True)

            # 降级：返回历史平均值
            if hasattr(self.polarization_analyzer, 'history') and len(self.polarization_analyzer.history) > 0:
                avg_pol = sum(self.polarization_analyzer.history) / len(self.polarization_analyzer.history)
                return {"polarization": avg_pol, "degraded": True}

            return {"polarization": 0.0, "error": str(e)}

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

    def _collect_agent_observation(self, agent, action) -> Optional[Dict]:
        """收集单个 agent 的观察信息"""
        try:
            # 获取 agent 对象
            agent_obj = agent if hasattr(agent, 'user_info') else None
            if not agent_obj:
                return None

            # 获取 agent ID 和名称
            agent_id = getattr(agent_obj, 'agent_id', 'unknown')
            user_info = getattr(agent_obj, 'user_info', None)
            agent_name = user_info.user_name if user_info else f"Agent {agent_id}"

            # 收集观察数据
            seen_posts = self._get_agent_seen_posts(agent_obj)
            context_info = self._get_agent_context_info(agent_obj)

            # 获取动作信息
            action_type = "UNKNOWN"
            action_content = ""
            action_reason = ""

            # 从 trace 表获取实际动作
            action_data = self._get_agent_last_action(agent_id)
            if action_data:
                action_type = action_data.get('action_type', 'UNKNOWN')
                action_content = action_data.get('content', '')
                action_reason = action_data.get('reason', '')

            return {
                'agentId': f"agent_{agent_id}",
                'agentName': agent_name,
                'step': self.current_step,
                'observations': {
                    'seenPosts': seen_posts,
                    'seenAgentsCount': context_info.get('seen_agents_count', 0),
                    'retrievedMemories': context_info.get('memory_records', 0),
                    'contextTokens': context_info.get('context_tokens', 0),
                    'contextLength': context_info.get('context_length', 0),
                },
                'action': {
                    'type': action_type,
                    'content': action_content,
                    'reason': action_reason,
                },
                'timestamp': datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Warning: Failed to collect observation for agent: {e}", flush=True)
            return None

    def _get_agent_seen_posts(self, agent) -> List[Dict]:
        """获取 agent 在当前步骤看到的帖子"""
        posts = []

        try:
            # 方法1：从 agent 的 context 中提取
            if hasattr(agent, 'memory'):
                memory = agent.memory
                if hasattr(memory, 'get_context'):
                    context, _ = memory.get_context()
                    posts = self._parse_posts_from_context(context)

            # 方法2：从环境日志中获取
            if not posts and hasattr(agent, 'env'):
                env = agent.env
                if hasattr(env, 'last_render_stats'):
                    stats = env.last_render_stats
                    posts = self._parse_posts_from_render_stats(stats)

            return posts[:10]  # 限制返回数量
        except Exception as e:
            print(f"Warning: Failed to get seen posts: {e}", flush=True)
            return []

    def _parse_posts_from_context(self, context: List) -> List[Dict]:
        """从 context (List[OpenAIMessage]) 中解析帖子信息"""
        posts = []

        try:
            import json

            for message in context:
                if isinstance(message, dict):
                    content = message.get('content', '')

                    # 尝试解析 JSON 格式的帖子数据
                    if 'post_id' in content or 'content' in content:
                        try:
                            data = json.loads(content) if isinstance(content, str) else content

                            if isinstance(data, dict) and 'content' in data:
                                posts.append({
                                    'postId': str(data.get('post_id', 'unknown')),
                                    'content': data.get('content', '')[:500],
                                    'author': data.get('author_name', 'Unknown'),
                                    'authorId': str(data.get('user_id', 'unknown')),
                                    'timestamp': data.get('created_at', datetime.now().isoformat()),
                                    'numLikes': data.get('num_likes', 0),
                                })
                        except:
                            pass

            return posts[:10]
        except Exception as e:
            print(f"Warning: Failed to parse posts from context: {e}", flush=True)
            return []

    def _parse_posts_from_render_stats(self, stats: Dict) -> List[Dict]:
        """从 render stats 中解析帖子信息"""
        posts = []

        try:
            if 'observed_posts' in stats:
                for post in stats['observed_posts'][:10]:
                    posts.append({
                        'postId': str(post.get('id', 'unknown')),
                        'content': post.get('content', '')[:500],
                        'author': post.get('author', 'Unknown'),
                        'authorId': str(post.get('author_id', 'unknown')),
                        'timestamp': post.get('timestamp', datetime.now().isoformat()),
                        'numLikes': post.get('num_likes', 0),
                    })
        except Exception as e:
            print(f"Warning: Failed to parse posts from render stats: {e}", flush=True)

        return posts

    def _get_agent_context_info(self, agent) -> Dict:
        """获取 agent 的上下文信息"""
        info = {
            'seen_agents_count': 0,
            'memory_records': 0,
            'context_tokens': 0,
            'context_length': 0,
        }

        try:
            # 获取上下文长度
            if hasattr(agent, 'memory'):
                memory = agent.memory
                if hasattr(memory, 'get_context'):
                    context, token_count = memory.get_context()
                    # context 是 List[OpenAIMessage], token_count 是实际的 token 数量
                    info['context_length'] = sum(len(str(msg.get('content', ''))) for msg in context)
                    info['context_tokens'] = token_count if isinstance(token_count, int) else len(context) * 100  # 使用 OASIS 返回的实际 token 数
                    info['memory_records'] = len(context)  # context 本身就是 memory records

            # 获取看到的 agent 数量
            info['seen_agents_count'] = min(len(self.agents), 50)

        except Exception as e:
            print(f"Warning: Failed to get context info: {e}", flush=True)

        return info

    def _get_agent_last_action(self, agent_id: int) -> Optional[Dict]:
        """从数据库中获取 agent 的最后动作"""
        try:
            import sqlite3
            import os

            if not os.path.exists(self.db_path):
                return None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 从 trace 表查询最近的动作
            cursor.execute(
                """
                SELECT action, info, created_at
                FROM trace
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (agent_id,)
            )

            row = cursor.fetchone()
            conn.close()

            if row:
                action, info, created_at = row
                # 映射动作类型
                action_map = {
                    'create_post': 'CREATE_POST',
                    'like': 'LIKE_POST',
                    'follow': 'FOLLOW',
                    'refresh': 'REFRESH',
                }
                mapped_type = action_map.get(action.lower(), action.upper())

                return {
                    'action_type': mapped_type,
                    'content': info or f'Executed {action}',
                    'reason': f'Agent decided to {action}',
                }

            return None
        except Exception as e:
            print(f"Warning: Failed to get last action: {e}", flush=True)
            return None

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
            "total_system_records": 0,
            "total_user_records": 0,
            "total_assistant_records": 0,
            "total_function_records": 0,
            "total_tool_records": 0,
            "total_assistant_function_call_records": 0,
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
                retrieved_records = memory.retrieve()
                retrieve_timings.append((time.perf_counter() - start) * 1000)
                memory_records.append(len(retrieved_records))
                self._accumulate_memory_record_metrics(
                    metrics,
                    retrieved_records,
                )
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

    @staticmethod
    def _accumulate_memory_record_metrics(
        metrics: Dict[str, Any],
        retrieved_records: List[Any],
    ) -> None:
        for record in retrieved_records:
            memory_record = getattr(record, "memory_record", None)
            if memory_record is None:
                continue

            role = getattr(memory_record, "role_at_backend", None)
            message = getattr(memory_record, "message", None)
            message_class = (
                message.__class__.__name__
                if message is not None
                else None
            )

            if role == OpenAIBackendRole.SYSTEM:
                metrics["total_system_records"] += 1
            elif role == OpenAIBackendRole.USER:
                metrics["total_user_records"] += 1
            elif role == OpenAIBackendRole.ASSISTANT:
                metrics["total_assistant_records"] += 1
                if message_class == "FunctionCallingMessage":
                    metrics["total_assistant_function_call_records"] += 1
            elif role == OpenAIBackendRole.FUNCTION:
                metrics["total_function_records"] += 1
            elif role == OpenAIBackendRole.TOOL:
                metrics["total_tool_records"] += 1

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
