from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.dependencies import get_simulation_service_dependency
from app.models.simulation import (
    MemoryDebugAgentStatus,
    MemoryDebugStatus,
    MemoryMode,
    PlatformType,
    SimulationState,
)
from main import app


class _StubSimulationService:
    async def get_memory_debug_status(self) -> MemoryDebugStatus:
        return MemoryDebugStatus(
            state=SimulationState.READY,
            memory_mode=MemoryMode.ACTION_V1,
            current_step=5,
            total_steps=50,
            agent_count=1,
            platform=PlatformType.TWITTER,
            context_token_limit=16384,
            generation_max_tokens=1024,
            longterm_enabled=True,
            agents=[
                MemoryDebugAgentStatus(
                    agent_id=1,
                    user_name="agent_1",
                    name="Agent One",
                    memory_runtime="action_v1",
                    memory_supported=True,
                    recent_retained_step_count=3,
                    compressed_action_block_count=1,
                    compressed_heartbeat_count=1,
                    compressed_retained_step_count=4,
                    total_retained_step_count=5,
                    last_observation_stage="interaction_reduced",
                    last_prompt_tokens=1200,
                    last_recall_gate=True,
                    last_recalled_count=2,
                    last_injected_count=1,
                )
            ],
        )


async def _override_simulation_service():
    return _StubSimulationService()


def test_memory_debug_endpoint_returns_structured_payload() -> None:
    app.dependency_overrides[get_simulation_service_dependency] = (
        _override_simulation_service
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/sim/memory")
        assert response.status_code == 200
        payload = response.json()
        assert payload["memory_mode"] == "action_v1"
        assert payload["current_step"] == 5
        assert payload["longterm_enabled"] is True
        assert len(payload["agents"]) == 1
        assert payload["agents"][0]["memory_supported"] is True
        assert payload["agents"][0]["last_observation_stage"] == "interaction_reduced"
    finally:
        app.dependency_overrides.clear()
