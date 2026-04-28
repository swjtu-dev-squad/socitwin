import asyncio
from pathlib import Path
from types import SimpleNamespace

from oasis import UserInfo

import app.core.oasis_manager as oasis_manager_module
from app.core.oasis_manager import OASISManager
from app.memory.config import MemoryMode
from app.models.simulation import ModelConfig, PlatformType, SimulationConfig


class _FakeAgent:
    def __init__(self, agent_id: int) -> None:
        self.social_agent_id = agent_id


class _FakeEnv:
    def __init__(self) -> None:
        self.reset_count = 0
        self.step_calls = []
        self.closed = False

    async def reset(self) -> None:
        self.reset_count += 1

    async def step(self, actions) -> None:
        self.step_calls.append(actions)

    async def close(self) -> None:
        self.closed = True


class _FakeGraph:
    def __init__(self, agents=None) -> None:
        self._agents = list(agents or [])

    def get_num_nodes(self) -> int:
        return len(self._agents)

    def get_agents(self):
        return [(index, agent) for index, agent in enumerate(self._agents)]

    def add_agent(self, agent) -> None:
        self._agents.append(agent)


class _FakeProfile:
    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        self.user_name = f"agent_{agent_id}"
        self.name = f"Agent {agent_id}"
        self.bio = f"Bio {agent_id}"

    def to_dict(self):
        return {"profile": {"interests": ["memory"]}}


class _FakeActionV1Agent:
    def __init__(self, agent_id: int, *, user_name: str = "agent", name: str = "Agent") -> None:
        self.social_agent_id = agent_id
        self.user_info = SimpleNamespace(user_name=user_name, name=name)

    def memory_debug_snapshot(self):
        return {
            "memory_runtime": "action_v1",
            "memory_supported": True,
            "recent_retained_step_count": 3,
            "recent_retained_step_ids": [2, 3, 4],
            "compressed_action_block_count": 2,
            "compressed_heartbeat_count": 1,
            "compressed_retained_step_count": 5,
            "total_retained_step_count": 6,
            "last_observation_stage": "interaction_reduced",
            "last_observation_prompt_tokens": 777,
            "last_prompt_tokens": 1234,
            "last_recall_gate": True,
            "last_recall_gate_reason_flags": {"topic_trigger": True},
            "last_recall_query_source": "distilled_topic",
            "last_recalled_count": 2,
            "last_injected_count": 1,
            "last_prompt_budget_status": "ok",
        }


def test_action_v1_file_source_builds_twitter_agents_from_csv(tmp_path: Path, monkeypatch) -> None:
    manager = OASISManager()
    manager._memory_mode = MemoryMode.ACTION_V1

    profile_path = tmp_path / "agents.csv"
    profile_path.write_text(
        "name,username,user_char,description\n"
        "Alice,user_alice,Tech enthusiast,Longer twitter bio\n",
        encoding="utf-8",
    )

    captured = {}
    monkeypatch.setattr(oasis_manager_module, "AgentGraph", _FakeGraph)

    def _fake_build_social_agent(**kwargs):
        captured.update(kwargs)
        return _FakeAgent(kwargs["agent_id"])

    monkeypatch.setattr(manager, "_build_social_agent", _fake_build_social_agent)

    graph = asyncio.run(
        manager._load_agents_from_file(
            str(profile_path),
            PlatformType.TWITTER,
            model=object(),
        )
    )

    assert graph.get_num_nodes() == 1
    assert captured["agent_id"] == 0
    assert captured["user_info"].user_name == "user_alice"
    assert captured["user_info"].name == "Alice"
    assert captured["user_info"].description == "Longer twitter bio"
    assert (
        captured["user_info"].profile["other_info"]["user_profile"]
        == "Tech enthusiast"
    )


