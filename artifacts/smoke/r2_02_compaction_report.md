# R2-02 Episodic Compaction 长步数 Smoke Test 报告

| 属性 | 值 |
|---|---|
| **执行时间** | 2026-03-17 |
| **结论** | ❌ BLOCKED（功能未实现） |
| **关联 Issue** | #7, #26 |
| **配置** | 3 agents, 20 steps, reddit, topic=AI, gpt-4.1-mini |

---

## 执行结果

### 20 步稳定性

20 步全部跑通，无崩溃，无 traceback。

### 内存增长数据

| 指标 | Step 1 | Step 20 | 增量 | 增长率 |
|---|---|---|---|---|
| `avg_memory_records` | 3.0 | 22.0 | +19.0 | **1.00 条/步（线性）** |
| `avg_context_tokens` | 265 | 4089 | +3824 | +239 tokens/步（Step 1-17 线性，Step 17-20 触顶截断） |
| `total_user_records` | 3 | 60 | +57 | 每步 +3（线性堆积） |
| `total_assistant_records` | 3 | 3 | 0 | 固定不变 |
| `avg_get_context_ms` | 0.4ms | 5.1ms | +4.7ms | 随记录数线性增长 |

**关键观察**：Step 17 后 `avg_context_tokens` 稳定在 4089（触达截断上限），但 `avg_memory_records` 仍继续线性增长（18→19→20→21→22），说明底层记录仍在堆积，只是被截断后不再影响 token 数。

### EpisodeRecord 检查

```
❌ No EpisodeRecord found in any step output
```

**结论**：Episodic Compaction（Issue #26）**尚未实现**。当前行为是纯线性历史堆积，旧的原始轮次未被压缩为 `EpisodeRecord`。

---

## Gate 验收状态

| 验收项 | 状态 |
|---|---|
| 20 步可稳定跑完 | ✅ PASS |
| `memory_avg` 未出现异常跳涨 | ✅ PASS（线性增长，无突变） |
| `context_avg` 增长但受控 | ⚠️ PARTIAL（Step 17 触顶截断，底层仍堆积） |
| 旧的原始轮次被压缩，不再线性保留全部历史 | ❌ FAIL（线性堆积，1.00 条/步） |
| 至少抽取到 2 条有效的 `EpisodeRecord` | ❌ BLOCKED（功能未实现） |
| 无额外 LLM 摘要化痕迹 | ✅ PASS（无 LLM 摘要调用） |

**总体结论：❌ BLOCKED — Issue #26 Episodic Compaction 尚未实现，当前为线性历史堆积。**

---

## 风险评估

当前 `avg_context_tokens` 在 Step 17 触顶（4089 tokens），这意味着：
- 在 17 步后，旧的上下文开始被截断，agent 会丢失早期记忆
- 在更长的仿真（50+ steps）中，agent 将只能看到最近的 ~17 步历史
- 这不是"受控压缩"，而是"被动截断"——行为不可预期

**建议**：优先推进 Issue #26 的实现，在 20 步以内完成 EpisodeRecord 的基础结构，避免长期仿真中的记忆丢失问题。

---

## 产出物

| 文件 | 说明 |
|---|---|
| `r2_02_compaction_report.md` | 本报告 |
| `r2_02_context_metrics.csv` | 20 步 context 指标 CSV |
| `r2_02_episode_samples.json` | EpisodeRecord 样本（空，功能未实现） |
| `r2_02_clean.json` | context_smoke 完整输出 |
