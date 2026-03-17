# 任务卡：R2-03 A/B Long-term Sidecar 联调 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P1 |
| **类型** | Smoke Test / Interface Integration |
| **负责人** | @B侧long-term负责人 |
| **协作人** | @A侧记忆负责人 |
| **关联 Issue** | #7, #26, #27 |

---

## 1. 背景

#27 已明确：B 侧目标是在共享的 `EpisodeRecord` 契约上提供可插拔的持久化存储（durable store）与检索（retrieval）能力；长期记忆的写入单元必须是 `EpisodeRecord`，检索查询（retrieval query）不能直接使用原始观察提示（raw observation prompt），`query_source` 只能来自提炼后的话题（distilled topic）、近期的片段式摘要（recent episodic summary）或结构化事件查询（structured event query）。

这张卡的核心是验证：A 侧的片段（episode）输出，B 侧能否稳定接住并取回来。

## 2. 目标

验证最小联调链路：

*   A 侧输出 `EpisodeRecord`
*   B 侧 `write_episode` / `write_episodes` 可接收
*   `retrieve_relevant(query, limit)` 可返回兼容结构
*   `query_source` 不违反共享契约

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| `longterm.py` 最小接口 | 大规模向量检索优化 |
| 内存中持久化存储 | 持久化后端性能评测 |
| 写入/检索正确性 | 召回率（recall）学术评估 |
| `EpisodeRecord` 对接 | |

## 4. 前置条件

*   #26 产出的 `EpisodeRecord` 已可样本化输出。
*   B 侧 Sidecar 最小接口已存在或待补充。
*   先使用内存中（in-memory）路由，避免被外部存储拖住节奏。#27 的验收也明确要求至少完成内存中路由的正确性。

## 5. 执行步骤

**(1) 准备 A 侧 `EpisodeRecord` 样本**

从 R2-02 或测试 fixture 中导出 3-5 条 `EpisodeRecord`。

**(2) 写入 Sidecar**

调用：
*   `write_episode(episode)`
*   `write_episodes(episodes)`

**(3) 构造合法 query**

`query_source` 只能从以下类型中选择，不允许直接使用原始观察提示：
*   提炼后的话题
*   近期的片段式摘要
*   结构化事件查询

**(4) 执行 retrieve**

调用：`retrieve_relevant(query, limit=3)`

**(5) 验证返回结果**

检查：
*   结果结构兼容 `EpisodeRecord`
*   内容与 query 有相关性
*   `clear` 后可正确清空

## 6. 通过标准 (Gate)

*   [ ] `write_episode()` 正常
*   [ ] `write_episodes()` 正常
*   [ ] `retrieve_relevant()` 返回非空或合理空结果
*   [ ] 结果结构兼容 `EpisodeRecord`
*   [ ] `query_source` 合法
*   [ ] `clear()` 正常工作
*   [ ] 不要求原始观察直接入库

## 7. 失败标准

*   A 侧产物无法写入 B 侧。
*   B 侧返回结构漂移。
*   检索强依赖原始观察提示。
*   内存中路由自身都不稳定。

## 8. 证据要求

*   `artifacts/smoke/r2_03_sidecar_smoke.md`
*   `artifacts/smoke/r2_03_retrieve_samples.json`
*   接口调用样例与结果样例

## 9. 备注

这张卡本质上是在确认 #26 和 #27 不是两条平行宇宙，而是真能握手。
