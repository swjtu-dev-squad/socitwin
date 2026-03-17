# 任务卡：ST-03 Analytics 真数据 / 假数据甄别 Smoke Test

- **状态**：Ready
- **优先级**：P0
- **类型**：Smoke Test / 页面审计 / 数据流核查
- **负责人**：
- **协作人**：
- **创建日期**：2026-03-17
- **关联 Issue**：#2
- **关联代码**：`src/pages/Analytics.tsx`, `src/lib/store.ts`, `server.ts`
- **预期产出**：`artifacts/smoke/st03_analytics_truth_table.md`

---

## 1. 背景与目标

Issue #2 已明确指出：Analytics 页面历史上存在大量硬编码假数据。虽然部分指标（如信息传播速度）已有演进，但仍需系统性地审计所有指标的数据来源，以防止团队基于幻觉指标做决策。

本任务的目标是核对“当前代码”与“issue 描述”之间的差异，形成一张真伪表，明确每个指标是**真实后端数据**、**前端派生值**还是**未实现/假数据**。

## 2. 范围

### In Scope
- `src/pages/Analytics.tsx`
- `src/lib/store.ts`
- `src/lib/types.ts`
- `server.ts`
- `history` / `status` / `agents` 的数据来源核查

### Out of Scope
- 立刻实现所有缺失指标
- 传播图完整后端计算
- 敏感性分析

## 3. 必查指标

- 群体极化率
- 极化趋势图
- 信息传播速度
- 从众效应指数
- A/B 测试偏差
- 观点分布矩阵
- 传播节点分析

## 4. 执行步骤

**Step 1：运行最小模拟**

执行 3～5 次 step，确保 `history` 已有多条记录。

**Step 2：打开 Analytics 页面**

逐项记录页面中展示的指标。

**Step 3：输出审计表**

在 `artifacts/smoke/st03_analytics_truth_table.md` 中，按以下格式记录审计结果：

| 指标 | 当前页面值 | 当前代码来源 | 数据类型 | 风险 | 处理建议 |
|---|---|---|---|---|---|
| | | | | | |

## 5. 通过标准 (Gate)

- [ ] Analytics 所有展示项均有来源说明。
- [ ] 无“看似真实实则硬编码”的指标继续裸奔。
- [ ] 未实现项必须明确标注 `placeholder`、`disabled` 或 `Coming Soon`。
- [ ] 真数据项可追溯到 `status`/`history`/`agents`。

## 6. 失败标准

- 指标来源说不清
- 页面数据与 store 不一致
- 假数据继续伪装成真实值
- issue 与现状冲突但无人澄清

## 7. 证据要求

- 页面截图
- `history` 导出样本
- 完整的 `st03_analytics_truth_table.md`

---

## Gate

- [ ] 能按文档步骤复现
- [ ] 证据完整
- [ ] 结论明确（Pass / Fail / Blocked）
- [ ] 若 Fail，已给出定位方向
- [ ] 若涉及代码修改，已单独提交 commit
