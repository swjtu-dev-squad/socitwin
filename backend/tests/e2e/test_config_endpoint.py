"""
测试 /api/sim/config 端点。

这组测试只覆盖当前新仓库的配置合同：
- 使用 `llm_config`
- `agent_count` 默认值与边界
- 平台字段校验
"""

from unittest.mock import AsyncMock

import pytest
from app.core.dependencies import get_simulation_service_dependency
from app.models.simulation import ConfigResult
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_service():
    service = AsyncMock()
    service.oasis_manager.is_initialized = False
    service.configure.return_value = ConfigResult(
        success=True,
        message="Simulation configured successfully",
        simulation_id="test-123",
        config={
            "platform": "twitter",
            "agent_count": 10,
            "memory_mode": "upstream",
        },
        agents_created=10,
    )
    app.dependency_overrides[get_simulation_service_dependency] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_simulation_service_dependency, None)


def _base_config(**overrides):
    config = {
        "platform": "twitter",
        "agent_count": 10,
        "llm_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT",
        },
    }
    config.update(overrides)
    return config


def test_configure_basic_twitter_config(client: TestClient, mock_service):
    response = client.post("/api/sim/config", json=_base_config())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["agents_created"] == 10


def test_configure_reddit_platform(client: TestClient, mock_service):
    response = client.post("/api/sim/config", json=_base_config(platform="reddit", agent_count=15))
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_configure_invalid_platform(client: TestClient):
    response = client.post(
        "/api/sim/config",
        json=_base_config(platform="invalid_platform"),
    )
    assert response.status_code == 422


def test_configure_invalid_agent_count(client: TestClient):
    for count in [0, -1, -10]:
        response = client.post("/api/sim/config", json=_base_config(agent_count=count))
        assert response.status_code == 422


def test_configure_uses_default_agent_count(client: TestClient, mock_service):
    config = {
        "platform": "twitter",
        "llm_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT",
        },
    }

    response = client.post("/api/sim/config", json=config)
    assert response.status_code == 200
    mock_service.configure.assert_awaited()
    configure_call = mock_service.configure.await_args.args[0]
    assert configure_call.agent_count == 5
