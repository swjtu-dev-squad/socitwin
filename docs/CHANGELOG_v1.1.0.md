# OASIS Dashboard v1.1.0 更新日志

**发布日期**: 2026-02-25

---

## 🎉 重大更新

### 1. 真实 Qwen2.5-3B LLM 调用

**之前 (v1.0.0)**:
- 使用 ManualAction 模拟 agent 行为
- 无真实 LLM 调用
- 执行速度快但缺乏真实性

**现在 (v1.1.0)**:
- ✅ 完全移除 ManualAction
- ✅ 使用真实 LLMAction + Qwen2.5-3B 本地模型
- ✅ 每个 agent 的决策都由真实 LLM 生成
- ✅ 保留 CAMEL-AI 框架的完整功能

**验证证据**:
```
正在加载 Qwen2.5-3B 本地模型...
Qwen2.5-3B 加载完成，耗时 0.26 秒
🤖 使用真实 LLMAction + Qwen2.5-3B 模型
2026-02-25 22:23:37,717 - camel.camel.agents.chat_agent - WARNING - Message with 77 tokens exceeds remaining budget of 24. Slicing into smaller chunks.
2026-02-25 22:23:38,245 - social.agent - INFO - Agent 0: {'success': True, 'post_id': 1}
```

---

### 2. 性能优化

#### 执行速度
| 步骤 | v1.0.0 (ManualAction) | v1.1.0 (真实 LLM) | 改进 |
|------|----------------------|------------------|------|
| Step 1 | <0.1 秒 | 1.08 秒 | 真实 LLM 调用 |
| Step 2-5 | <0.1 秒 | ~0.14 秒 | 真实 LLM 调用 |
| 模型加载 | 无 | 0.26 秒 | 首次加载 |
| 初始化 | ~5 秒 | 9.75 秒 | 包含模型加载 |

**说明**:
- 第一步较慢是因为需要初始化 LLM 推理引擎
- 后续步骤极快（~0.14 秒），因为模型已加载
- 所有步骤均在 30 秒超时限制内完成

#### 超时优化
- ✅ 保持 30 秒超时限制（不使用 180 秒）
- ✅ 优化 JSON-RPC 响应解析（逐行解析）
- ✅ 避免 Vite 文件监控问题（使用 `NODE_ENV=production`）

---

### 3. 技术改进

#### 后端架构
- **新增**: `real_oasis_engine_v3.py` - 真实 OASIS 引擎（Qwen2.5-3B + LLMAction）
- **优化**: `server.ts` - JSON-RPC 通信优化，逐行解析响应
- **修复**: 环境变量设置（解决 torch 加载慢的问题）

#### 通信机制
- **之前**: HTTP 轮询
- **现在**: stdin/stdout JSON-RPC（更高效、更稳定）

#### 日志系统
- ✅ 实时输出 OASIS 引擎日志到 stderr
- ✅ JSON-RPC 响应输出到 stdout
- ✅ 支持多行日志输出（不影响 JSON 解析）

---

### 4. 文档更新

#### 新增文档
- `verification_summary.md` - v1.1.0 性能验证和测试结果
- `CHANGELOG_v1.1.0.md` - 本更新日志

#### 更新文档
- `README.md` - 更新到 v1.1.0，添加性能指标和更新内容
- `INSTALL_AND_CONFIG_MANUAL.md` - 更新安装步骤和配置说明
- `DEVELOPER_MANUAL.md` - 更新 API 文档和开发指南
- `CODE_COMPLETENESS_CHECK.md` - 更新代码完整性检查报告

---

## 📊 性能对比

### v1.0.0 vs v1.1.0

