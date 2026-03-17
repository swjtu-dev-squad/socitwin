# 第二轮 Smoke Test 总览

**核心目标**：在多 Agent、较长步数、非空行为场景下，验证系统能否稳定地产生可分析的社会模拟行为，并在此基础上验证记忆压缩链路、Analytics 页面和三大核心指标的可信性，同时固化数据库访问约束，为后续 #27、#30、#32、#33、#34 等更重功能提供可靠基线。

---

## 测试配置

| 配置 | Agents | Steps | Topics | RecSys |
|---|---|---|---|---|
| **A (中等)** | 3 | 10 | AI | hot-score |
| **B (增强)** | 5 | 20 | AI + politics | hot-score |

## 建议执行顺序

1.  **R2-01：多 Agent 非空产出** (先证明系统不空跑)
2.  **R2-02：Episodic Compaction 长步数** (再证明长步数下记忆受控)
3.  **R2-04：非空 Analytics / 三大指标可信性** (再证明非空数据上的图表可信)
4.  **R2-03：A/B Sidecar 联调** (然后才去接 sidecar)
5.  **R2-05：API-only / 单进程数据库约束** (最后把运行约束写死)

## 任务卡列表

*   [R2-01-multi-agent-nonempty-behavior-smoke.md](./R2-01-multi-agent-nonempty-behavior-smoke.md)
*   [R2-02-episodic-compaction-longrun-smoke.md](./R2-02-episodic-compaction-longrun-smoke.md)
*   [R2-03-sidecar-integration-smoke.md](./R2-03-sidecar-integration-smoke.md)
*   [R2-04-nonempty-analytics-metrics-smoke.md](./R2-04-nonempty-analytics-metrics-smoke.md)
*   [R2-05-api-only-db-constraint-smoke.md](./R2-05-api-only-db-constraint-smoke.md)