def test_action_v1_file_source_builds_reddit_agents_from_json(tmp_path: Path, monkeypatch) -> None:
    manager = OASISManager()
    manager._memory_mode = MemoryMode.ACTION_V1

    profile_path = tmp_path / "agents.json"
    profile_path.write_text(
        (
            '[{"username":"user_bob","realname":"Bob","bio":"Reddit bio",'
            '"persona":"Political persona","age":22,"gender":"male","mbti":"ENFP","country":"UK"}]'
        ),
        encoding="utf-8",
    )

    captured = {}
    monkeypatch.setattr(oasis_manager_module, "AgentGraph", _FakeGraph)

    def _fake_build_social_agent(**kwargs):
        captured.update(kwargs)
        return _FakeAgent(kwargs["agent_id"])

    monkeypatch.setattr(manager, "_build_social_agent", _fake_build_social_agent)

    graph = asyncio.run(
        manager._load_agents_from_file(
            str(profile_path),
            PlatformType.REDDIT,
            model=object(),
        )
    )

    assert graph.get_num_nodes() == 1
    assert captured["agent_id"] == 0
    assert captured["user_info"].user_name == "user_bob"
    assert captured["user_info"].name == "Bob"
    assert captured["user_info"].description == "Reddit bio"
    other_info = captured["user_info"].profile["other_info"]
    assert other_info["user_profile"] == "Political persona"
    assert other_info["age"] == 22
    assert other_info["gender"] == "male"
    assert other_info["mbti"] == "ENFP"
    assert other_info["country"] == "UK"


def test_build_action_v1_runtime_settings_uses_manager_config(monkeypatch) -> None:
    manager = OASISManager()
    manager._config = SimulationConfig(
        llm_config=ModelConfig(
            model_platform="DEEPSEEK",
            max_tokens=1024,
        )
    )
    manager._db_path = "/tmp/test-simulation.db"

    fake_store = object()
    monkeypatch.setattr(
        manager,
        "_get_action_v1_longterm_store",
        lambda *, settings: fake_store,
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "get_settings",
        lambda: SimpleNamespace(
            OASIS_CONTEXT_TOKEN_LIMIT=16384,
            OASIS_LONGTERM_ENABLED=True,
        ),
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "apply_recall_env_overrides",
        lambda preset: preset.__class__(
            retrieval_limit=7,
            cooldown_steps=preset.cooldown_steps,
            min_trigger_entity_count=preset.min_trigger_entity_count,
            allow_topic_trigger=preset.allow_topic_trigger,
            allow_anchor_trigger=preset.allow_anchor_trigger,
            allow_recent_action_trigger=preset.allow_recent_action_trigger,
            allow_self_authored_trigger=preset.allow_self_authored_trigger,
            deny_repeated_query_within_steps=preset.deny_repeated_query_within_steps,
            max_reason_trace_chars=preset.max_reason_trace_chars,
        ),
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "apply_summary_env_overrides",
        lambda preset: preset.__class__(
            max_action_items_per_block=11,
            compressed_action_block_drop_protected_count=preset.compressed_action_block_drop_protected_count,
            max_action_items_per_recent_turn=preset.max_action_items_per_recent_turn,
            max_authored_excerpt_chars=preset.max_authored_excerpt_chars,
            max_target_summary_chars=preset.max_target_summary_chars,
            max_local_context_chars=preset.max_local_context_chars,
            max_summary_merge_span=preset.max_summary_merge_span,
            max_heartbeat_entity_samples=preset.max_heartbeat_entity_samples,
            max_anchor_items_per_block=preset.max_anchor_items_per_block,
            max_entities_per_heartbeat=preset.max_entities_per_heartbeat,
            max_state_changes_per_turn=preset.max_state_changes_per_turn,
            max_outcome_digest_chars=preset.max_outcome_digest_chars,
            compressed_note_title=preset.compressed_note_title,
            recall_note_title="Recall title from env",
            omit_empty_template_fields=preset.omit_empty_template_fields,
        ),
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "apply_provider_runtime_env_overrides",
        lambda preset: preset.__class__(
            provider_error_matchers=preset.provider_error_matchers,
            provider_overflow_penalty_native_tiers=preset.provider_overflow_penalty_native_tiers,
            provider_overflow_penalty_heuristic_tiers=preset.provider_overflow_penalty_heuristic_tiers,
            counter_uncertainty_reserve_policy=preset.counter_uncertainty_reserve_policy,
            max_budget_retries=9,
        ),
    )

    token_counter = object()
    model = SimpleNamespace(token_counter=token_counter)
    user_info = UserInfo(
        user_name="agent_1",
        name="Agent One",
        description="Test agent",
        profile={},
        recsys_type="twitter",
    )

    runtime_settings = manager._build_action_v1_runtime_settings(
        user_info=user_info,
        model=model,
    )

    assert runtime_settings.token_counter is token_counter
    assert runtime_settings.context_token_limit == 16384
    assert runtime_settings.working_memory_budget.generation_reserve_tokens == 1024
    assert runtime_settings.recall_preset.retrieval_limit == 7
    assert runtime_settings.summary_preset.max_action_items_per_block == 11
    assert runtime_settings.summary_preset.recall_note_title == "Recall title from env"
    assert runtime_settings.provider_runtime_preset.max_budget_retries == 9
    assert runtime_settings.longterm_sidecar.enabled is True
    assert runtime_settings.longterm_sidecar.store is fake_store
    assert runtime_settings.model_backend_family == "deepseek"


