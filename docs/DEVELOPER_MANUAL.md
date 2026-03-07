# OASIS Dashboard 二次开发手册

## 目录

1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [开发环境设置](#开发环境设置)
5. [核心概念](#核心概念)
6. [常见开发任务](#常见开发任务)
7. [API 参考](#api-参考)
8. [调试技巧](#调试技巧)
9. [贡献指南](#贡献指南)

---

## 项目概述

OASIS Dashboard 是一个用于实时监控和控制 OASIS 社会模拟引擎的 Web 应用程序。项目采用现代化的前后端分离架构，前端使用 React + TypeScript，后端使用 Node.js + Express，模拟引擎使用 Python + OASIS 框架。

### 核心功能

- 实时监控模拟状态（KPI、智能体、帖子等）
- 控制模拟执行（启动、暂停、单步执行）
- 生成用户画像
- 可视化智能体网络关系
- 查看通信日志和群聊记录
- 数据分析和可视化

---

## 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 类型系统 |
| Vite | 5.x | 构建工具 |
| TailwindCSS | 3.x | 样式框架 |
| React Router | 6.x | 路由管理 |
| Axios | 1.x | HTTP 客户端 |
| Recharts | 2.x | 图表库 |
| Lucide React | - | 图标库 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Node.js | 20.x | 运行时环境 |
| Express | 4.x | Web 框架 |
| TypeScript | 5.x | 类型系统 |
| tsx | - | TypeScript 执行器 |

### 模拟引擎

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行时环境 |
| OASIS | 最新版 | 社会模拟框架 |
| CAMEL-AI | 最新版 | LLM 集成框架 |
| Ollama | 最新版 | 本地 LLM 服务 |

---

## 项目结构

```
oasis-dashboard/
├── src/                    # 前端源代码
│   ├── components/         # React 组件
│   │   ├── AgentDetailDrawer.tsx
│   │   ├── DashboardLayout.tsx
│   │   └── ForceGraph.tsx
│   ├── pages/              # 页面组件
│   │   ├── OverviewPage.tsx
│   │   ├── ControlPage.tsx
│   │   ├── ProfilesPage.tsx
│   │   ├── AgentsPage.tsx
│   │   ├── LogsPage.tsx
│   │   ├── GroupChatPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   └── SettingsPage.tsx
│   ├── lib/                # 工具库
│   │   ├── api.ts          # API 客户端
│   │   ├── socket.ts       # WebSocket 客户端
│   │   └── types.ts        # TypeScript 类型定义
│   ├── App.tsx             # 应用入口
│   └── main.tsx            # React 挂载点
├── api/                    # 后端 API 路由
│   ├── sim.ts              # 模拟控制 API
│   ├── users.ts            # 用户管理 API
│   └── logs.ts             # 日志 API
├── server.ts               # Express 服务器
├── oasis_engine.py         # OASIS 引擎集成
├── requirements.txt        # Python 依赖
├── package.json            # Node.js 依赖
├── vite.config.ts          # Vite 配置
└── tsconfig.json           # TypeScript 配置
```

---

## 开发环境设置

### 1. 克隆仓库

```bash
git clone https://github.com/SWJTU-AI-Lab/oasis-dashboard.git
cd oasis-dashboard
```

### 2. 安装依赖

```bash
# Node.js 依赖
pnpm install

# Python 依赖
uv sync
```

### 3. 配置本地 LLM

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载 Qwen2.5-3B 模型
ollama pull qwen2.5:3b
```

### 4. 启动开发服务器

```bash
npm run dev
```

这将同时启动：
- 前端开发服务器（Vite）：http://localhost:5173
- 后端 API 服务器（Express）：http://localhost:3000

---

## 核心概念

### 数据流

```
用户操作 → 前端组件 → API 客户端 → 后端 API → OASIS 引擎 → 数据库
                                                    ↓
用户界面 ← 前端组件 ← WebSocket ← 后端 ← 模拟状态更新
```

### 状态管理

前端使用 React Hooks 进行状态管理：

```typescript
// 示例：使用 useState 管理模拟状态
const [simStatus, setSimStatus] = useState({
  currentStep: 0,
  totalPosts: 0,
  activeAgents: 0,
  isRunning: false,
});
```

### API 通信

前端通过 Axios 与后端通信：

```typescript
// src/lib/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

export const simulationApi = {
  getStatus: () => api.get('/sim/status'),
  step: () => api.post('/sim/step'),
  reset: () => api.post('/sim/reset'),
};
```

---

## 常见开发任务

### 任务 1：添加新的页面

#### (1) 创建页面组件

在 `src/pages/` 目录下创建新文件：

```typescript
// src/pages/NewPage.tsx
import React from 'react';

const NewPage: React.FC = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">新页面</h1>
      {/* 页面内容 */}
    </div>
  );
};

export default NewPage;
```

#### (2) 添加路由

在 `src/App.tsx` 中添加路由：

```typescript
import NewPage from './pages/NewPage';

// 在 Routes 中添加
<Route path="/new" element={<NewPage />} />
```

#### (3) 添加菜单项

在 `src/components/DashboardLayout.tsx` 中添加菜单项：

```typescript
const navItems = [
  // ... 现有菜单项
  { name: '新页面', icon: YourIcon, href: '/new' },
];
```

### 任务 2：添加新的 API 端点

#### (1) 创建 API 路由

在 `api/` 目录下创建新文件：

```typescript
// api/new.ts
import { Router } from 'express';

const router = Router();

router.get('/data', async (req, res) => {
  try {
    // 处理逻辑
    res.json({ status: 'ok', data: {} });
  } catch (error) {
    res.status(500).json({ status: 'error', message: error.message });
  }
});

export default router;
```

#### (2) 注册路由

在 `server.ts` 中注册路由：

```typescript
import newRouter from './api/new';

app.use('/api/new', newRouter);
```

#### (3) 前端调用

在 `src/lib/api.ts` 中添加 API 方法：

```typescript
export const newApi = {
  getData: () => api.get('/new/data'),
};
```

### 任务 3：修改 OASIS 引擎配置

编辑 `oasis_engine.py`：

```python
# 修改模型配置
self.model = ModelFactory.create(
    model_platform=ModelPlatformType.OLLAMA,
    model_type="qwen2.5:7b",  # 使用更大的模型
    model_config_dict={"temperature": 0.8},  # 调整温度
)

# 修改智能体配置
agent = SocialAgent(
    agent_id=i,
    user_info=UserInfo(
        user_name=f"custom_agent_{i}",
        name=f"Custom Agent {i}",
        description="自定义智能体描述",
        profile=custom_profile,  # 添加自定义画像
        recsys_type="reddit",
    ),
    agent_graph=self.agent_graph,
    model=self.model,
    available_actions=custom_actions,  # 自定义动作
)
```

---

## API 参考

### 模拟控制 API

#### GET /api/sim/status

获取模拟状态。

**响应**：

```json
{
  "status": "ok",
  "data": {
    "currentStep": 10,
    "totalPosts": 50,
    "activeAgents": 10,
    "isRunning": true
  }
}
```

#### POST /api/sim/step

执行一步模拟。

**响应**：

```json
{
  "status": "ok",
  "current_step": 11,
  "total_posts": 55,
  "active_agents": 10
}
```

#### POST /api/sim/reset

重置模拟。

**响应**：

```json
{
  "status": "ok",
  "message": "Simulation reset successfully"
}
```

#### POST /api/sim/config

更新模拟配置。

**请求体**：

```json
{
  "agentCount": 20,
  "platform": "reddit"
}
```

**响应**：

```json
{
  "status": "ok",
  "message": "Configuration updated"
}
```

---

## 调试技巧

### 前端调试

#### 1. 使用浏览器开发者工具

```javascript
// 在组件中添加 console.log
console.log('当前状态:', simStatus);

// 使用 debugger 断点
debugger;
```

#### 2. React DevTools

安装 React DevTools 浏览器扩展，查看组件状态和 props。

### 后端调试

#### 1. 使用 console.log

```typescript
console.log('收到请求:', req.body);
console.log('返回响应:', response);
```

#### 2. 使用 Node.js 调试器

```bash
node --inspect server.ts
```

### Python 引擎调试

#### 1. 使用 print 语句

```python
print(f"当前步数: {self.current_step}")
print(f"智能体数量: {len(self.agents)}")
```

#### 2. 使用 Python 调试器

```python
import pdb; pdb.set_trace()
```

---

## 贡献指南

### 代码规范

- 使用 TypeScript 进行类型检查
- 遵循 ESLint 规则
- 使用 Prettier 格式化代码
- 编写清晰的注释和文档

### 提交规范

使用语义化提交信息：

```
feat: 添加新功能
fix: 修复 bug
docs: 更新文档
style: 代码格式调整
refactor: 代码重构
test: 添加测试
chore: 构建/工具链更新
```

### Pull Request 流程

1. Fork 仓库
2. 创建特性分支：`git checkout -b feature/new-feature`
3. 提交更改：`git commit -m "feat: 添加新功能"`
4. 推送分支：`git push origin feature/new-feature`
5. 创建 Pull Request

---

**文档版本**: v1.0.0  
**最后更新**: 2026年2月25日
