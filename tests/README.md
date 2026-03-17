# OASIS Dashboard Tests

测试套件的组织结构和运行方式。

## 📁 目录结构

```
tests/
├── unit/                    # 单元测试
│   ├── test_incremental_sim_logs.py      # 增量日志语义测试
│   ├── test_metrics_analyzer.py          # 指标分析器测试
│   └── test_polarization_analyzer.py    # 极化率分析器测试
│
├── integration/             # 集成测试
│   ├── test_context_integration.py      # 上下文集成测试
│   ├── test_e2e_polarization.py         # 极化率 E2E 测试
│   └── test_metrics_integration.py      # 指标集成测试
│
├── scripts/                 # 手工测试脚本
│   ├── test_e2e_simulation.py          # 完整 E2E 测试（主测试脚本）
│   ├── test_metrics_quick.py           # 快速指标测试
│   └── test_force_create.py             # 强制创建测试
│
├── __init__.py             # Python 包标识
└── README.md               # 本文档
```

## 🚀 运行测试

### 单元测试

运行所有单元测试：
```bash
pytest tests/unit/ -v
```

运行特定单元测试：
```bash
pytest tests/unit/test_metrics_analyzer.py -v
pytest tests/unit/test_polarization_analyzer.py -v
```

### 集成测试

运行所有集成测试：
```bash
pytest tests/integration/ -v
```

运行特定集成测试：
```bash
pytest tests/integration/test_metrics_integration.py -v
```

### 手工测试脚本

**快速指标测试**（推荐）：
```bash
# 3 agents, 3 steps，验证指标功能
python tests/scripts/test_metrics_quick.py
```

**完整 E2E 测试**：
```bash
# 5 agents, 5 steps，完整测试流程
python tests/scripts/test_e2e_simulation.py

# 自定义参数
python tests/scripts/test_e2e_simulation.py 10 3  # 10 agents, 3 steps
```

## 📊 测试覆盖率

### 单元测试覆盖

| 模块 | 测试文件 | 覆盖内容 |
|------|----------|----------|
| MetricsAnalyzer | test_metrics_analyzer.py | Velocity, HHI 计算，缓存 |
| PolarizationAnalyzer | test_polarization_analyzer.py | 立场分析，极化率计算 |
| 增量日志 | test_incremental_sim_logs.py | 水位线机制 |

### 集成测试覆盖

| 模块 | 测试文件 | 覆盖内容 |
|------|----------|----------|
| 引擎集成 | test_metrics_integration.py | API 响应，指标端到端 |
| 上下文 | test_context_integration.py | Context 管理，内存 |
| 极化率 | test_e2e_polarization.py | 完整极化率流程 |

## 🧪 测试数据

测试数据存储在：
- SQLite 数据库：`oasis_simulation.db`（被 .gitignore 排除）
- 测试结果：`test-results/` 目录（被 .gitignore 排除）

## 📝 编写新测试

### 单元测试模板

```python
import pytest
from oasis_dashboard.module import ClassToTest

class TestClassToTest:
    def test_feature_x(self):
        """测试某个功能"""
        result = ClassToTest.method()
        assert result == expected_value

    def test_edge_case_y(self):
        """测试边界情况"""
        result = ClassToTest.method()
        assert result is not None
```

### 集成测试模板

```python
import pytest
import requests

BASE_URL = "http://localhost:3000"

def test_api_endpoint():
    """测试 API 端点"""
    response = requests.get(f"{BASE_URL}/api/sim/status")
    assert response.status_code == 200
    data = response.json()
    assert "polarization" in data
```

## ⚙️ 配置

### pytest 配置（pyproject.toml）

测试配置已在 `pyproject.toml` 中配置：
- 测试发现路径：`tests/`
- asyncio 支持
- 超时设置

### 环境变量

测试需要以下环境变量：
- `OASIS_BASE_URL`: API 服务地址（默认 http://localhost:3000）
- `OPENAI_API_KEY`: LLM API 密钥（如需测试 LLM 功能）

## 🐛 调试失败的测试

### 查看详细输出
```bash
pytest tests/unit/test_metrics_analyzer.py -v -s
```

### 进入调试模式
```bash
pytest tests/unit/test_metrics_analyzer.py -v --pdb
```

### 只运行失败的测试
```bash
pytest tests/unit/ -x --tb=short
```

## 📚 相关文档

- [主项目 README](../README.md)
- [测试脚本使用指南](../TEST_SCRIPTS_README.md)
- [烟雾测试文档](../artifacts/smoke/)
