"""
OASIS 环境管理器

负责封装 OASIS 框架的复杂性，管理环境生命周期。
这是整个系统的核心组件，确保与 OASIS 框架的交互是安全和可控的。
"""

import asyncio
import csv
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# OASIS 框架导入
import oasis
from camel.configs import ChatGPTConfig

# CAMEL 框架导入
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from oasis import (
    ActionType,
    AgentGraph,
    DefaultPlatformType,
    LLMAction,
    ManualAction,
    SocialAgent,
    UserInfo,
    generate_reddit_agent_graph,
    generate_twitter_agent_graph,
)

# 本地导入
from app.core.config import get_settings
from app.memory import (
    ActionV1RuntimeSettings,
    LongtermSidecarConfig,
    MemoryMode,
    MemoryRuntimeFacade,
    MemoryRuntimeNotImplementedError,
    ObservationPresetConfig,
    ProviderRuntimePresetConfig,
    RecallPresetConfig,
    SummaryPresetConfig,
    WorkingMemoryBudgetConfig,
    apply_observation_env_overrides,
    apply_provider_runtime_env_overrides,
    apply_recall_env_overrides,
    apply_summary_env_overrides,
    apply_working_memory_env_overrides,
    build_chroma_longterm_store,
    probe_openai_compatible_embedding_backend,
    resolve_memory_runtime_config,
)
from app.memory.agent import build_action_v1_social_agent, build_upstream_social_agent
from app.memory.longterm import LongtermStore
from app.memory.tokens import HeuristicUnicodeTokenCounter
from app.models.simulation import (
    ModelConfig,
    PlatformType,
    SimulationConfig,
    SimulationState,
)

logger = logging.getLogger(__name__)


class OASISException(Exception):  # noqa: N818
    """OASIS 操作异常基类"""
    pass


class OASISInitError(OASISException):
    """OASIS 初始化错误"""
    pass


class OASISOperationError(OASISException):
    """OASIS 操作错误"""
    pass


class OASISStateError(OASISException):
    """OASIS 状态错误"""
    pass