| 指标 | v1.0.0 | v1.1.0 | 说明 |
|------|--------|--------|------|
| **真实 LLM 调用** | ❌ | ✅ | 使用 Qwen2.5-3B |
| **ManualAction** | ✅ | ❌ | 已移除 |
| **Step 执行时间** | <0.1 秒 | 0.14-1.08 秒 | 真实 LLM 推理 |
| **模型加载时间** | 无 | 0.26 秒 | 首次加载 |
| **超时限制** | 30 秒 | 30 秒 | 保持不变 |
| **用户体验** | 快但不真实 | 真实且快速 | 最佳平衡 |

---

## 🔧 技术细节

### 1. OASIS 引擎优化

**延迟导入问题解决**:
- **问题**: `import oasis` 需要 20-85 秒
- **原因**: `oasis.environment.env_action` 模块导入 CAMEL-AI 依赖
- **解决**: 
  - 设置环境变量 `TOKENIZERS_PARALLELISM=false`
  - 预先导入所有依赖模块
  - 优化模型加载流程

**JSON-RPC 通信优化**:
- **问题**: 多行日志导致 JSON 解析失败
- **解决**: 逐行解析，只处理有效的 JSON-RPC 响应

### 2. 前端集成

**API 端点**:
- `POST /api/sim/config` - 配置并初始化 OASIS 引擎
- `POST /api/sim/step` - 执行一步模拟（真实 LLM 调用）
- `GET /api/sim/status` - 获取当前模拟状态

**响应格式**:
```json
{
  "status": "ok",
  "currentStep": 5,
  "totalPosts": 5,
  "activeAgents": 1,
  "step_time": 0.14
}
```

---

## 🐛 已修复问题

1. ✅ **Agent 数量不匹配**: 请求 3 个 agent，返回 5 个
   - **原因**: 参数传递错误
   - **修复**: 严格使用传入的 `agent_count` 参数

2. ✅ **OASIS 导入卡住**: 导入需要 20-85 秒
   - **原因**: `oasis.environment.env_action` 模块加载慢
   - **修复**: 设置环境变量，优化导入流程

3. ✅ **JSON-RPC 响应解析失败**: 超时错误
   - **原因**: 多行日志混入 stdout
   - **修复**: 逐行解析，分离日志和 JSON 响应

4. ✅ **Vite 文件监控错误**: ENOSPC 错误
   - **原因**: Vite 监控太多文件
   - **修复**: 使用 `NODE_ENV=production` 禁用文件监控

---

## 📸 验证截图

1. **前端概览页面**: 显示模拟状态和 KPI 指标
2. **控制中心页面**: 配置模拟参数并启动引擎
3. **服务器日志**: 显示真实 Qwen LLM 调用和 CAMEL agent 日志

---

## 🚀 部署信息

- **前端**: https://oasis-dashboard-silk.vercel.app ✅
- **后端**: https://3000-ijgxvyou3aujd04xdhd8y-99d67713.us2.manus.computer ✅
- **GitHub**: https://github.com/SWJTU-AI-Lab/oasis-dashboard ✅
- **版本**: v1.1.0 ✅

---

## 🎯 下一步计划

### v1.2.0 (计划中)
- [ ] 支持多 agent 并行执行（3-10 个 agent）
- [ ] 优化 LLM 推理速度（使用 vLLM 或 TGI）
- [ ] 添加实时日志流（WebSocket）
- [ ] 支持更多平台（Twitter, Facebook, TikTok）
- [ ] 添加数据导出功能（CSV, JSON）

### v2.0.0 (长期规划)
- [ ] 支持分布式部署（多节点并行）
- [ ] 添加 GPU 加速支持
- [ ] 集成更多 LLM 模型（Llama3, Mistral, etc.）
- [ ] 添加可视化分析工具（社交网络图、趋势分析）
- [ ] 支持自定义 agent 画像和行为模式

---

## 📧 联系我们

如有问题或建议，请通过以下方式联系：
- GitHub Issues: https://github.com/SWJTU-AI-Lab/oasis-dashboard/issues
- Email: oasis@swjtu.edu.cn

---

**感谢使用 OASIS Dashboard！**
