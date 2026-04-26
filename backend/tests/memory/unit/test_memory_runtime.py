import asyncio

from app.memory.config import MemoryMode, normalize_memory_mode, resolve_memory_runtime_config
from app.memory.runtime import (
    MemoryRuntimeFacade,
    RuntimeBuildPlan,
)


def test_normalize_memory_mode_accepts_strings() -> None:
    assert normalize_memory_mode("upstream") is MemoryMode.UPSTREAM
    assert normalize_memory_mode("action_v1") is MemoryMode.ACTION_V1


def test_resolve_memory_runtime_config_prefers_explicit_mode() -> None:
    config = resolve_memory_runtime_config(
        explicit_mode=MemoryMode.ACTION_V1,
        settings_mode="upstream",
    )
    assert config.mode is MemoryMode.ACTION_V1


def test_resolve_memory_runtime_config_falls_back_to_settings() -> None:
    config = resolve_memory_runtime_config(
        explicit_mode=None,
        settings_mode="upstream",
    )
    assert config.mode is MemoryMode.UPSTREAM


def test_runtime_facade_builds_action_v1_runtime() -> None:
    facade = MemoryRuntimeFacade(
        resolve_memory_runtime_config(explicit_mode=MemoryMode.ACTION_V1)
    )

    model = object()
    graph = object()
    env = object()

    async def _noop_model():
        return model

    async def _noop_graph(received_model):
        assert received_model is model
        return graph

    artifacts = asyncio.run(
        facade.build_runtime(
            RuntimeBuildPlan(
                create_model=_noop_model,
                build_agent_graph=_noop_graph,
                create_environment=lambda built_graph: env if built_graph is graph else None,
            )
        )
    )

    assert artifacts.model is model
    assert artifacts.agent_graph is graph
    assert artifacts.env is env


def test_runtime_facade_builds_upstream_runtime() -> None:
    facade = MemoryRuntimeFacade(
        resolve_memory_runtime_config(explicit_mode=MemoryMode.UPSTREAM)
    )

    model = object()
    graph = object()
    env = object()

    async def _model():
        return model

    async def _graph(received_model):
        assert received_model is model
        return graph

    artifacts = asyncio.run(
        facade.build_runtime(
            RuntimeBuildPlan(
                create_model=_model,
                build_agent_graph=_graph,
                create_environment=lambda built_graph: env if built_graph is graph else None,
            )
        )
    )

    assert artifacts.model is model
    assert artifacts.agent_graph is graph
    assert artifacts.env is env
