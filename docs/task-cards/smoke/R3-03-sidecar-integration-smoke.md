# 任务卡：R3-03 Sidecar 真联调 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Smoke Test / A-B Integration Validation |
| **负责人** | @记忆负责人 |
| **协作人** | @引擎负责人 |
| **关联 Issue** | #7, #26, #27 |

---

## 1. 背景

#26 的最新说明已经很明确：A 侧当前已经完成“旧历史事件化”的主链路，并建议下一步进入 A/B 联调；A 侧负责产出 `EpisodeRecord`，B 侧负责消费 `EpisodeRecord`、写入 long-term sidecar 并支持 retrieve。

#27 也把 B 侧最小契约写死了：

- long-term 输入单元必须是 `EpisodeRecord`
- `query_source` 只能来自 `distilled topic` / `recent episodic summary` / `structured event query`
- 交付物至少包括 `write_episode` / `write_episodes` / `retrieve_relevant` / `clear`
- 至少完成 in-memory route 的 write / retrieve correctness。

你现在既然已经补了 `EpisodeRecord` + `InMemoryLongTermSidecar`，那这张卡不再是“接口存在性”，而是验证 A/B 契约真的闭合。

## 2. 目标

验证以下链路：

- A 侧 episode 输出能被 B 侧 sidecar 正常接收；
- step 过程中 `sidecar_stats` 会变化；
- `retrieve` 能返回与 query 相关的 episode；
- `reset` 后 sidecar 状态清空；
- 非法输入会被明确拒绝。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| `EpisodeRecord` 样本输出 | persistent vector backend |
| `write_episode` / `write_episodes` | embedding recall 优化 |
| `retrieve_relevant` | 大规模性能测试 |
| `clear` / `reset` | |
| `sidecar_stats` 动态变化 | |

## 4. 前置条件

- `oasis_dashboard/longterm.py` 中最小 sidecar 已存在。
- `real_oasis_engine_v3.py` 的 step 返回值已暴露 `sidecar_stats`。
- R3-01 至少有非空行为数据。

## 5. 执行步骤

**(1) 运行 10 agents / 20 steps 场景**

复用 R3-01 配置 B，保证有更多 episode 输入材料。

**(2) 每步记录 `sidecar_stats`**

至少记录：

- `episode_count`
- `write_count`
- `retrieve_count`（若有）
- `raw_turn_count`
- `compaction_applied`

**(3) 导出 `EpisodeRecord` 样本**

抽取 3~5 条 episode，确认字段包括：

- `agent_id`
- `step_id`
- `platform`
- `observed_entities`
- `actions`
- `state_changes`
- `outcome`
- `query_source`
- `summary_text`
- `metadata`

**(4) 执行 `retrieve`**

构造合法 query：

- `distilled topic`
- `recent episodic summary`
- `structured event query`

三类至少各 1 个。

**(5) 执行 `reset`**

验证 sidecar 是否被清空，stats 是否归零或清空。

## 6. 通过标准 (Gate)

- [ ] `sidecar_stats` 在多步运行中有变化
- [ ] 至少观察到 3 条有效 `EpisodeRecord` 样本
- [ ] `write_episode()` / `write_episodes()` 已实际发生
- [ ] `retrieve_relevant()` 能返回非空或合理空结果
- [ ] 返回结构兼容 `EpisodeRecord`
- [ ] `reset` 后 sidecar 被清空
- [ ] 非法 `query_source` 会被拒绝

## 7. 失败标准

- `sidecar_stats` 始终不变
- 没有任何 `EpisodeRecord` 可观测输出
- `retrieve` 形同虚设
- `reset` 后残留旧 episode
- 不合法输入未被拦截

## 8. 证据要求

- `artifacts/smoke/r3_03_sidecar_integration_report.md`
- `artifacts/smoke/r3_03_episode_samples.json`
- `artifacts/smoke/r3_03_retrieve_results.json`
- `reset` 前后 `sidecar_stats` 对照

## 9. 备注

这张卡的本质不是“sidecar 文件存在”，而是：
A 侧整理出来的档案，B 侧档案馆能不能收、能不能查、能不能清。
