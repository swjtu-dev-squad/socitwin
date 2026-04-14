import asyncio
from pathlib import Path
from types import SimpleNamespace

from oasis import UserInfo

import app.core.oasis_manager as oasis_manager_module
from app.core.oasis_manager import OASISInitError, OASISManager
from app.memory.config import MemoryMode
from app.models.simulation import ModelConfig, PlatformType, SimulationConfig


def test_action_v1_file_source_is_explicitly_rejected(tmp_path: Path) -> None:
    manager = OASISManager()
    manager._memory_mode = MemoryMode.ACTION_V1

    profile_path = tmp_path / "agents.json"
    profile_path.write_text("[]", encoding="utf-8")

    try:
        asyncio.run(
            manager._load_agents_from_file(
                str(profile_path),
                PlatformType.TWITTER,
                model=object(),
            )
        )
    except OASISInitError as exc:
        assert "template/manual" in str(exc)
        assert "agent_source=file" in str(exc)
        return

    raise AssertionError("expected action_v1 file-source rejection")


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
    assert runtime_settings.longterm_sidecar.enabled is True
    assert runtime_settings.longterm_sidecar.store is fake_store
    assert runtime_settings.model_backend_family == "deepseek"
