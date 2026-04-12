# 🤖 Socitwin 智能体系统

本文档提供智能体系统的核心概念和快速参考。详细实现请查看相关源文件。

## 📋 项目概览

**Socitwin** = 是一个基于 **camel-ai/oasis** 框架的多智能体社交网络模拟平台，用于研究舆论传播、极化现象和群体行为
注：**OASIS (Open-ended Autonomous Social Intelligence Simulation)**: 由 CAMEL-AI 开发的开源多智能体社交模拟框架

- **后端**: FastAPI + OASIS + DeepSeek/OpenAI,使用uv管理依赖和运行脚本
- **前端**: React + Vite + TailwindCSS，使用pnpm管理依赖
- **目标**: 研究舆论传播、极化现象、群体行为

## 🏗️ 架构概览

```
backend/
├── app/
│   ├── api/                      # REST API 端点
│   │   ├── simulation.py         # 模拟控制（config, step, status）
│   │   └── topics.py             # 主题管理（list, activate, reload）
│   ├── core/                     # 核心管理器
│   │   ├── config.py             # 配置管理（Pydantic Settings）
│   │   ├── dependencies.py       # 依赖注入（单例模式）
│   │   ├── oasis_manager.py      # OASIS 框架封装（生命周期管理）
│   │   ├── topic_loader.py       # 主题配置加载器（YAML + 热重载）
│   │   └── agent_generator.py    # 智能体生成器（多样化个性）
│   ├── models/                   # Pydantic 数据模型
│   │   ├── simulation.py         # 模拟相关模型（Agent, Config, State）
│   │   └── topics.py             # 主题相关模型（Topic, TopicConfig）
│   └── services/                 # 业务逻辑层
│       ├── simulation_service.py # 模拟服务（协调 API 和 OASIS）
│       └── topic_service.py      # 主题服务（主题激活逻辑）
├── config/                       # 配置文件
│   └── topics.yaml               # 主题定义（YAML 格式）
├── test/                         # E2E 测试框架
│   ├── e2e_simulation_test.py   # 自动化测试脚本
│   ├── run_tests.sh              # 测试运行脚本
│   └── README.md                 # 测试文档
├── data/                         # 数据目录
│   └── simulations/              # 模拟数据库（SQLite）
├── test-result/                  # 测试结果（JSON）
├── pyproject.toml                # 项目配置（uv）
├── .env.example                  # 环境变量模板
└── main.py                       # FastAPI 应用入口
```

## 🤖 智能体系统

### 核心概念

**智能体（Agent）** = 模拟的社交媒体用户

- 身份信息（姓名、用户名、简介）
- 兴趣标签（决定内容推荐）
- 行为能力（发帖、评论、点赞、关注等）
- 个性特征（MBTI、年龄、性别等）

### 三种生成方式

| 方式 | 适用场景 | 配置位置 |
|------|---------|----------|
| **模板生成** | 大规模快速创建 | `agent_source.source_type="template"` |
| **文件加载** | 可复现配置 | `agent_source.source_type="file"` |
| **手动配置** | 精确控制 | `agent_source.source_type="manual"` |

详细配置: [simulation.py](backend/app/models/simulation.py)

## 🎯 支持的动作

### Twitter
- CREATE_POST, COMMENT, LIKE, UNLIKE, REPOST, QUOTE
- FOLLOW, UNFOLLOW, MUTE, REFRESH

### Reddit
- CREATE_POST, COMMENT, LIKE, DISLIKE
- JOIN_GROUP, CREATE_GROUP, REFRESH

完整动作列表: [simulation.py](backend/app/models/simulation.py)

## 🔧 快速开始

### 1. 配置模拟

```bash
curl -X POST http://localhost:8000/api/sim/config \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "twitter",
    "agent_count": 10,
    "llm_config": {"model_platform": "DEEPSEEK"}
  }'
```

### 2. 激活主题

```bash
curl -X POST http://localhost:8000/api/topics/climate_change_debate/activate
```

### 3. 执行步骤

```bash
curl -X POST http://localhost:8000/api/sim/step \
  -H "Content-Type: application/json" \
  -d '{"step_type": "auto"}'
```

完整 API: [Swagger 文档](http://localhost:8000/docs)

## 📊 数据模型

### 核心模型

- `AgentConfig` - 智能体配置
- `SimulationConfig` - 模拟配置
- `Topic` - 主题定义
- `StepRequest` - 步骤请求

模型定义: [models/simulation.py](backend/app/models/simulation.py)

### 数据库

- SQLite 存储
- 表: user, post, comment, trace, follow, like
- 位置: `backend/data/simulations/`

## 🛠️ 技能 (Skills)

项目集成了 Claude Code Skills 来提升开发效率和代码质量：

### 🎨 UI/UX 设计
- **ui-ux-pro-max** - 智能设计系统生成器（50+ 风格、161 配色方案、57 字体搭配）
- **ckm:design-system** - 设计系统最佳实践
- **ckm:ui-styling** - UI 样式指南
- **web-design-guidelines** - Web 界面规范审查（Vercel Labs）

### 🔧 后端开发
- **fastapi-templates** - FastAPI 工程化最佳实践（异步模式、依赖注入、Repository 模式）

### 📐 前端开发
- **vercel-react-best-practices** - React/Next.js 性能优化指南
- **vercel-composition-patterns** - React 组件组合模式

### 📖 使用方法

**1. 对话中自动激活**
```
"帮我设计一个用户设置页面"
"审查这个表单的可访问性"
"优化这个 React 组件的性能"
```

**2. Slash Command（更稳定）**
```
/ui-ux-pro-max 为落地页生成设计系统
/web-design-guidelines 检查 src/pages/Home.tsx
/fastapi-templates 创建用户认证 API
```

## 🧪 测试

```bash
python e2e_simulation_test.py --help
```
