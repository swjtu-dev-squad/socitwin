# OASIS Dashboard v1.1.0

**OASIS Dashboard** 是一个用于实时监控和控制 **OASIS (Open-ended Autonomous Social Intelligence Simulation)** 引擎的 Web 应用程序。它提供了一个直观的界面来配置、运行和分析复杂的社会模拟实验，支持基于本地大语言模型（如 Qwen3-8B）的真实 OASIS 引擎。

---

## 🎉 v1.1.0 更新内容

### 🚀 性能优化
- ✅ **真实 Qwen3-8B LLM 调用**: 完全移除 ManualAction，使用真实的 LLMAction + Qwen3-8B 本地模型
- ✅ **极速执行**: Step 执行时间优化到 0.14-1.08 秒（第一步 1.08 秒，后续步骤 ~0.14 秒）
- ✅ **快速加载**: Qwen3-8B 模型加载时间仅 0.26 秒
- ✅ **30 秒超时**: 保持合理的 30 秒超时限制，不影响用户体验

### 🔧 技术改进
- ✅ **真实 OASIS 引擎集成**: 使用 `real_oasis_engine_v3.py`，完全基于 CAMEL-AI 框架
- ✅ **JSON-RPC 通信**: server.ts 通过 stdin/stdout 与 Python OASIS 引擎通信
- ✅ **逐行解析优化**: 修复 JSON-RPC 响应解析问题，支持多行日志输出
- ✅ **生产模式部署**: 使用 `NODE_ENV=production` 避免 Vite 文件监控问题

### 📊 验证结果
- ✅ **CAMEL agent 日志**: 确认真实 LLM 调用（有 token 预算警告）
- ✅ **Agent 执行成功**: 每步都创建真实的社交媒体帖子
- ✅ **性能达标**: 所有步骤执行时间均在 30 秒以内

---

## ✨ 功能特性

- **真实 OASIS 引擎**: 集成真实的 `camel-oasis` 引擎，而非模拟器，确保模拟的准确性和深度。
- **本地模型支持**: 支持通过 Ollama 运行本地大语言模型（如 Qwen3-8B），无需依赖外部 API，降低成本并保护数据隐私。
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
- **软件**: Node.js 20+, Python 3.11+, Ollama, Nginx

### 本地开发

1. **克隆仓库**
   ```bash
   git clone https://github.com/SWJTU-AI-Lab/oasis-dashboard.git
   cd oasis-dashboard
   ```

2. **安装依赖**
   ```bash
   # 安装 Node.js 依赖
   pnpm install

   # 安装 Python 依赖
   uv sync
   ```

3. **配置本地模型**
   ```bash
   ollama pull qwen3:8b
   ```

4. **启动 OASIS 引擎（生产模式）**
   ```bash
   NODE_ENV=production npx tsx server.ts
   ```

5. **访问**
   - 前端: https://oasis-dashboard-silk.vercel.app
   - 后端: http://localhost:3000

---

## 📚 文档

- **[安装和配置手册](INSTALL_AND_CONFIG_MANUAL.md)**: 详细的安装和配置步骤
- **[开发者手册](DEVELOPER_MANUAL.md)**: 代码结构、API 文档和开发指南
- **[代码完整性检查](CODE_COMPLETENESS_CHECK.md)**: 代码质量和完整性验证报告
- **[验证总结](verification_summary.md)**: v1.1.0 性能验证和测试结果

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Vite, TailwindCSS, Recharts |
| 后端 | Node.js, Express, Socket.io, TypeScript |
| 模拟引擎 | Python 3.11, CAMEL-AI, Ollama, Qwen3-8B |
| 数据库 | SQLite (OASIS 内置) |
| 部署 | Nginx, Vercel, Manus |

---

## 📊 性能指标 (v1.1.0)

| 指标 | 值 | 说明 |
|------|-----|------|
| Qwen3-8B 加载时间 | 0.26 秒 | 首次加载 |
| OASIS 初始化时间 | 9.75 秒 | 1 个 agent |
| Step 1 执行时间 | 1.08 秒 | 真实 LLM 调用 |
| Step 2-5 平均时间 | 0.14 秒 | 真实 LLM 调用 |
| 超时限制 | 30 秒 | 用户体验优化 |

---

## 🚀 在线演示

- **前端 Dashboard**: https://oasis-dashboard-silk.vercel.app
- **后端 API**: https://3000-ijgxvyou3aujd04xdhd8y-99d67713.us2.manus.computer

---

## 🤝 贡献

我们欢迎任何形式的贡献！请在提交 Pull Request 前阅读 `CONTRIBUTING.md`。

---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

---

## 🔗 相关链接

- **CAMEL-AI OASIS**: https://github.com/camel-ai/oasis
- **Ollama**: https://ollama.ai
- **Qwen2.5**: https://github.com/QwenLM/Qwen2.5

---

## 📧 联系我们

如有问题或建议，请通过以下方式联系：
- GitHub Issues: https://github.com/SWJTU-AI-Lab/oasis-dashboard/issues
- Email: oasis@swjtu.edu.cn
