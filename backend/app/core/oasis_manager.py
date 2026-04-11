"""
OASIS 环境管理器

负责封装 OASIS 框架的复杂性，管理环境生命周期。
这是整个系统的核心组件，确保与 OASIS 框架的交互是安全和可控的。
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import uuid

# OASIS 框架导入
import oasis
from oasis import (
    AgentGraph,
    DefaultPlatformType,
    LLMAction,
    ManualAction,
    SocialAgent,
    UserInfo,
    ActionType,
    generate_twitter_agent_graph,
    generate_reddit_agent_graph,
)

# CAMEL 框架导入
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.configs import ChatGPTConfig

# 本地导入
from app.models.simulation import (
    SimulationConfig,
    PlatformType,
    SimulationState,
    OASISActionType,
    AgentConfig,
    ModelConfig,
)


logger = logging.getLogger(__name__)


class OASISException(Exception):
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

        # 模拟状态
        self._state: SimulationState = SimulationState.UNINITIALIZED
        self._current_step: int = 0
        self._max_steps: int = 100
        self._created_at: Optional[datetime] = None
        self._updated_at: Optional[datetime] = None

        # 配置
        self._config: Optional[SimulationConfig] = None
        self._platform_type: PlatformType = PlatformType.TWITTER

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

    def get_state_info(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        agent_count = 0
        if self._agent_graph:
            agent_count = self._agent_graph.get_num_nodes()

        return {
            "state": self._state.value,
            "current_step": self._current_step,
            "max_steps": self._max_steps,
            "agent_count": agent_count,
            "platform": self._platform_type.value,
            "created_at": self._created_at.isoformat() if self._created_at else None,
            "updated_at": self._updated_at.isoformat() if self._updated_at else None,
            "db_path": self._db_path,
        }

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
                    self._state = SimulationState.UNINITIALIZED

                # 保存配置
                self._config = config
                self._platform_type = config.platform
                self._max_steps = config.max_steps
                self._current_step = 0

                # 创建模型
                self._model = await self._create_model(config.llm_config)

                # 创建智能体图
                if config.agent_source.source_type == "file":
                    self._agent_graph = await self._load_agents_from_file(
                        config.agent_source.file_path,
                        config.platform
                    )
                elif config.agent_source.source_type == "manual":
                    self._agent_graph = await self._generate_agents_from_manual(
                        config.agent_count,
                        config
                    )
                else:
                    self._agent_graph = await self._generate_agents_from_template(
                        config.agent_count,
                        config
                    )

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

                # 创建 OASIS 环境
                self._env = oasis.make(
                    agent_graph=self._agent_graph,
                    platform=self._get_platform_type(config.platform),
                    database_path=self._db_path,
                    semaphore=32,  # 并发限制
                )

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
                    "db_path": self._db_path,
                    "simulation_id": sim_id if 'sim_id' in locals() else None,
                }

            except Exception as e:
                logger.error(f"Failed to initialize OASIS: {e}")
                await self.close()
                raise OASISInitError(f"Initialization failed: {str(e)}")

    async def _create_model(self, config: ModelConfig):
        """创建 LLM 模型"""
        try:
            from app.core.config import get_settings
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

            logger.info(f"Model created: {config.model_platform}/{config.model_type}")
            return model

        except Exception as e:
            logger.error(f"Failed to create model: {e}")
            raise OASISInitError(f"Model creation failed: {str(e)}")

    def _get_platform_type(self, platform: PlatformType):
        """转换平台类型"""
        if platform == PlatformType.TWITTER:
            return DefaultPlatformType.TWITTER
        elif platform == PlatformType.REDDIT:
            return DefaultPlatformType.REDDIT
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    async def _load_agents_from_file(self, file_path: str, platform: PlatformType) -> AgentGraph:
        """从文件加载智能体"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Agent file not found: {file_path}")

            available_actions = self._get_default_actions(platform)

            if platform == PlatformType.TWITTER:
                agent_graph = await generate_twitter_agent_graph(
                    profile_path=file_path,
                    model=self._model,
                    available_actions=available_actions,
                )
            else:
                agent_graph = await generate_reddit_agent_graph(
                    profile_path=file_path,
                    model=self._model,
                    available_actions=available_actions,
                )

            logger.info(f"Loaded {agent_graph.get_num_nodes()} agents from file")
            return agent_graph

        except Exception as e:
            logger.error(f"Failed to load agents from file: {e}")
            raise OASISInitError(f"File loading failed: {str(e)}")

    async def _generate_agents_from_template(
        self, agent_count: int, config: SimulationConfig
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

                agent = SocialAgent(
                    agent_id=profile.agent_id,
                    user_info=user_info,
                    agent_graph=agent_graph,
                    model=self._model,
                    available_actions=available_actions,
                )

                agent_graph.add_agent(agent)

            logger.info(f"Generated {agent_count} diverse agents using AgentGenerator")
            return agent_graph

        except Exception as e:
            logger.error(f"Failed to generate agents: {e}")
            raise OASISInitError(f"Agent generation failed: {str(e)}")

    async def _generate_agents_from_manual(
        self, agent_count: int, config: SimulationConfig
    ) -> AgentGraph:
        """从手动配置生成智能体"""
        try:
            from app.models.simulation import AgentConfig

            agent_graph = AgentGraph()
            available_actions = self._get_default_actions(config.platform)

            # 如果有手动配置，使用配置的智能体
            if config.agent_source.manual_config:
                logger.info(f"Creating {len(config.agent_source.manual_config)} agents from manual config")

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

                    agent = SocialAgent(
                        agent_id=agent_config.agent_id,
                        user_info=user_info,
                        agent_graph=agent_graph,
                        model=self._model,
                        available_actions=available_actions,
                    )

                    agent_graph.add_agent(agent)

                logger.info(f"Created {len(config.agent_source.manual_config)} agents from manual config")
            else:
                # 如果没有手动配置，使用生成器填充剩余数量
                logger.info(f"No manual config provided, generating {agent_count} agents using template")
                return await self._generate_agents_from_template(agent_count, config)

            return agent_graph

        except Exception as e:
            logger.error(f"Failed to generate agents from manual config: {e}")
            # 回退到模板生成
            logger.info("Falling back to template generation")
            return await self._generate_agents_from_template(agent_count, config)

    def _get_default_actions(self, platform: PlatformType) -> List[ActionType]:
        """获取默认动作类型"""
        if platform == PlatformType.TWITTER:
            return ActionType.get_default_twitter_actions()
        else:
            return ActionType.get_default_reddit_actions()

    # ========================================================================
    # 模拟控制
    # ========================================================================

    async def step(
        self,
        actions: Optional[Dict[SocialAgent, Union[LLMAction, ManualAction]]] = None
    ) -> Dict[str, Any]:
        """
        执行一步模拟

        Args:
            actions: 智能体动作字典，None 表示所有智能体自动决策

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

            if self._current_step >= self._max_steps:
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
                self._current_step += 1
                self._updated_at = datetime.now()

                # 检查是否完成
                if self._current_step >= self._max_steps:
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
                self._state = SimulationState.UNINITIALIZED
                self._current_step = 0
                self._env = None
                self._agent_graph = None

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
                self._env = None
                self._agent_graph = None
                self._state = SimulationState.UNINITIALIZED

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