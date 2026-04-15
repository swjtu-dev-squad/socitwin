from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.core.dependencies import get_simulation_service_dependency
from app.memory.config import MemoryMode
from app.models.simulation import (
    Agent,
    MemoryDebugAgentStatus,
    MemoryDebugStatus,
    PlatformType,
    SimulationState,
    SimulationStatus,
)
from main import app


class _StubConfig:
    recsys_type = "twitter"


class _StubOasisManager:
    _db_path = None
    _config = _StubConfig()


class _StubSimulationService:
    oasis_manager = _StubOasisManager()

    async def get_status(self) -> SimulationStatus:
        return SimulationStatus(
            state=SimulationState.READY,
            current_step=7,
            total_steps=50,
            agent_count=1,
            platform=PlatformType.TWITTER,
            memory_mode=MemoryMode.ACTION_V1,
            updated_at=datetime(2026, 4, 15, 12, 0, 0),
            total_posts=0,
            total_interactions=0,
            polarization=0.25,
            active_agents=1,
            agents=[
                Agent(
                    id=1,
                    user_name="agent_1",
                    name="Agent One",
                    description="Neutral observer interested in AI policy.",
                    bio="A careful observer.",
                    status="idle",
                    influence=0.4,
                    activity=80.0,
                    interests=["AI", "policy"],
                    following=[],
                )
            ],
        )

    async def get_memory_debug_status(self) -> MemoryDebugStatus:
        return MemoryDebugStatus(
            state=SimulationState.READY,
            memory_mode=MemoryMode.ACTION_V1,
            current_step=7,
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
                    recent_retained_step_count=2,
                    recent_retained_step_ids=[6, 7],
                    compressed_action_block_count=1,
                    compressed_heartbeat_count=1,
                    compressed_retained_step_count=3,
                    total_retained_step_count=5,
                    last_prompt_tokens=1200,
                    last_recall_gate=True,
                    last_recall_query_text="AI policy memory",
                    last_recalled_count=2,
                    last_injected_count=1,
                    last_recalled_step_ids=[2, 3],
                    last_injected_step_ids=[3],
                    last_selected_recent_step_ids=[7],
                    last_selected_compressed_keys=["action:2-3", "heartbeat:4-5"],
                    last_selected_recall_step_ids=[3],
                )
            ],
        )


async def _override_simulation_service():
    return _StubSimulationService()


def test_agent_monitor_endpoint_returns_frontend_contract() -> None:
    app.dependency_overrides[get_simulation_service_dependency] = (
        _override_simulation_service
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/sim/agents/monitor")
        assert response.status_code == 200
        payload = response.json()
        assert payload["simulation"]["memoryMode"] == "action_v1"
        assert payload["simulation"]["currentStep"] == 7
        assert len(payload["agents"]) == 1
        agent = payload["agents"][0]
        assert agent["id"] == "1"
        assert agent["memory"]["retrieval"]["status"] == "ready"
        assert agent["memory"]["debug"]["recentRetainedStepIds"] == [6, 7]
        assert agent["memory"]["debug"]["compressedRetainedStepCount"] == 3
        assert agent["memory"]["debug"]["lastInjectedStepIds"] == [3]
        assert agent["memory"]["debug"]["lastSelectedRecentStepIds"] == [7]
        assert agent["memory"]["debug"]["lastSelectedCompressedKeys"] == [
            "action:2-3",
            "heartbeat:4-5",
        ]
        assert agent["memory"]["debug"]["lastSelectedRecallStepIds"] == [3]
        assert agent["memory"]["retrieval"]["items"][0]["createdAt"] == "3"
    finally:
        app.dependency_overrides.clear()


def test_agent_monitor_detail_endpoint_returns_memory_summary() -> None:
    app.dependency_overrides[get_simulation_service_dependency] = (
        _override_simulation_service
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/sim/agents/1/monitor")
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"]["user_name"] == "agent_1"
        assert payload["status"]["contextTokens"] == 1200
        assert payload["status"]["retrievedMemories"] == 1
        assert payload["memory"]["retrieval"]["enabled"] is True
        assert "AI policy memory" in payload["memory"]["retrieval"]["content"]
    finally:
        app.dependency_overrides.clear()