class OASISManager:
    """
    OASIS 环境管理器 - 单例模式

    职责：
    - 封装 OASIS 环境的生命周期管理
    - 提供线程安全的异步操作接口
    - 处理错误重试和资源清理
    - 隔离 OASIS 框架细节
    """

    _instance: Optional['OASISManager'] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # OASIS 环境状态
        self._env: Optional[oasis.Platform] = None
        self._agent_graph: Optional[AgentGraph] = None
        self._model: Any = None
        self._db_path: Optional[str] = None
        self._action_v1_longterm_store: Optional[LongtermStore] = None

        # 模拟状态
        self._state: SimulationState = SimulationState.UNINITIALIZED
        self._current_step: int = 0
        self._max_steps: int = 100
        self._created_at: Optional[datetime] = None
        self._updated_at: Optional[datetime] = None

        # 配置
        self._config: Optional[SimulationConfig] = None
        self._platform_type: PlatformType = PlatformType.TWITTER
        self._memory_mode: MemoryMode = MemoryMode.UPSTREAM
        self._error_message: Optional[str] = None

        # 并发控制
        self._operation_lock = asyncio.Lock()
        self._background_tasks = set()

        # 标记为已初始化
        self._initialized = True

        logger.info("OASIS Manager initialized")

    @property
    def state(self) -> SimulationState:
        """获取当前状态"""
        return self._state

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._state != SimulationState.UNINITIALIZED

    @property
    def is_ready(self) -> bool:
        """检查是否准备好执行步骤"""
        return self._state in [SimulationState.READY, SimulationState.RUNNING]

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._state == SimulationState.RUNNING

    def _clear_runtime_state(self, *, clear_error_message: bool = True) -> None:
        self._env = None
        self._agent_graph = None
        self._model = None
        self._action_v1_longterm_store = None
        self._state = SimulationState.UNINITIALIZED
        self._memory_mode = MemoryMode.UPSTREAM
        self._config = None
        self._db_path = None
        self._created_at = None
        if clear_error_message:
            self._error_message = None

    def get_state_info(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        agent_count = 0
        if self._agent_graph:
            agent_count = self._agent_graph.get_num_nodes()
        context_token_limit = self._resolve_context_token_limit()
        generation_max_tokens = self._resolve_generation_max_tokens()
        model_backend_token_limit = self._resolve_model_backend_token_limit()

        return {
            "state": self._state.value,
            "current_step": self._current_step,
            "max_steps": self._max_steps,
            "agent_count": agent_count,
            "platform": self._platform_type.value,
            "memory_mode": self._memory_mode.value,
            "created_at": self._created_at.isoformat() if self._created_at else None,
            "updated_at": self._updated_at.isoformat() if self._updated_at else None,
            "db_path": self._db_path,
            "context_token_limit": context_token_limit,
            "generation_max_tokens": generation_max_tokens,
            "model_backend_token_limit": model_backend_token_limit,
            "error_message": self._error_message,
        }

    def _resolve_context_token_limit(self) -> Optional[int]:
        if self._config is not None:
            try:
                explicit_limit = getattr(self._config, "context_token_limit", None)
                if explicit_limit:
                    return int(explicit_limit)
            except Exception:
                pass
        try:
            return int(get_settings().OASIS_CONTEXT_TOKEN_LIMIT)
        except Exception:
            return None

    def _resolve_generation_max_tokens(self) -> Optional[int]:
        if self._config is None:
            return None
        try:
            return int(getattr(self._config.llm_config, "max_tokens", 0) or 0)
        except Exception:
            return None

    def _resolve_model_backend_token_limit(self) -> Optional[int]:
        if self._model is None:
            return None
        try:
            return int(getattr(self._model, "token_limit", 0) or 0)
        except Exception:
            return None

    def get_memory_debug_info(self) -> Dict[str, Any]:
        """获取独立于 /status 的 memory 调试摘要。"""
        state_info = self.get_state_info()
        context_token_limit = None
        generation_max_tokens = None
        if self._config is not None:
            generation_max_tokens = int(getattr(self._config.llm_config, "max_tokens", 0) or 0)
        try:
            context_token_limit = int(get_settings().OASIS_CONTEXT_TOKEN_LIMIT)
        except Exception:
            context_token_limit = None

        agents: list[dict[str, Any]] = []
        for agent in self.get_all_agents():
            agents.append(self._build_agent_memory_debug_info(agent))

        return {
            "state": self._state.value,
            "memory_mode": self._memory_mode.value,
            "current_step": state_info["current_step"],
            "total_steps": state_info["max_steps"],
            "agent_count": state_info["agent_count"],
            "platform": state_info["platform"],
            "context_token_limit": context_token_limit,
            "generation_max_tokens": generation_max_tokens,
            "longterm_enabled": bool(
                self._memory_mode == MemoryMode.ACTION_V1
                and self._action_v1_longterm_store is not None
            ),
            "agents": agents,
        }

    def _build_agent_memory_debug_info(self, agent: SocialAgent) -> Dict[str, Any]:
        base = {
            "agent_id": int(getattr(agent, "social_agent_id", 0) or 0),
            "user_name": str(getattr(getattr(agent, "user_info", None), "user_name", "") or ""),
            "name": str(getattr(getattr(agent, "user_info", None), "name", "") or ""),
            "memory_runtime": self._memory_mode.value,
            "memory_supported": False,
            "recent_retained_step_count": 0,
            "recent_retained_step_ids": [],
            "compressed_action_block_count": 0,
            "compressed_heartbeat_count": 0,
            "compressed_retained_step_count": 0,
            "total_retained_step_count": 0,
            "last_observation_stage": "",
            "last_observation_prompt_tokens": 0,
            "last_prompt_tokens": 0,
            "last_recall_gate": None,
            "last_recall_gate_reason_flags": {},
            "last_recall_query_source": "",
            "last_recall_query_text": "",
            "last_recalled_count": 0,
            "last_injected_count": 0,
            "last_recalled_step_ids": [],
            "last_injected_step_ids": [],
            "last_recall_reason_trace": "",
            "last_recall_overlap_filtered_count": 0,
            "last_recall_overlap_filtered_step_ids": [],
            "last_recall_selection_stop_reason": "",
            "last_runtime_failure_category": "",
            "last_runtime_failure_stage": "",
            "last_prompt_budget_status": "",
            "last_selected_recent_step_ids": [],
            "last_selected_compressed_keys": [],
            "last_selected_recall_step_ids": [],
        }
        snapshot_fn = getattr(agent, "memory_debug_snapshot", None)
        if callable(snapshot_fn):
            snapshot = snapshot_fn() or {}
            if isinstance(snapshot, dict):
                base.update(snapshot)
        return base

    # ========================================================================
    # 初始化和配置
    # ========================================================================

    async def initialize(self, config: SimulationConfig) -> Dict[str, Any]:
        """
        初始化 OASIS 环境

        Args:
            config: 模拟配置

        Returns:
            初始化结果信息

        Raises:
            OASISInitError: 初始化失败
        """
        async with self._operation_lock:
            try:
                logger.info(f"Initializing OASIS with config: {config.platform.value}")

                # 清理现有环境（不获取锁，避免死锁）
                if self._env:
                    await self._env.close()
                    logger.info("OASIS environment closed")
                    self._env = None
                    self._agent_graph = None
                    self._model = None
                    self._action_v1_longterm_store = None
                    self._state = SimulationState.UNINITIALIZED

                # 保存配置
                self._config = config
                self._platform_type = config.platform
                self._max_steps = config.max_steps
                self._current_step = 0
                self._error_message = None
                settings = get_settings()
                runtime_config = resolve_memory_runtime_config(
                    explicit_mode=config.memory_mode,
                    settings_mode=settings.OASIS_MEMORY_MODE,
                )
                self._memory_mode = runtime_config.mode

                # 设置数据库路径
                if not config.db_path:
                    # 自动生成唯一数据库路径
                    data_dir = Path("./data/simulations")
                    data_dir.mkdir(parents=True, exist_ok=True)
                    sim_id = str(uuid.uuid4())[:8]
                    self._db_path = str(data_dir / f"simulation_{sim_id}.db")
                else:
                    self._db_path = config.db_path

                # 清理旧数据库
                if os.path.exists(self._db_path):
                    os.remove(self._db_path)

                await self._validate_runtime_dependencies(settings=settings)

                runtime = MemoryRuntimeFacade(runtime_config)
                artifacts = await runtime.build_runtime(
                    plan=self._build_runtime_plan(config)
                )
                self._model = artifacts.model
                self._agent_graph = artifacts.agent_graph
                self._env = artifacts.env

                # 重置环境
                await self._env.reset()

                # 更新状态
                self._state = SimulationState.READY
                self._created_at = datetime.now()
                self._updated_at = datetime.now()

                agent_count = self._agent_graph.get_num_nodes()

                logger.info(f"OASIS initialized successfully with {agent_count} agents")

                return {
                    "success": True,
                    "agent_count": agent_count,
                    "platform": config.platform.value,
                    "memory_mode": self._memory_mode.value,
                    "db_path": self._db_path,
                    "simulation_id": sim_id if 'sim_id' in locals() else None,
                }

            except MemoryRuntimeNotImplementedError as e:
                logger.error(f"Requested memory runtime is not implemented yet: {e}")
                if self._env:
                    try:
                        await self._env.close()
                    except Exception as close_exc:
                        logger.error(f"Failed to close environment after init error: {close_exc}")
                self._clear_runtime_state(clear_error_message=False)
                self._memory_mode = runtime_config.mode
                self._error_message = str(e)
                self._updated_at = datetime.now()
                raise OASISInitError(str(e))
            except Exception as e:
                logger.error(f"Failed to initialize OASIS: {e}")
                if self._env:
                    try:
                        await self._env.close()
                    except Exception as close_exc:
                        logger.error(f"Failed to close environment after init error: {close_exc}")
                self._clear_runtime_state(clear_error_message=False)
                self._memory_mode = runtime_config.mode
                self._error_message = str(e)
                self._updated_at = datetime.now()
                raise OASISInitError(f"Initialization failed: {str(e)}")

    async def _validate_runtime_dependencies(self, *, settings) -> None:
        if self._memory_mode != MemoryMode.ACTION_V1:
            return
        if not settings.OASIS_LONGTERM_ENABLED:
            return

        embedding_backend = str(
            settings.OASIS_LONGTERM_EMBEDDING_BACKEND or "heuristic"
        ).strip().lower()
        if embedding_backend not in {"openai", "openai_compatible", "openai-compatible"}:
            return

        embedding_model = str(settings.OASIS_LONGTERM_EMBEDDING_MODEL or "").strip()
        if not embedding_model:
            raise OASISInitError(
                "action_v1 requires OASIS_LONGTERM_EMBEDDING_MODEL when "
                "OASIS_LONGTERM_EMBEDDING_BACKEND=openai_compatible."
            )

        try:
            await asyncio.to_thread(
                probe_openai_compatible_embedding_backend,
                model=embedding_model,
                api_key=settings.OASIS_LONGTERM_EMBEDDING_API_KEY,
                base_url=settings.OASIS_LONGTERM_EMBEDDING_BASE_URL,
                timeout_seconds=5.0,
            )
        except Exception as exc:
            endpoint = settings.OASIS_LONGTERM_EMBEDDING_BASE_URL or "default endpoint"
            raise OASISInitError(
                "action_v1 embedding backend is unavailable. "
                f"backend={embedding_backend}, model={embedding_model}, endpoint={endpoint}. "
                "Start the local embedding service, switch the embedding backend to "
                "'heuristic', or use upstream mode."
            ) from exc

    def _build_runtime_plan(self, config: SimulationConfig):
        from app.memory.runtime import RuntimeBuildPlan

        return RuntimeBuildPlan(
            create_model=lambda: self._create_model(config.llm_config),
            build_agent_graph=lambda model: self._build_default_agent_graph(
                config,
                model,
            ),
            create_environment=lambda agent_graph: self._create_environment(
                agent_graph=agent_graph,
                config=config,
            ),
        )

    async def _create_model(self, config: ModelConfig):
        """创建 LLM 模型"""
        try:
            settings = get_settings()

            # 设置环境变量（CAMEL 框架从环境变量读取 API key）
            if config.model_platform.upper() == "DEEPSEEK" and settings.DEEPSEEK_API_KEY:
                os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY
                logger.info("DEEPSEEK_API_KEY set from settings")
            elif config.model_platform.upper() == "OPENAI" and settings.OPENAI_API_KEY:
                os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
                logger.info("OPENAI_API_KEY set from settings")

            model_platform = getattr(ModelPlatformType, config.model_platform.upper())
            model_type = getattr(ModelType, config.model_type.upper())

            model_config_dict = ChatGPTConfig(
                temperature=config.temperature,
                max_tokens=config.max_tokens
            ).as_dict()

            model = ModelFactory.create(
                model_platform=model_platform,
                model_type=model_type,
                model_config_dict=model_config_dict,
            )

            self._model = model
            logger.info(f"Model created: {config.model_platform}/{config.model_type}")
            return model

        except Exception as e:
            logger.error(f"Failed to create model: {e}")
            raise OASISInitError(f"Model creation failed: {str(e)}")

    async def _build_default_agent_graph(
        self,
        config: SimulationConfig,
        model: Any,
    ) -> AgentGraph:
        if config.agent_source.source_type == "file":
            return await self._load_agents_from_file(
                config.agent_source.file_path,
                config.platform,
                model,
            )
        if config.agent_source.source_type == "manual":
            return await self._generate_agents_from_manual(
                config.agent_count,
                config,
                model,
            )
        return await self._generate_agents_from_template(
            config.agent_count,
            config,
            model,
        )

    def _create_environment(
        self,
        *,
        agent_graph: AgentGraph,
        config: SimulationConfig,
    ):
        return oasis.make(
            agent_graph=agent_graph,
            platform=self._get_platform_type(config.platform),
            database_path=self._db_path,
            semaphore=32,  # 并发限制
        )

    def _get_platform_type(self, platform: PlatformType):
        """转换平台类型"""
        if platform == PlatformType.TWITTER:
            return DefaultPlatformType.TWITTER
        elif platform == PlatformType.REDDIT:
            return DefaultPlatformType.REDDIT
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    async def _load_agents_from_file(
        self,
        file_path: str,
        platform: PlatformType,
        model: Any,
    ) -> AgentGraph:
        """从文件加载智能体"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Agent file not found: {file_path}")

            available_actions = self._get_default_actions(platform)

            if self._memory_mode == MemoryMode.ACTION_V1:
                agent_graph = AgentGraph()
                file_agents = self._parse_file_agent_profiles(
                    file_path=file_path,
                    platform=platform,
                )
                for agent_record in file_agents:
                    user_info = UserInfo(
                        user_name=agent_record["user_name"],
                        name=agent_record["name"],
                        description=agent_record["description"],
                        profile=agent_record["profile"],
                        recsys_type=platform.value,
                    )
                    agent = self._build_social_agent(
                        agent_id=agent_record["agent_id"],
                        user_info=user_info,
                        agent_graph=agent_graph,
                        model=model,
                        available_actions=available_actions,
                    )
                    agent_graph.add_agent(agent)
                logger.info(
                    f"Loaded {agent_graph.get_num_nodes()} action_v1 agents from file"
                )
                return agent_graph

            if platform == PlatformType.TWITTER:
                agent_graph = await generate_twitter_agent_graph(
                    profile_path=file_path,
                    model=model,
                    available_actions=available_actions,
                )
            else:
                agent_graph = await generate_reddit_agent_graph(
                    profile_path=file_path,
                    model=model,
                    available_actions=available_actions,
                )

            logger.info(f"Loaded {agent_graph.get_num_nodes()} agents from file")
            return agent_graph

        except Exception as e:
            logger.error(f"Failed to load agents from file: {e}")
            raise OASISInitError(f"File loading failed: {str(e)}")

    def _parse_file_agent_profiles(
        self,
        *,
        file_path: str,
        platform: PlatformType,
    ) -> list[dict[str, Any]]:
        if platform == PlatformType.TWITTER:
            return self._parse_twitter_file_agent_profiles(file_path=file_path)
        return self._parse_reddit_file_agent_profiles(file_path=file_path)

    def _parse_twitter_file_agent_profiles(self, *, file_path: str) -> list[dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        if not rows:
            return []
        return [
            self._normalize_file_agent_record(
                row=row,
                index=index,
                platform=PlatformType.TWITTER,
            )
            for index, row in enumerate(rows)
        ]

    def _parse_reddit_file_agent_profiles(self, *, file_path: str) -> list[dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("Reddit file agent profiles must be a JSON list.")
        return [
            self._normalize_file_agent_record(
                row=item,
                index=index,
                platform=PlatformType.REDDIT,
            )
            for index, item in enumerate(payload)
            if isinstance(item, dict)
        ]

    def _normalize_file_agent_record(
        self,
        *,
        row: dict[str, Any],
        index: int,
        platform: PlatformType,
    ) -> dict[str, Any]:
        row = {str(key): value for key, value in row.items()}
        agent_id = self._coerce_int(row.get("agent_id"), index)
        user_name = self._coerce_text(
            row.get("user_name") or row.get("username"),
            default=f"agent_{agent_id}",
        )
        name = self._coerce_text(
            row.get("name") or row.get("realname") or row.get("username"),
            default=user_name,
        )
        description = self._coerce_text(
            row.get("description") or row.get("bio") or row.get("user_char"),
            default="",
        )

        existing_profile = row.get("profile")
        profile: dict[str, Any]
        if isinstance(existing_profile, dict):
            profile = dict(existing_profile)
        else:
            profile = {}
        other_info = profile.get("other_info")
        if not isinstance(other_info, dict):
            other_info = {}
            profile["other_info"] = other_info

        user_profile = (
            row.get("user_profile")
            or row.get("persona")
            or row.get("user_char")
            or other_info.get("user_profile")
            or description
        )
        if user_profile:
            other_info["user_profile"] = self._coerce_text(user_profile, default="")

        for field_name in ("gender", "mbti", "country"):
            if row.get(field_name) not in (None, ""):
                other_info[field_name] = self._coerce_text(row.get(field_name), default="")

        age_value = row.get("age")
        if age_value not in (None, ""):
            other_info["age"] = self._coerce_int(age_value, 0)

        interests = row.get("interests")
        if interests not in (None, "") and not profile.get("interests"):
            if isinstance(interests, str):
                profile["interests"] = [
                    item.strip() for item in interests.split(",") if item.strip()
                ]
            elif isinstance(interests, list):
                profile["interests"] = [
                    self._coerce_text(item, default="")
                    for item in interests
                    if self._coerce_text(item, default="")
                ]

        if platform == PlatformType.REDDIT and "bio" in row and not description:
            description = self._coerce_text(row.get("bio"), default="")

        return {
            "agent_id": agent_id,
            "user_name": user_name,
            "name": name,
            "description": description,
            "profile": profile,
        }

    @staticmethod
    def _coerce_text(value: Any, *, default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        if value in (None, ""):
            return default
        return int(value)

    async def _generate_agents_from_template(
        self,
        agent_count: int,
        config: SimulationConfig,
        model: Any,
    ) -> AgentGraph:
        """从模板生成智能体（使用智能体生成器）"""
        try:
            from app.core.agent_generator import get_agent_generator

            agent_graph = AgentGraph()
            available_actions = self._get_default_actions(config.platform)

            # 使用智能体生成器创建多样化配置
            generator = get_agent_generator()
            agent_profiles = generator.generate_batch(agent_count, config.platform.value)

            # 根据配置创建智能体
            for profile in agent_profiles:
                user_info = UserInfo(
                    user_name=profile.user_name,
                    name=profile.name,
                    description=profile.bio,
                    profile=profile.to_dict()["profile"],
                    recsys_type=config.platform.value,
                )

                agent = self._build_social_agent(
                    agent_id=profile.agent_id,
                    user_info=user_info,
                    agent_graph=agent_graph,
                    model=model,
                    available_actions=available_actions,
                )

                agent_graph.add_agent(agent)

            logger.info(f"Generated {agent_count} diverse agents using AgentGenerator")
            return agent_graph

        except Exception as e:
            logger.error(f"Failed to generate agents: {e}")
            raise OASISInitError(f"Agent generation failed: {str(e)}")

    async def _generate_agents_from_manual(
        self,
        agent_count: int,
        config: SimulationConfig,
        model: Any,
    ) -> AgentGraph:
        """从手动配置生成智能体"""
        try:
            from app.models.simulation import AgentConfig

            agent_graph = AgentGraph()
            available_actions = self._get_default_actions(config.platform)

            # 如果有手动配置，使用配置的智能体
            if config.agent_source.manual_config:
                logger.info(
                    "Creating %s agents from manual config",
                    len(config.agent_source.manual_config),
                )

                for agent_config_dict in config.agent_source.manual_config:
                    # 将字典转换为 AgentConfig
                    agent_config = AgentConfig(**agent_config_dict)

                    # 构建profile字典，包含interests
                    profile = agent_config.profile or {}
                    if agent_config.interests:
                        profile['interests'] = agent_config.interests

                    user_info = UserInfo(
                        user_name=agent_config.user_name,
                        name=agent_config.name,
                        description=agent_config.description,
                        profile=profile,
                        recsys_type=config.platform.value,
                    )

                    agent = self._build_social_agent(
                        agent_id=agent_config.agent_id,
                        user_info=user_info,
                        agent_graph=agent_graph,
                        model=model,
                        available_actions=available_actions,
                    )

                    agent_graph.add_agent(agent)

                logger.info(
                    "Created %s agents from manual config",
                    len(config.agent_source.manual_config),
                )
            else:
                # 如果没有手动配置，使用生成器填充剩余数量
                logger.info(
                    "No manual config provided, generating %s agents using template",
                    agent_count,
                )
                return await self._generate_agents_from_template(
                    agent_count,
                    config,
                    model,
                )

            return agent_graph

        except Exception as e:
            logger.error(f"Failed to generate agents from manual config: {e}")
            # 回退到模板生成
            logger.info("Falling back to template generation")
            return await self._generate_agents_from_template(
                agent_count,
                config,
                model,
            )

    def _get_default_actions(self, platform: PlatformType) -> List[ActionType]:
        """获取默认动作类型"""
        if platform == PlatformType.TWITTER:
            return ActionType.get_default_twitter_actions()
        else:
            return ActionType.get_default_reddit_actions()

    def _build_social_agent(
        self,
        *,
        agent_id: int,
        user_info: UserInfo,
        agent_graph: AgentGraph,
        model: Any,
        available_actions: list[ActionType],
    ) -> SocialAgent:
        if self._memory_mode == MemoryMode.UPSTREAM:
            return build_upstream_social_agent(
                agent_id=agent_id,
                user_info=user_info,
                agent_graph=agent_graph,
                model=model,
                available_actions=available_actions,
                context_token_limit=self._resolve_context_token_limit(),
            )

        return build_action_v1_social_agent(
            agent_id=agent_id,
            user_info=user_info,
            agent_graph=agent_graph,
            model=model,
            available_actions=available_actions,
            context_settings=self._build_action_v1_runtime_settings(
                user_info=user_info,
                model=model,
            ),
        )

    def _build_action_v1_runtime_settings(
        self,
        *,
        user_info: UserInfo,
        model: Any,
    ) -> ActionV1RuntimeSettings:
        if self._config is None:
            raise OASISInitError("Simulation config is missing for action_v1 runtime.")

        settings = get_settings()
        token_counter, token_counter_mode = self._resolve_action_v1_token_counter(model)
        resolved_context_token_limit = self._resolve_context_token_limit()
        observation_preset = apply_observation_env_overrides(ObservationPresetConfig())
        working_memory_budget = apply_working_memory_env_overrides(
            WorkingMemoryBudgetConfig(
                generation_reserve_tokens=max(
                    0,
                    int(getattr(self._config.llm_config, "max_tokens", 0) or 0),
                ),
            )
        )
        recall_preset = apply_recall_env_overrides(RecallPresetConfig())
        summary_preset = apply_summary_env_overrides(SummaryPresetConfig())
        provider_runtime_preset = apply_provider_runtime_env_overrides(
            ProviderRuntimePresetConfig()
        )
        longterm_store = self._get_action_v1_longterm_store(settings=settings)
        runtime_settings = ActionV1RuntimeSettings(
            token_counter=token_counter,
            system_message=self._build_agent_system_message(user_info=user_info),
            context_token_limit=resolved_context_token_limit or settings.OASIS_CONTEXT_TOKEN_LIMIT,
            observation_preset=observation_preset,
            summary_preset=summary_preset,
            working_memory_budget=working_memory_budget,
            recall_preset=recall_preset,
            longterm_sidecar=LongtermSidecarConfig(
                enabled=bool(settings.OASIS_LONGTERM_ENABLED and longterm_store is not None),
                store=longterm_store,
                retrieval_limit=recall_preset.retrieval_limit,
            ),
            provider_runtime_preset=provider_runtime_preset,
            memory_window_size=None,
            prompt_assembly_enabled=True,
            token_counter_mode=token_counter_mode,
            context_window_source="settings_context_limit",
            model_backend_family=str(self._config.llm_config.model_platform).lower(),
        )
        runtime_settings.validate()
        return runtime_settings

    def _build_agent_system_message(self, *, user_info: UserInfo):
        from camel.messages import BaseMessage

        return BaseMessage.make_assistant_message(
            role_name="system",
            content=user_info.to_system_message(),
        )

    def _resolve_action_v1_token_counter(self, model: Any):
        try:
            token_counter = model.token_counter
        except Exception:
            token_counter = None

        if token_counter is None:
            return HeuristicUnicodeTokenCounter(), "heuristic_fallback"
        return token_counter, "native_backend"

    def _get_action_v1_longterm_store(self, *, settings) -> Optional[LongtermStore]:
        if not settings.OASIS_LONGTERM_ENABLED:
            return None
        if self._action_v1_longterm_store is not None:
            return self._action_v1_longterm_store
        if not self._db_path:
            raise OASISInitError("Database path is missing for action_v1 long-term store.")

        chroma_path = Path(settings.OASIS_LONGTERM_CHROMA_PATH)
        chroma_path.mkdir(parents=True, exist_ok=True)
        collection_name = (
            f"{settings.OASIS_LONGTERM_COLLECTION_PREFIX}_{Path(self._db_path).stem}"
        )
        self._action_v1_longterm_store = build_chroma_longterm_store(
            collection_name=collection_name,
            embedding_backend=settings.OASIS_LONGTERM_EMBEDDING_BACKEND,
            embedding_model=settings.OASIS_LONGTERM_EMBEDDING_MODEL,
            embedding_api_key=settings.OASIS_LONGTERM_EMBEDDING_API_KEY,
            embedding_base_url=settings.OASIS_LONGTERM_EMBEDDING_BASE_URL,
            client_type="persistent",
            path=str(chroma_path),
            delete_collection_on_close=settings.OASIS_LONGTERM_DELETE_COLLECTION_ON_CLOSE,
        )
        return self._action_v1_longterm_store

    # ========================================================================
    # 模拟控制
    # ========================================================================

    async def step(
        self,
        actions: Optional[Dict[SocialAgent, Union[LLMAction, ManualAction]]] = None,
        *,
        count_towards_budget: bool = True,
    ) -> Dict[str, Any]:
        """
        执行一步模拟

        Args:
            actions: 智能体动作字典，None 表示所有智能体自动决策
            count_towards_budget: 是否消耗正式模拟 step 预算。topic 激活等
                启动阶段动作应传 False，避免挤占用户配置的 max_steps。

        Returns:
            执行结果

        Raises:
            OASISStateError: 状态不正确
            OASISOperationError: 操作失败
        """
        async with self._operation_lock:
            if not self.is_ready:
                raise OASISStateError(
                    f"Cannot execute step in state: {self._state.value}"
                )

            if count_towards_budget and self._current_step >= self._max_steps:
                await self._complete_simulation()
                return {
                    "success": True,
                    "completed": True,
                    "message": "Simulation completed - max steps reached"
                }

            try:
                # 更新状态
                self._state = SimulationState.RUNNING
                self._updated_at = datetime.now()

                # 如果没有提供动作，所有智能体自动决策
                if actions is None:
                    actions = {
                        agent: LLMAction()
                        for _, agent in self._agent_graph.get_agents()
                    }

                # 执行步骤
                await self._env.step(actions)

                # 更新计数
                if count_towards_budget:
                    self._current_step += 1
                self._updated_at = datetime.now()

                # 检查是否完成
                if count_towards_budget and self._current_step >= self._max_steps:
                    await self._complete_simulation()
                else:
                    self._state = SimulationState.READY

                logger.info(f"Step {self._current_step} executed successfully")

                return {
                    "success": True,
                    "step_executed": self._current_step,
                    "completed": self._current_step >= self._max_steps,
                    "actions_count": len(actions),
                }

            except Exception as e:
                logger.error(f"Step execution failed: {e}")
                self._state = SimulationState.ERROR
                raise OASISOperationError(f"Step execution failed: {str(e)}")

    async def pause(self) -> Dict[str, Any]:
        """暂停模拟"""
        async with self._operation_lock:
            # 可以在 READY 或 RUNNING 状态下暂停
            if not (self.is_ready or self.is_running):
                return {
                    "success": False,
                    "message": f"Cannot pause - simulation is {self._state.value}"
                }

            self._state = SimulationState.PAUSED
            self._updated_at = datetime.now()

            logger.info("Simulation paused")
            return {
                "success": True,
                "message": "Simulation paused",
                "current_step": self._current_step
            }

    async def resume(self) -> Dict[str, Any]:
        """恢复模拟"""
        async with self._operation_lock:
            if self._state != SimulationState.PAUSED:
                return {
                    "success": False,
                    "message": f"Cannot resume - simulation is {self._state.value}"
                }

            self._state = SimulationState.READY
            self._updated_at = datetime.now()

            logger.info("Simulation resumed")
            return {
                "success": True,
                "message": "Simulation resumed",
                "current_step": self._current_step
            }

    async def reset(self) -> Dict[str, Any]:
        """重置模拟"""
        async with self._operation_lock:
            try:
                # 关闭现有环境
                if self._env:
                    await self._env.close()

                # 清理数据库
                if self._db_path and os.path.exists(self._db_path):
                    os.remove(self._db_path)

                # 重置状态
                self._current_step = 0
                self._clear_runtime_state()

                self._updated_at = datetime.now()

                logger.info("Simulation reset")
                return {
                    "success": True,
                    "message": "Simulation reset successfully"
                }

            except Exception as e:
                logger.error(f"Reset failed: {e}")
                raise OASISOperationError(f"Reset failed: {str(e)}")

    async def _complete_simulation(self):
        """完成模拟"""
        self._state = SimulationState.COMPLETE
        self._updated_at = datetime.now()
        logger.info(f"Simulation completed after {self._current_step} steps")

    # ========================================================================
    # 数据查询
    # ========================================================================

    def get_agent(self, agent_id: int) -> Optional[SocialAgent]:
        """获取指定智能体"""
        if self._agent_graph:
            try:
                _, agent = self._agent_graph.get_agents([agent_id])[0]
                return agent
            except (IndexError, KeyError):
                return None
        return None

    def get_all_agents(self) -> List[SocialAgent]:
        """获取所有智能体"""
        if self._agent_graph:
            return [agent for _, agent in self._agent_graph.get_agents()]
        return []

    def get_agent_count(self) -> int:
        """获取智能体数量"""
        if self._agent_graph:
            return self._agent_graph.get_num_nodes()
        return 0

    # ========================================================================
    # 资源清理
    # ========================================================================

    async def close(self):
        """关闭 OASIS 环境并清理资源"""
        async with self._operation_lock:
            try:
                if self._env:
                    await self._env.close()
                    logger.info("OASIS environment closed")

                # 重置状态
                self._clear_runtime_state()

            except Exception as e:
                logger.error(f"Error during close: {e}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# ============================================================================
# 单例访问函数
# ============================================================================

_async_lock = asyncio.Lock()
_oasis_manager: Optional[OASISManager] = None


async def get_oasis_manager() -> OASISManager:
    """获取 OASIS 管理器单例"""
    global _oasis_manager

    async with _async_lock:
        if _oasis_manager is None:
            _oasis_manager = OASISManager()
            logger.info("OASIS Manager singleton created")

        return _oasis_manager
