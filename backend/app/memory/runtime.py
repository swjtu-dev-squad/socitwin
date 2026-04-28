from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .config import MemoryRuntimeConfig


class MemoryRuntimeNotImplementedError(NotImplementedError):
    """Raised when a selected memory runtime has not been migrated yet."""


@dataclass(slots=True)
class RuntimeBuildPlan:
    """Callbacks for building the runtime in a mode-aware way."""

    create_model: Callable[[], Awaitable[Any]]
    build_agent_graph: Callable[[Any], Awaitable[Any]]
    create_environment: Callable[[Any], Any]


@dataclass(slots=True)
class RuntimeBuildArtifacts:
    """Concrete runtime objects returned to OASISManager."""

    model: Any
    agent_graph: Any
    env: Any


class MemoryRuntimeFacade:
    """Phase-1 runtime facade for explicit upstream/action_v1 mode wiring."""

    def __init__(self, runtime_config: MemoryRuntimeConfig) -> None:
        self.runtime_config = runtime_config

    @property
    def mode(self) -> str:
        return self.runtime_config.mode.value

    async def build_runtime(self, plan: RuntimeBuildPlan) -> RuntimeBuildArtifacts:
        model = await plan.create_model()
        agent_graph = await plan.build_agent_graph(model)
        env = plan.create_environment(agent_graph)
        return RuntimeBuildArtifacts(
            model=model,
            agent_graph=agent_graph,
            env=env,
        )
