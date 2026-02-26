# OASIS Dashboard v1.0.0

**OASIS Dashboard** 是一个用于实时监控和控制 **OASIS (Open-ended Autonomous Social Intelligence Simulation)** 引擎的 Web 应用程序。它提供了一个直观的界面来配置、运行和分析复杂的社会模拟实验，支持基于本地大语言模型（如 Qwen2.5-3B）的真实 OASIS 引擎。

---

## ✨ 功能特性

- **真实 OASIS 引擎**: 集成真实的 `camel-oasis` 引擎，而非模拟器，确保模拟的准确性和深度。
- **本地模型支持**: 支持通过 Ollama 运行本地大语言模型（如 Qwen2.5-3B），无需依赖外部 API，降低成本并保护数据隐私。
- **实时监控**: 实时查看模拟状态、KPI 指标（活跃 Agent、总帖子数、极化指数）和智能体活动。
- **动态控制**: 在模拟运行时动态调整参数、注入事件和干预智能体行为。
- **数据可视化**: 通过社交网络图、趋势分析和地理热图直观地理解模拟过程。
- **用户画像生成**: 基于真实世界数据集（如 Reddit）生成具有文化背景的智能体画像。
- **日志分析**: 详细记录和分析每个智能体的决策过程和交互行为。
- **群聊监控**: 观测群体讨论、意见形成和共谋行为。
- **模块化设计**: 前后端分离，易于扩展和二次开发。

---

## 🚀 快速开始

### 环境要求

- **操作系统**: Ubuntu 22.04 LTS (推荐)
- **硬件**: 至少 4核 CPU, 8GB 内存, 40GB 硬盘
- **软件**: Node.js 20+, Python 3.10+, Ollama, Nginx

### 本地开发

1. **克隆仓库**
   ```bash
   git clone https://github.com/SWJTU-AI-Lab/oasis-dashboard.git
   cd oasis-dashboard
   ```

2. **安装依赖**
   ```bash
   npm install
   pip install -r requirements.txt
   ```

3. **配置本地模型**
   ```bash
   ollama pull qwen2.5:3b
   ```

4. **启动开发服务器**
   ```bash
   npm run dev
   ```

5. **访问**
   - 前端: `http://localhost:5173`
   - 后端: `http://localhost:3000`

---

## 部署

### 生产环境部署 (推荐)

请参考 `DEPLOYMENT_MANUAL.md` 获取在您自己的服务器上进行完整独立部署的详细指南。

### Vercel + Render/Railway (免费)

请参考 `PERMANENT_DEPLOYMENT_GUIDE.md` 获取在免费平台上进行永久部署的指南。

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| 前端 | React, TypeScript, Vite, TailwindCSS |
| 后端 | Node.js, Express, Socket.io |
| 模拟引擎 | Python, camel-ai, Ollama |
| 数据库 | Neo4j (用于社交网络) |
| 部署 | Nginx, Docker, Vercel, Render |

---

## 🤝 贡献

我们欢迎任何形式的贡献！请在提交 Pull Request 前阅读 `CONTRIBUTING.md`。

---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。
