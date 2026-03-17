# 任务卡：R5-02 推荐策略影响下的传播 / 极化 / 羊群对比分析

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Analytics / Comparative Evaluation |
| **负责人** | 分析负责人 |
| **协作人** | 可视化负责人、推荐算法负责人 |
| **关联 Issue** | #33, #24, #22, #32 |

---

## 1. 背景

#33 负责“看见传播”，#24 负责“三大指标计算与分析报告”，#22 负责“信息传播、群体极化、羊群效应三幅图”，而 #32 负责推荐策略。现在的问题不是这些东西有没有，而是：**不同推荐策略是否真的导致不同的传播形态、极化结果和羊群行为？** 这才是实验平台的灵魂，不然推荐器只是换个名字、图表只是会动而已。

## 2. 目标

在 R5-01 的实验结果基础上，建立最小对比分析能力，使系统能够展示：

- 推荐策略对传播速度的影响；
- 推荐策略对极化曲线的影响；
- 推荐策略对 HerdIndex 的影响；
- 不同策略下传播图结构差异。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| 指标对比图 | 归因分析 / SHAP / Sobol（#31） |
| 传播图差异展示 | 复杂统计显著性检验 |
| 推荐器间结果对照 | 学术级论文图表润色 |
| 最小结论导出 | |

## 4. 建议最小展示项

至少做以下 4 组图/表：

1.  **Polarization 曲线对比**
2.  **HerdIndex 曲线对比**
3.  **Velocity 柱状图或折线图对比**
4.  **传播图快照对比**（同一 step，不同推荐器）

## 5. 实现方案

- **数据来源**：直接读取 R5-01 的实验结果与 Analytics 指标（`polarization trace`, `herdIndex trace`, `velocity summary`, `propagationData snapshot`）。
- **最小 UI 方案**：新增一个最小 Compare 面板，支持选择两个推荐器和一个数据集，展示 4 个核心差异图。
- **输出格式**：
  ```typescript
  type CompareResult = {
    recommenderA: string;
    recommenderB: string;
    polarizationDelta: number[];
    herdDelta: number[];
    velocityDelta: number;
    propagationSummaryA: object;
    propagationSummaryB: object;
  };
  ```

## 6. 测试用例

- **T1**：同数据集下两种推荐器对比可显示（页面能渲染两条曲线）。
- **T2**：差异指标存在（`velocityDelta !== 0` 或曲线明显不同）。
- **T3**：传播图快照可切换（可在推荐器 A / B 间切换）。
- **T4**：导出报告可读（Markdown / JSON 中能明确看出推荐器差异）。

## 7. 通过标准 (Gate)

- [ ] 至少支持 2 个推荐器对比
- [ ] 至少 3 类核心指标可视化对比
- [ ] 传播图快照可比较
- [ ] 差异结果非空且可解释
- [ ] 有最小导出报告

## 8. 失败标准

- 图表只是重复同一份数据
- 差异全是 0 且无合理解释
- 传播图与 run 对不上
- UI 只能看单一推荐器

## 9. 证据要求

- `artifacts/r5/r5_02_compare_panel.png`
- `artifacts/r5/r5_02_compare_result.json`
- `artifacts/r5/r5_02_report.md`

## 10. 建议提交信息

```bash
git commit -m "feat(compare): add recommender impact comparison for propagation and polarization"
```