def test_build_social_agent_uses_upstream_builder(monkeypatch) -> None:
    manager = OASISManager()
    manager._memory_mode = MemoryMode.UPSTREAM

    sentinel_agent = object()
    captured = {}

    def _fake_builder(**kwargs):
        captured.update(kwargs)
        return sentinel_agent

    monkeypatch.setattr(
        oasis_manager_module,
        "build_upstream_social_agent",
        _fake_builder,
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "get_settings",
        lambda: SimpleNamespace(OASIS_CONTEXT_TOKEN_LIMIT=16384),
    )

    result = manager._build_social_agent(
        agent_id=7,
        user_info=object(),
        agent_graph=object(),
        model=object(),
        available_actions=[],
    )

    assert result is sentinel_agent
    assert captured["agent_id"] == 7
    assert captured["context_token_limit"] == 16384


def test_build_social_agent_uses_action_v1_builder(monkeypatch) -> None:
    manager = OASISManager()
    manager._memory_mode = MemoryMode.ACTION_V1

    sentinel_agent = object()
    sentinel_settings = object()
    captured = {}

    monkeypatch.setattr(
        manager,
        "_build_action_v1_runtime_settings",
        lambda *, user_info, model: sentinel_settings,
    )

    def _fake_builder(**kwargs):
        captured.update(kwargs)
        return sentinel_agent

    monkeypatch.setattr(
        oasis_manager_module,
        "build_action_v1_social_agent",
        _fake_builder,
    )

    user_info = object()
    model = object()
    result = manager._build_social_agent(
        agent_id=9,
        user_info=user_info,
        agent_graph=object(),
        model=model,
        available_actions=[],
    )

    assert result is sentinel_agent
    assert captured["agent_id"] == 9
    assert captured["user_info"] is user_info
    assert captured["model"] is model
    assert captured["context_settings"] is sentinel_settings


def test_initialize_and_step_action_v1_manual_mode(monkeypatch, tmp_path: Path) -> None:
    manager = OASISManager()
    env = _FakeEnv()
    model = object()

    async def _fake_create_model(_config):
        return model

    monkeypatch.setattr(manager, "_create_model", _fake_create_model)
    monkeypatch.setattr(
        manager,
        "_create_environment",
        lambda *, agent_graph, config: env,
    )
    monkeypatch.setattr(
        manager,
        "_build_action_v1_runtime_settings",
        lambda *, user_info, model: object(),
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "build_action_v1_social_agent",
        lambda **kwargs: _FakeAgent(kwargs["agent_id"]),
    )

    config = SimulationConfig(
        platform=PlatformType.TWITTER,
        memory_mode=MemoryMode.ACTION_V1,
        db_path=str(tmp_path / "simulation.db"),
        llm_config=ModelConfig(model_platform="DEEPSEEK", max_tokens=1024),
        agent_source={
            "source_type": "manual",
            "manual_config": [
                {
                    "agent_id": 1,
                    "user_name": "agent_1",
                    "name": "Agent One",
                    "description": "Test agent",
                    "profile": {"interests": ["memory"]},
                }
            ],
        },
    )

    init_result = asyncio.run(manager.initialize(config))

    assert init_result["success"] is True
    assert init_result["memory_mode"] == "action_v1"
    assert init_result["agent_count"] == 1
    assert env.reset_count == 1

    manager._agent_graph = _FakeGraph([_FakeAgent(1)])
    step_result = asyncio.run(manager.step())

    assert step_result["success"] is True
    assert step_result["step_executed"] == 1
    assert len(env.step_calls) == 1
    assert len(env.step_calls[0]) == 1

    asyncio.run(manager.close())


