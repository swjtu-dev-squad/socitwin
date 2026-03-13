# OASIS 与项目架构详解

## 目录

1. [OASIS 是什么](#1-oasis-是什么)
2. [OASIS 是如何工作的](#2-oasis-是如何工作的)
3. [项目框架讲解](#3-项目框架讲解)
4. [快速开始](#4-快速开始)

---

## 1. OASIS 是什么

### 1.1 核心定义

**OASIS** (Open Agent Social Interaction Simulations) 是一个开源的 Python 框架，用于大规模社交媒体互动模拟。

- **GitHub**: https://github.com/camel-ai/oasis
- **官网**: https://oasis.camel-ai.org
- **包名**: `camel-oasis`

### 1.2 核心能力

| 能力 | 描述 |
|------|------|
| **超大规模** | 可同时模拟 1,000,000+ AI 智能体 |
| **真实行为** | 支持 23 种社交互动类型（发帖、评论、点赞、分享、关注等） |
| **多平台** | Twitter、Reddit、LinkedIn 等主流社交平台 |
| **LLM 驱动** | 使用大语言模型生成真实的人类行为 |
| **动态网络** | 社交关系图实时演变 |
| **推荐系统** | 可配置不同推荐算法（热门、时序、协同过滤等） |

### 1.3 应用场景

```
┌─────────────────────────────────────────────────────┐
│                  OASIS 应用场景                      │
├─────────────────────────────────────────────────────┤
│  📊 信息传播研究    - 研究谣言、新闻如何在网络扩散    │
│  🔍 群体极化分析    - 分析观点两极分化的形成过程      │
│  🧪 推荐算法验证    - 测试不同算法对用户行为的影响    │
│  🌐 社会动力学模拟  - 研究舆情演化、群体行为模式      │
│  🎯 营销策略优化    - 模拟不同营销策略的效果          │
└─────────────────────────────────────────────────────┘
```

### 1.4 技术栈

```
OASIS 技术栈
├── Python 3.10-3.11
├── camel-ai (LLM 抽象层)
│   ├── OpenAI GPT-4/GPT-3.5
│   ├── Ollama (本地模型)
│   └── 其他 LLM 提供商
├── Neo4j (图数据库，存储社交网络)
├── NetworkX (图分析)
├── Transformers (NLP 模型)
└── Sentence-Transformers (文本嵌入)
```

---

## 2. OASIS 是如何工作的

### 2.1 核心概念

#### SocialAgent (社交智能体)

每个 `SocialAgent` 代表一个虚拟用户，具有：

```python
SocialAgent {
    agent_id: int                    # 唯一标识
    user_info: UserInfo {
        user_name: str               # 用户名
        name: str                    # 显示名称
        description: str             # 个人简介
        profile: dict                # 人口统计学特征
        embeddings: dict             # 向量表示
    }
    beliefs: dict                    # 信念/观点
    personality: dict                # 性格特征
    available_actions: List[Action]  # 可执行的动作
}
```

#### AgentGraph (社交网络图)

存储智能体之间的社交关系：

```python
AgentGraph {
    nodes: List[SocialAgent]         # 智能体列表
    edges: List[Connection]          # 社交关系
    # 图结构：谁关注谁、谁和谁是好友
}
```

#### Action (动作类型)

OASIS 支持 23 种动作类型：

```
├── 内容相关
│   ├── CREATE_POST      创建帖子
│   ├── COMMENT          评论
│   ├── SHARE            分享
│   └── QUOTE_POST       引用转发
│
├── 互动相关
│   ├── LIKE_POST        点赞帖子
│   ├── LIKE_COMMENT     点赞评论
│   ├── FOLLOW           关注用户
│   ├── UNFOLLOW         取消关注
│   └── BLOCK            屏蔽用户
│
└── 其他
    ├── VIEW_PROFILE     查看个人资料
    ├── JOIN_COMMUNITY   加入社区
    └── LEAVE_COMMUNITY  离开社区
```

### 2.2 工作流程

```
┌─────────────────────────────────────────────────────────┐
│                   OASIS 模拟流程                         │
└─────────────────────────────────────────────────────────┘

    1. 初始化阶段
    ┌──────────────────────────────────────┐
    │ • 创建 AgentGraph                    │
    │ • 生成 N 个 SocialAgent              │
    │   - 分配观点/信念                     │
    │   - 建立社交关系图                    │
    │ • 配置推荐算法                        │
    └──────────────────────────────────────┘

    2. 模拟循环 (每个 Step)
    ┌──────────────────────────────────────┐
    │                                      │
    │  ┌────────────┐    ┌──────────────┐  │
    │  │ 选择活跃   │ -> │   推荐系统   │  │
    │  │   Agent    │    │  选择内容    │  │
    │  └────────────┘    └──────────────┘  │
    │       │                  │           │
    │       v                  v           │
    │  ┌──────────────────────────────┐   │
    │  │        Agent 决策             │   │
    │  │  (LLM 或 Rule-based)         │   │
    │  └──────────────────────────────┘   │
    │       │                             │
    │       v                             │
    │  ┌────────────┐    ┌──────────────┐ │
    │  │ 执行 Action│ -> │ 更新网络图   │ │
    │  └────────────┘    └──────────────┘ │
    │                                      │
    └──────────────────────────────────────┘

    3. 数据收集
    ┌──────────────────────────────────────┐
    │ • 帖子数量统计                       │
    │ • 网络极化度计算                     │
    │ • 社区检测                           │
    │ • 行为日志记录                       │
    └──────────────────────────────────────┘
```

### 2.3 LLM 驱动的决策过程

```python
# Agent 使用 LLM 生成内容的过程
agent = SocialAgent(...)

# 1. 感知环境
perceived_content = agent perceive(推荐系统的内容)

# 2. LLM 决策
action = agent.decide(
    context={
        "user_beliefs": agent.beliefs,
        "perceived_content": perceived_content,
        "personality": agent.personality
    },
    model=LLM  # 调用 GPT-4/Qwen 等
)

# 3. 执行动作
agent.execute(action)

# 4. 更新状态
agent.update_beliefs(action)
graph.update_connections(agent, action)
```

### 2.4 推荐系统

OASIS 内置多种推荐算法：

| 算法 | 工作原理 | 适用场景 |
|------|----------|----------|
| **Hot-score** | 热度排序（点赞+评论） | 模拟 Twitter/Reddit 热门内容 |
| **Chronological** | 时间倒序 | 模拟 Instagram 等社交平台 |
| **Collaborative Filtering** | 协同过滤 | 个性化推荐 |
| **Content-based** | 基于内容相似度 | 兴趣匹配 |

---

## 3. 项目框架讲解

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                 OASIS Dashboard 架构                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    前端层 (Frontend)                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │  React + TypeScript + Vite                       │  │
│  │  - 模拟控制面板                                    │  │
│  │  - 实时数据可视化                                  │  │
│  │  - 社交网络图展示                                  │  │
│  │  - 行为日志查看                                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP REST API
                      │ /api/sim/config
                      │ /api/sim/step
                      │ /api/sim/status
                      │ /api/users/generate
┌─────────────────────▼───────────────────────────────────┐
│                  中间层 (Backend)                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Node.js + Express + Socket.IO                   │  │
│  │  - REST API 服务 (端口 3000)                      │  │
│  │  - WebSocket 实时推送                             │  │
│  │  - Vite 开发服务器集成                            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │ JSON-RPC over stdin/stdout
                      │ spawn + pipe
┌─────────────────────▼───────────────────────────────────┐
│                  OASIS 引擎层 (Python)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  real_oasis_engine_v3.py                         │  │
│  │  - RealOASISEngineV3 类                          │  │
│  │  - JSON-RPC 服务器                                │  │
│  │  - OASIS 框架集成                                 │  │
│  │  - Qwen2.5-3B LLM (本地模型)                      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   数据层 (Data)                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - Neo4j (社交网络图存储)                         │  │
│  │  - SQLite (本地缓存)                              │  │
│  │  - In-Memory (运行时状态)                         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
oasis-dashboard/
├── src/                          # 前端源码
│   ├── components/               # React 组件
│   │   ├── SimulationPanel.tsx   # 模拟控制面板
│   │   ├── AgentList.tsx         # 智能体列表
│   │   ├── SocialGraph.tsx       # 社交网络可视化
│   │   └── LogViewer.tsx         # 行为日志查看器
│   ├── lib/                      # 工具库
│   │   ├── api.ts                # API 客户端
│   │   └── types.ts              # TypeScript 类型定义
│   └── main.tsx                  # React 入口
│
├── server.ts                     # Node.js 后端服务器
├── vite.config.ts                # Vite 配置
│
├── real_oasis_engine_v3.py       # Python OASIS 引擎
│   ├── RealOASISEngineV3         # 引擎主类
│   ├── initialize()              # 初始化模拟
│   ├── step()                    # 执行一步模拟
│   ├── generate_users()          # 生成用户
│   └── JSON-RPC Server           # RPC 通信
│
├── requirements.txt              # Python 依赖
├── package.json                  # Node.js 依赖
└── docs/                         # 文档目录
```

### 3.3 前端组件详解

#### 核心组件树

```
App
├── Layout
│   ├── Header                   # 顶部导航
│   └── Sidebar                  # 侧边栏
│
├── SimulationPanel              # 模拟控制面板
│   ├── ConfigForm               # 配置表单
│   │   ├── PlatformSelect       # 平台选择 (Twitter/Reddit)
│   │   ├── RecsysSelect         # 推荐算法选择
│   │   ├── AgentCountInput      # 智能体数量
│   │   └── TopicSelect          # 话题选择
│   │
│   ├── ControlButtons           # 控制按钮
│   │   ├── StartButton          # 启动模拟
│   │   ├── StepButton           # 单步执行
│   │   └── ResetButton          # 重置模拟
│   │
│   └── StatsDisplay             # 统计展示
│       ├── ActiveAgents         # 活跃智能体数
│       ├── TotalPosts           # 总帖子数
│       ├── Polarization         # 极化度
│       └── CurrentStep          # 当前步数
│
├── SocialGraphView              # 社交网络可视化
│   └── NetworkGraph             # D3.js/Cytoscape.js 图
│
├── AgentListView                # 智能体列表
│   └── AgentCard                # 单个智能体卡片
│       ├── UserInfo             # 用户信息
│       ├── Beliefs              # 信念展示
│       └── Actions              # 动作历史
│
├── GroupChatView                # 群组聊天视图
│   └── MessageList              # 消息列表
│       ├── UserMessage          # 用户消息
│       └── AgentMessage         # 智能体消息
│
└── LogViewer                    # 行为日志查看器
    └── LogEntry                 # 单条日志
```

### 3.4 后端 API 详解

#### REST API 端点

| 端点 | 方法 | 功能 | 参数 |
|------|------|------|------|
| `/api/sim/config` | POST | 配置并启动模拟 | `platform`, `recsys`, `agentCount`, `topics`, `regions` |
| `/api/sim/step` | POST | 执行一步模拟 | - |
| `/api/sim/status` | GET | 获取当前状态 | - |
| `/api/sim/reset` | POST | 重置模拟 | - |
| `/api/users/generate` | POST | 生成智能体 | `platform`, `count`, `topics`, `regions` |
| `/api/sim/group-message` | POST | 发送群组消息 | `content`, `agentName` |

#### WebSocket 事件

```typescript
// 服务器 -> 客户端
socket.on("stats_update", (data) => {
  // 模拟统计更新
  data: {
    running: boolean,
    currentStep: number,
    activeAgents: number,
    totalPosts: number,
    polarization: number
  }
});

socket.on("new_log", (data) => {
  // 新行为日志
  data: {
    timestamp: string,
    agentId: number,
    actionType: string,
    content: string,
    reason: string
  }
});

socket.on("group_message", (data) => {
  // 群组新消息
  data: {
    id: string,
    timestamp: string,
    agentId: number,
    agentName: string,
    content: string
  }
});
```

### 3.5 Python OASIS 引擎详解

#### RealOASISEngineV3 类

```python
class RealOASISEngineV3:
    """真实 OASIS 引擎 V3（速度优化版）"""

    def __init__(self, model_platform="ollama", model_type="qwen2.5:3b"):
        """
        初始化引擎
        - model_platform: LLM 平台 (ollama/openai)
        - model_type: 模型名称 (qwen2.5:3b/gpt-4o-mini)
        """

    async def initialize(self, agent_count, platform, recsys, topic):
        """
        初始化模拟环境
        - 创建 AgentGraph
        - 生成 SocialAgent
        - 配置推荐算法
        返回: 初始化状态
        """

    async def step(self):
        """
        执行一步模拟
        - 选择活跃智能体
        - 推荐系统选择内容
        - Agent 决策并执行动作
        - 更新网络图
        返回: 模拟结果
        """

    async def generate_users(self, platform, count, topics, regions):
        """
        生成用户
        返回: 生成的智能体列表
        """

    async def inject_message(self, content, agent_name):
        """
        注入人工消息
        返回: 消息对象
        """

    async def reset(self):
        """重置模拟环境"""
```

#### JSON-RPC 通信

```python
# Python 引擎启动 RPC 服务器
request = {
    "jsonrpc": "2.0",
    "method": "step",
    "params": {},
    "id": 123456789
}

# Node.js 发送请求
oasisProcess.stdin.write(JSON.stringify(request) + "\n")

# Python 返回响应
response = {
    "jsonrpc": "2.0",
    "id": 123456789,
    "result": {
        "current_step": 1,
        "total_posts": 5,
        "polarization": 0.3,
        ...
    }
}
```

### 3.6 数据流向示例

```
用户点击"启动模拟"按钮
    │
    ▼
前端: POST /api/sim/config
    {
      "agentCount": 1000,
      "platform": "Twitter",
      "recsys": "Hot-score"
    }
    │
    ▼
Node.js: 接收请求，调用 Python 引擎
    callOasisEngine("initialize", config)
    │
    ▼
Python: RealOASISEngineV3.initialize()
    1. 创建 ModelFactory (Qwen2.5-3B)
    2. 创建 AgentGraph
    3. 生成 1000 个 SocialAgent
    4. 返回初始化状态
    │
    ▼
Node.js: 更新 simulationState
    io.emit("stats_update", newState)
    │
    ▼
前端: Socket.IO 接收更新
    更新 UI 显示
```

---

## 4. 快速开始

### 4.1 环境要求

- **Python**: 3.10 或 3.11
- **Node.js**: 18+
- **Ollama**: (可选，用于本地 LLM)

### 4.2 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/SWJTU-AI-Lab/oasis-dashboard.git
cd oasis-dashboard

# 2. 安装 Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv

# 3. 创建 Python 虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 4. 安装 Python 依赖
pip install --upgrade pip
pip install -r requirements.txt

# 5. 安装 Node.js 依赖
npm install

# 6. 启动开发服务器
npm run dev
```

### 4.3 访问应用

打开浏览器访问: http://localhost:3000

### 4.4 常见问题

#### Q: 如何使用本地 Qwen 模型？

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载 Qwen2.5-3B 模型
ollama pull qwen2.5:3b

# 项目会自动使用 Ollama
```

#### Q: 如何调整智能体数量？

在启动模拟时，在控制面板中设置 `agentCount` 参数（建议从 10-100 开始测试）。

#### Q: 模拟速度如何优化？

- 使用本地模型（Qwen2.5-3B）而非 OpenAI API
- 减少 `agentCount`
- 选择简单的推荐算法（如 Chronological）

---

## 5. 参考资源

### 官方文档
- [OASIS GitHub](https://github.com/camel-ai/oasis)
- [OASIS 官网](https://oasis.camel-ai.org)
- [camel-ai 文档](https://docs.camel-ai.org/)

### 论文
- "OASIS: Open Agent Social Interaction Simulations" (2024)

### 社区
- [Discord](https://discord.gg/camel-ai)
- [GitHub Discussions](https://github.com/camel-ai/oasis/discussions)

---

**文档版本**: v1.0.0
**最后更新**: 2026-03-01
