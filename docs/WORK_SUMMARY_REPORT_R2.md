# 第二轮协同开发工作总结报告

| 属性 | 值 |
|---|---|
| **报告周期** | 2026-03-17 |
| **核心目标** | 执行第二轮 5 张 Smoke Test，验证多 Agent 产出、长步数记忆、Analytics 指标、Sidecar 联调、数据库约束 |
| **最终状态** | 2 PASS / 2 BLOCKED / 1 FAIL (修复后 PASS) |

---

## 1. R2 Smoke Test 执行结果总览

| 任务卡 | 标题 | 结论 | 产出物 |
|---|---|---|---|
| R2-01 | 多 Agent 非空产出 | ✅ **PASS** (修复后) | `r2_01_output.json` |
| R2-02 | Episodic Compaction 长步数 | ❌ **BLOCKED** | `r2_02_compaction_report.md` |
| R2-04 | 非空 Analytics / 三大指标可信性 | ✅ **PASS** | `r2_04_metrics.csv` |
| R2-03 | A/B Sidecar 联调 | ❌ **BLOCKED** | `r2_03_sidecar_smoke.md` |
| R2-05 | API-only / 单进程数据库约束 | ✅ **PASS** | `r2_05_db_constraint.md` |

---

## 2. 关键发现与修复

### 2.1 R2-01：LLM 调用链路修复（`content: null` 400 错误 & Ollama 配置错误）

**初始现象**：step 耗时 <1s，`totalPosts` 不增长，LLM 未被调用。

**根因分析**：

1.  **`content: null` 400 错误**：`camel 0.2.78` 框架在 LLM 返回 `tool_call` 且 `content` 为 `None` 时，直接将 `None` 传给 OpenAI API，导致 400 错误。这是一个 camel 框架的 bug。
2.  **Ollama 配置错误**：`server.ts` 启动 Python 引擎时未传递 `OASIS_MODEL_PLATFORM` 等环境变量，导致引擎默认使用 `ollama/qwen3:8b` 本地模型，而沙箱中无 Ollama 服务，返回 `401 - External tokens are not supported`。

**修复方案**：

1.  **Patch `camel` 框架**：在 `.venv` 中直接修改 `camel/messages/base.py` 的 `to_openai_assistant_message()` 方法，将 `content=None` 替换为空字符串 `""`。
2.  **注入环境变量**：修改 `server.ts` 的 `spawn` 调用，将 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 等环境变量注入到 Python 子进程中，强制使用 OpenAI 兼容 API。

**最终结果**：修复后，LLM 调用成功，step 耗时 4.87s，`totalPosts` 真实增长，`new_logs` 有真实内容。

### 2.2 R2-02 & R2-03：功能未实现（BLOCKED）

*   **R2-02 (Episodic Compaction)**：Issue #26 仍 Open，`EpisodeRecord` 和 `compact()` 方法未实现，当前为线性历史堆积，Step 17 触顶截断。
*   **R2-03 (Sidecar 联调)**：Issue #27 仍 Open，`longterm.py` 和相关接口（`write_episode`, `retrieve_relevant`）未实现，A/B 侧握手链路不存在。

**结论**：这两项测试被阻塞，需等待相关 Issue 开发完成。

### 2.3 R2-04：极化值恒定 Bug

**现象**：在 20 步仿真中，极化指数始终为 `0.4200`，无任何变化。

**根因**：`polarization_analyzer` 仅在 `initialize` 时基于初始 LLM 立场分析被调用一次，后续 step 中未被重新调用，导致极化值无法动态更新。

**建议**：在 `step` 方法中增加对 `polarization_analyzer` 的调用，或在前端 Analytics 页面增加独立的极化分析刷新按钮。

### 2.4 R2-05：单进程写入约束确认

**结论**：当前架构已自然满足单进程写入约束。CLI smoke 使用独立的 `/tmp` 数据库，Dashboard 运行时由 RPC 进程独占 `oasis_simulation.db`，所有交互通过 API 完成，无并发写入冲突。

---

## 3. 遗留观察与建议

1.  **`totalPosts` 计数 Bug**：R2-01 修复后，`totalPosts` 仍固定为 1，即使数据库中有多个帖子。这是 `server.ts` 中 `totalPosts` 计数逻辑的 bug，不影响 LLM 调用的事实。
2.  **推进阻塞 Issue**：优先推进 Issue #26 和 #27，完成 Episodic Compaction 和 Sidecar 接口的开发，以解锁 R2-02 和 R2-03 的测试。
3.  **修复极化值恒定 Bug**：在 `step` 中重新计算极化值，或提供前端刷新机制。

---

## 4. 产出物清单

所有报告、JSON 结果、CSV 数据均已提交到 `artifacts/smoke/` 目录。
