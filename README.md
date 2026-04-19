<div align="center">

  # 🌐 Socitwin

  ### AI-Powered Multi-Agent Social Media Simulation Platform

  [![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green.svg)](https://fastapi.tiangolo.com)
  [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
  [![Code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
  [![Author](https://img.shields.io/badge/author-swjtu--dev--squad-informational.svg)](https://github.com/swjtu-dev-squad)

  [![Backend](https://img.shields.io/badge/backend-FastAPI-009688.svg)](backend/)
  [![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB.svg)](frontend/)
  [![OASIS](https://img.shields.io/badge/OASIS-integrated-purple.svg)](https://github.com/simulation-collective/oasis)

  [![Tests](https://img.shields.io/badge/tests-e2e-brightgreen.svg)](backend/tests/)
  [![Documentation](https://img.shields.io/badge/docs-latest-orange.svg)](docs/)
  [![Status](https://img.shields.io/badge/status-active-success.svg)](#)

  **Advanced social media simulation powered by LLM-driven autonomous agents**

  [Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API](#-api-docs) • [Contributing](#-contributing)

</div>

---

## 📖 Overview

**Socitwin** is an advanced multi-agent social media simulation platform that leverages the [OASIS framework](https://github.com/simulation-collective/oasis) to create realistic social interactions between AI-powered autonomous agents on platforms like Twitter and Reddit.

### 🎯 Key Capabilities

- 🤖 **LLM-Driven Agents**: Agents powered by DeepSeek, OpenAI, or other LLMs
- 🌐 **Multi-Platform Support**: Twitter and Reddit simulation environments
- 📊 **File-Driven Topics**: Configurable scenarios via YAML
- 🔄 **Hot-Reload Configuration**: Update topics without restarting
- 📈 **Comprehensive Analytics**: Track posts, interactions, and agent behavior
- 🧪 **E2E Testing**: Automated testing framework with detailed reports
- ⚡ **High Performance**: Async FastAPI backend with efficient OASIS integration

---

## ✨ Features

### 🎭 Agent System
- **Diverse Personalities**: Auto-generated agents with unique profiles, interests, and behaviors
- **Intelligent Actions**: Agents can post, comment, like, share, and follow
- **Realistic Interactions**: Recommendation systems and feed buffers for authentic social dynamics
- **Customizable**: Support for template-based, file-based, or manual agent configuration

### 📝 Topic Management
- **YAML Configuration**: Define simulation scenarios declaratively
- **Initial Post Injection**: Seed conversations with specific content
- **Auto Feed Refresh**: Ensure all agents see new content
- **Platform Agnostic**: Same topic works across different platforms

### 🔧 Simulation Control
- **Step-by-Step Execution**: Control simulation progression
- **Pause/Resume**: Manage simulation state
- **Background Tasks**: Run long simulations asynchronously
- **Detailed Logging**: Comprehensive trace of all agent actions

### 📊 Data & Analytics
- **SQLite Database**: Persistent storage of all simulation data
- **Rich Metrics**: Posts, interactions, agent activity tracking
- **Export Capabilities**: JSON export with filtering options
- **Database Queries**: Direct access to simulation data

---


### Technology Stack

**Backend:**
- [FastAPI](https://fastapi.tiangolo.com) - Modern async web framework
- [OASIS](https://github.com/simulation-collective/oasis) - Social simulation framework
- [Pydantic](https://docs.pydantic.dev) - Data validation
- [CAMEL](https://www.camel-ai.org) - LLM abstraction layer
- [SQLite](https://www.sqlite.org) - Embedded database

**Frontend:**
- [React](https://react.dev) - UI framework
- [Vite](https://vitejs.dev) - Build tool
- [TypeScript](https://www.typescriptlang.org) - Type safety

**LLM Support:**
- DeepSeek
- OpenAI (GPT-4, GPT-3.5)
- Other OpenAI-compatible APIs

**Development Tools:**
- Claude Code Skills for UI/UX design, FastAPI best practices, and React optimization

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11
- Node.js 18+
- pnpm (package manager for frontend)
- uv (package manager for backend)
- DeepSeek or OpenAI API key

### Backend Setup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Install dependencies using uv
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env and add your API keys

# 4. Start the server
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies using pnpm
pnpm install

# 3. Start development server
pnpm dev
```

### Run Your First Simulation

```bash
# Using the E2E test script
cd backend/tests/e2e
./run_tests.sh --quick

# Or via API
curl -X POST http://localhost:8000/api/sim/config \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "twitter",
    "agent_count": 5,
    "max_steps": 10
  }'

# Activate a topic
curl -X POST http://localhost:8000/api/topics/climate_change_debate/activate

# Execute simulation steps
curl -X POST http://localhost:8000/api/sim/step \
  -H "Content-Type: application/json" \
  -d '{"step_type": "auto"}'
```

---

## 🎨 Code Formatting & Linting

本项目使用自动化代码风格检查来确保代码质量。在提交 PR 之前，请确保你的代码通过所有的格式化和 linting 检查。

### Backend Code Style

**工具:**
- **Pyright** - TypeScript 风格的类型检查
- **Ruff** - 快速的 Python linter 和 formatter

**手动格式化:**
```bash
cd backend

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 检查代码风格问题
ruff check . --ignore=E501

# 自动修复可修复的问题
ruff check . --ignore=E501 --fix

# 运行类型检查
pyright app/
```

**Ruff 规则:**
- 导入排序和格式化
- 未使用的导入和变量检测
- 代码复杂度检查
- 类型安全检查

### Frontend Code Style

**工具:**
- **Prettier** - 代码格式化工具
- **TypeScript** - 类型检查

**手动格式化:**
```bash
cd frontend

# 检查代码格式
pnpm run format:check

# 自动格式化代码
pnpm run format

# 运行类型检查
pnpm run build
```

**Prettier 规则:**
- 一致的缩进和空格
- 单引号 vs 双引号
- 尾随逗号处理
- 代码行长度限制

### Pre-Commit Workflow

推荐的提交前工作流程：

```bash
# 1. 格式化后端代码
cd backend
source .venv/bin/activate
ruff check . --ignore=E501 --fix
pyright app/

# 2. 格式化前端代码
cd ../frontend
pnpm run format
pnpm run build

# 3. 提交代码
git add .
git commit -m "你的提交信息"
```

### CI/CD 检查

GitHub Actions 会自动运行以下检查：

**后端:**
- ✅ Pyright 类型检查（硬性失败）
- ✅ Ruff 代码风格检查（硬性失败）

**前端:**
- ✅ Prettier 格式检查（硬性失败）
- ✅ TypeScript + Vite 构建（硬性失败）

**注意:** 所有检查都必须通过才能合并 PR。Reviewdog 会在 PR 中添加评论，指出具体的代码问题。

---


## 🧪 Testing

### E2E Tests

```bash
# Quick test (3 steps, 3 agents)
cd backend/tests/e2e
./run_tests.sh --quick

# Full test (50 steps, 10 agents)
./run_tests.sh --full

# Custom test
./run_tests.sh --agent-count 10 --max-steps 20 --topic tech_ai_regulation

# Python script
python backend/tests/e2e/e2e_simulation_test.py --help
```

### Test Results

Results are saved to `backend/test-results/` as JSON files with detailed metrics:
- Execution time per step
- Posts and interactions delta
- Success/failure status
- Final simulation state

---

## 📖 Configuration

### Topics (YAML)

Topics are defined in `backend/config/topics.yaml`:

```yaml
topics:
  - id: "climate_change_debate"
    name: "Climate Change Debate"
    description: "Agents discuss climate policy with varying viewpoints"
    initial_post:
      content: "Climate change is the most urgent crisis of our time!"
      agent_id: 0
    settings:
      trigger_refresh: true
```

### Environment Variables

Key environment variables in `.env`:

```bash
# API Keys
DEEPSEEK_API_KEY=your_deepseek_key
OPENAI_API_KEY=your_openai_key

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=true

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:5173"]
```

## 👥 Authors

**Developed by swjtu-dev-squad**

- 🎓 **Southwest Jiaotong University** - Developer Squad
- 🌟 **Focus**: Social simulation, AI agents, and multi-agent systems

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [OASIS Framework](https://github.com/simulation-collective/oasis) - Social simulation infrastructure
- [FastAPI](https://fastapi.tiangolo.com) - Modern Python web framework
- [CAMEL Framework](https://www.camel-ai.org) - LLM abstraction layer
- All contributors and supporters of this project

---

<div align="center">

  **Built with ❤️ by swjtu-dev-squad for social simulation research**

  **Southwest Jiaotong University**

  [⬆ Back to Top](#-socitwin)

</div>
