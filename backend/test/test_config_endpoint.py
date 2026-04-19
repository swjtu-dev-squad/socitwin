"""
测试 /api/sim/config 端点

这个测试文件专门测试模拟配置端点的功能，包括：
- 基本配置设置
- 不同平台配置
- 智能体数量配置
- DeepSeek 模型配置
- 错误处理
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.main import app
from fastapi.testclient import TestClient


class TestConfigEndpoint:
    """测试配置端点"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def mock_simulation_service(self):
        """模拟 SimulationService"""
        with patch("app.services.simulation_service.SimulationService") as mock:
            service = mock.return_value
            service.oasis_manager.is_initialized = False
            service.configure = AsyncMock(return_value={
                "success": True,
                "message": "Simulation configured successfully",
                "simulation_id": "test-123",
                "config": {
                    "platform": "twitter",
                    "agent_count": 10
                },
                "agents_created": 10
            })
            yield service

    def test_configure_basic_twitter_config(self, client, mock_simulation_service):
        """测试基本的 Twitter 配置（使用 DeepSeek）"""
        config_data = {
            "platform": "twitter",
            "agent_count": 10,
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT"
            }
        }

        with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
            response = client.post("/api/sim/config", json=config_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "agents_created" in data

    def test_configure_reddit_platform(self, client, mock_simulation_service):
        """测试 Reddit 平台配置"""
        config_data = {
            "platform": "reddit",
            "agent_count": 15,
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT"
            }
        }

        with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
            response = client.post("/api/sim/config", json=config_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_configure_with_different_agent_counts(self, client, mock_simulation_service):
        """测试不同数量的智能体配置"""
        agent_counts = [1, 5, 10, 20, 50]

        for count in agent_counts:
            config_data = {
                "platform": "twitter",
                "agent_count": count,
                "model_config": {
                    "model_platform": "OPENAI",
                    "model_type": "GPT_4O_MINI"
                }
            }

            with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
                response = client.post("/api/sim/config", json=config_data)
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    def test_configure_with_deepseek_models(self, client, mock_simulation_service):
        """测试 DeepSeek 模型配置"""
        # 测试默认的 DeepSeek 配置
        config_data = {
            "platform": "twitter",
            "agent_count": 10,
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT",
                "temperature": 0.7
            }
        }

        with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
            response = client.post("/api/sim/config", json=config_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_configure_invalid_platform(self, client):
        """测试无效平台配置"""
        config_data = {
            "platform": "invalid_platform",
            "agent_count": 10,
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT"
            }
        }

        response = client.post("/api/sim/config", json=config_data)
        # 应该返回 422 验证错误
        assert response.status_code == 422

    def test_configure_missing_required_fields(self, client):
        """测试缺少必需字段的配置"""
        # 缺少 agent_count
        config_data = {
            "platform": "twitter",
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT"
            }
        }

        response = client.post("/api/sim/config", json=config_data)
        assert response.status_code == 422

    def test_configure_invalid_agent_count(self, client):
        """测试无效的智能体数量"""
        invalid_counts = [0, -1, -10]

        for count in invalid_counts:
            config_data = {
                "platform": "twitter",
                "agent_count": count,
                "model_config": {
                    "model_platform": "DEEPSEEK",
                    "model_type": "DEEPSEEK_CHAT"
                }
            }

            response = client.post("/api/sim/config", json=config_data)
            assert response.status_code == 422

    def test_configure_service_error_handling(self, client, mock_simulation_service):
        """测试服务错误处理"""
        # 模拟服务返回错误
        mock_simulation_service.configure = AsyncMock(side_effect=Exception("Service error"))

        config_data = {
            "platform": "twitter",
            "agent_count": 10,
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT"
            }
        }

        with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
            response = client.post("/api/sim/config", json=config_data)

            # 端点应该捕获错误并返回失败响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "failed" in data["message"].lower()

    def test_configure_with_temperature(self, client, mock_simulation_service):
        """测试带温度参数的配置"""
        config_data = {
            "platform": "twitter",
            "agent_count": 10,
            "model_config": {
                "model_platform": "OPENAI",
                "model_type": "GPT_4O_MINI",
                "temperature": 0.8
            }
        }

        with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
            response = client.post("/api/sim/config", json=config_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_configure_response_structure(self, client, mock_simulation_service):
        """测试配置响应的结构"""
        config_data = {
            "platform": "twitter",
            "agent_count": 10,
            "model_config": {
                "model_platform": "DEEPSEEK",
                "model_type": "DEEPSEEK_CHAT"
            }
        }

        with patch("app.core.dependencies.get_simulation_service_dependency", return_value=mock_simulation_service):
            response = client.post("/api/sim/config", json=config_data)

            assert response.status_code == 200
            data = response.json()

            # 验证响应包含所有必需字段
            assert "success" in data
            assert "message" in data
            assert "simulation_id" in data
            assert "agents_created" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