def test_initialize_action_v1_template_mode(monkeypatch, tmp_path: Path) -> None:
    manager = OASISManager()
    env = _FakeEnv()
    model = object()

    async def _fake_create_model(_config):
        return model

    monkeypatch.setattr(manager, "_create_model", _fake_create_model)
    monkeypatch.setattr(
        manager,
        "_create_environment",
        lambda *, agent_graph, config: env,
    )
    monkeypatch.setattr(
        manager,
        "_build_action_v1_runtime_settings",
        lambda *, user_info, model: object(),
    )
    monkeypatch.setattr(
        oasis_manager_module,
        "build_action_v1_social_agent",
        lambda **kwargs: _FakeAgent(kwargs["agent_id"]),
    )

    fake_generator = SimpleNamespace(
        generate_batch=lambda agent_count, platform: [
            _FakeProfile(index + 1) for index in range(agent_count)
        ]
    )
    monkeypatch.setattr(
        "app.core.agent_generator.get_agent_generator",
        lambda: fake_generator,
    )

    config = SimulationConfig(
        platform=PlatformType.TWITTER,
        agent_count=2,
        memory_mode=MemoryMode.ACTION_V1,
        db_path=str(tmp_path / "template.db"),
        llm_config=ModelConfig(model_platform="DEEPSEEK", max_tokens=1024),
        agent_source={"source_type": "template"},
    )

    init_result = asyncio.run(manager.initialize(config))

    assert init_result["success"] is True
    assert init_result["memory_mode"] == "action_v1"
    assert init_result["agent_count"] == 2
    assert env.reset_count == 1

    asyncio.run(manager.close())


def test_get_memory_debug_info_for_action_v1_agent() -> None:
    manager = OASISManager()
    manager._state = oasis_manager_module.SimulationState.READY
    manager._current_step = 4
    manager._max_steps = 50
    manager._platform_type = PlatformType.TWITTER
    manager._memory_mode = MemoryMode.ACTION_V1
    manager._config = SimulationConfig(
        platform=PlatformType.TWITTER,
        memory_mode=MemoryMode.ACTION_V1,
        llm_config=ModelConfig(max_tokens=1024),
    )
    manager._agent_graph = _FakeGraph(
        [_FakeActionV1Agent(1, user_name="agent_1", name="Agent One")]
    )
    manager._action_v1_longterm_store = object()

    payload = manager.get_memory_debug_info()

    assert payload["memory_mode"] == "action_v1"
    assert payload["agent_count"] == 1
    assert payload["longterm_enabled"] is True
    assert payload["agents"][0]["memory_supported"] is True
    assert payload["agents"][0]["last_observation_stage"] == "interaction_reduced"
    assert payload["agents"][0]["last_recall_gate"] is True


def test_get_memory_debug_info_for_upstream_agent() -> None:
    manager = OASISManager()
    manager._state = oasis_manager_module.SimulationState.READY
    manager._current_step = 1
    manager._max_steps = 10
    manager._platform_type = PlatformType.TWITTER
    manager._memory_mode = MemoryMode.UPSTREAM
    upstream_agent = SimpleNamespace(
        social_agent_id=5,
        user_info=SimpleNamespace(user_name="up_5", name="Upstream Five"),
    )
    manager._agent_graph = _FakeGraph([upstream_agent])

    payload = manager.get_memory_debug_info()

    assert payload["memory_mode"] == "upstream"
    assert payload["agent_count"] == 1
    assert payload["agents"][0]["memory_supported"] is False
    assert payload["agents"][0]["recent_retained_step_count"] == 0


def test_step_can_skip_budget_count_for_setup_actions() -> None:
    manager = OASISManager()
    manager._env = _FakeEnv()
    manager._agent_graph = _FakeGraph([_FakeAgent(0)])
    manager._state = oasis_manager_module.SimulationState.READY
    manager._current_step = 2
    manager._max_steps = 3

    result = asyncio.run(
        manager.step(
            actions={_FakeAgent(0): object()},
            count_towards_budget=False,
        )
    )

    assert result["success"] is True
    assert result["step_executed"] == 2
    assert result["completed"] is False
    assert manager._current_step == 2
    assert manager._state == oasis_manager_module.SimulationState.READY
