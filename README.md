# OASIS Dashboard

OASIS Dashboard 是一个基于 OASIS (Open Agent Social Interaction Simulations) 的社交媒体模拟可视化平台，支持百万级 AI 智能体的社交互动模拟和实时监控。

## 项目特性

- **实时监控**：实时显示智能体的社交互动、决策逻辑和行为数据
- **多平台支持**：支持 Reddit、Twitter、Facebook、TikTok、Instagram 等多个社交平台模拟
- **智能推荐算法**：集成 Hot-score、TwHIN-BERT、For You、EdgeRank 等推荐算法
- **可视化分析**：提供社交网络拓扑图、极化指数分析、传播深度分析等多维度可视化
- **群聊监控**：实时观测群体讨论、意见形成与共谋行为
- **用户画像生成**：基于真实数据特征，通过 LLM 生成具有丰富性格、背景和兴趣的智能体

## 技术栈

- **前端**：React + TypeScript + Vite + TailwindCSS
- **后端**：Express + Socket.io
- **可视化**：Recharts + D3.js
- **AI 引擎**：Google Gemini API
- **模拟框架**：OASIS (CAMEL-AI)

## 快速开始

### 环境要求

- Node.js 22.13.0+
- npm 或 pnpm

### 安装依赖

```bash
npm install
```

### 配置环境变量

创建 `.env.local` 文件：

```bash
GEMINI_API_KEY=your_api_key_here
DANGEROUSLY_DISABLE_HOST_CHECK=true
```

### 启动开发服务器

```bash
npm run dev
```

服务器将在 `http://localhost:3000` 启动。

### 构建生产版本

```bash
npm run build
```

## 页面导航

- `/` - 系统概览：实时 KPI 监控和趋势分析
- `/control` - 控制中心：模拟参数配置和启动控制
- `/profiles` - 用户画像生成：智能体批量生成
- `/agents` - 智能体监控：社交网络拓扑和智能体列表
- `/logs` - 通信日志：实时交互行为和决策逻辑
- `/groupchat` - 群聊监控：群体讨论和意见形成
- `/analytics` - 分析仪表板：多维度行为数据分析
- `/settings` - 设置：LLM 引擎配置和系统设置

## 项目结构

```
oasis-dashboard/
├── src/
│   ├── components/      # React 组件
│   ├── pages/          # 页面组件
│   ├── lib/            # 工具函数和类型定义
│   └── App.tsx         # 应用入口
├── server.ts           # Express 后端服务
├── vite.config.ts      # Vite 配置
├── package.json        # 项目依赖
└── README.md          # 项目文档
```

## 开发团队

SWJTU AI Lab

## 许可证

MIT License

## 相关链接

- [OASIS GitHub](https://github.com/camel-ai/oasis)
- [CAMEL-AI](https://www.camel-ai.org/)
- [AI Studio App](https://ai.studio/apps/9ec88f8e-3036-43ea-b4d5-088515ea6670)
