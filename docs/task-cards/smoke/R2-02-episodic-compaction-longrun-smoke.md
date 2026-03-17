# 任务卡：R2-02 Episodic Compaction 长步数 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Smoke Test / Memory Compaction |
| **负责人** | @A侧记忆负责人 |
| **协作人** | @引擎负责人 |
| **关联 Issue** | #7, #26 |

---

## 1. 背景

#7 是长期记忆主 Issue；#26 明确要求将旧的原始对话轮次（old raw turns）从线性历史记录（linear chat history）转为确定性的片段式压缩（deterministic episodic compaction），并且要求保留近期的原始轮次（recent raw turns），将旧轮次压缩成 `EpisodeRecord`，且不引入新的大语言模型（LLM）摘要化（summarization）。

第一轮测试只证明了短步数下 `context/memory` 链路可运行。第二轮要验证在更长步数下，记忆是否真的受控，而不是继续温和地膨胀到未来导致系统崩溃。

## 2. 目标

验证在 20-30 步的场景下：

*   近期的原始轮次仍被保留；
*   旧的原始轮次被片段化（episodic）；
*   `avg_memory_records` 与 `avg_context_tokens` 的增长斜率变缓；
*   `EpisodeRecord` 结构稳定可读取。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| 片段式压缩主链路 | B 侧持久化存储（durable store） |
| Context 指标 | 检索排序（retrieval ranking）优化 |
| `EpisodeRecord` 结构 | 向量后端持久化 |
| 长步数稳定性 | |

## 4. 前置条件

*   `context_smoke.py` 可运行。
*   A 侧片段式压缩已接入主链路。
*   使用单进程数据库写入方式。

## 5. 执行步骤

**(1) CLI 长步数 smoke**

```bash
.venv/bin/python -m oasis_dashboard.context_smoke \
  --model-platform ollama \
  --model-type qwen3:8b \
  --agent-count 3 \
  --steps 20 \
  --platform reddit \
  --topic AI \
  --json
```

**(2) 记录每一步**

*   `posts`
*   `step_time`
*   `context_avg`
*   `context_max`
*   `memory_avg`
*   `retrieve_avg_ms`
*   `user` / `assistant` / `function` / `tool` 消息计数

**(3) 抽查片段化结果**

检查是否存在：

*   旧的原始消息缩减
*   `EpisodeRecord` 替代旧记录
*   `query_source` / `summary_text` / `metadata` 等字段结构稳定

## 6. 通过标准 (Gate)

*   [ ] 20 步可稳定跑完
*   [ ] `memory_avg` 未出现异常跳涨
*   [ ] `context_avg` 增长但受控
*   [ ] 旧的原始轮次被压缩，不再线性保留全部历史
*   [ ] 至少抽取到 2 条有效的 `EpisodeRecord`
*   [ ] 无额外 LLM 摘要化痕迹

## 7. 失败标准

*   长步数仍然线性堆积原始历史记录。
*   Context token 异常飙升。
*   检索耗时失控。
*   片段（episode）结构不稳定或不可读。

## 8. 证据要求

*   `artifacts/smoke/r2_02_compaction_report.md`
*   `artifacts/smoke/r2_02_context_metrics.csv`
*   `artifacts/smoke/r2_02_episode_samples.json`

## 9. 备注

这张卡验证的是：#26 到底是不是“真的在压缩历史”，而不是只是换了个更优雅的名字继续堆积历史。
