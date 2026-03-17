# 任务卡：R6-02 Compare Panel 前端接入

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Frontend / Comparative Analytics / Visualization |
| **负责人** | 前端分析负责人 |
| **协作人** | 可视化负责人、实验框架负责人 |
| **关联 Issue** | #33, #24, #22, #32 |

---

## 1. 背景

R5-02 已经有了 compare 分析逻辑和图表生成能力，但如果它仍停留在脚本/报告层，用户就不能在前端直接做策略对比。
而当前 Analytics 页面在旧快照里还是偏单次运行视角，这正好说明 R6-02 要补的是“实验对比面板”。

## 2. 目标

在前端实现一个最小 Compare Panel，使用户可以：

- 选择两个实验结果或两个推荐器 run；
- 对比极化曲线；
- 对比 HerdIndex 曲线；
- 对比速度/帖子等摘要指标；
- 对比传播图快照。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| Compare Panel 页面/区域 | SHAP / Sobol 归因分析 (#31) |
| 实验 run 选择器 | 统计显著性检验 |
| 4 类核心图表 | 高级交互动画 |
| 传播图快照切换 | 跨多实验复杂矩阵比较 |
| 指标差异摘要卡 | |

## 4. 建议最小图表

- Polarization 对比折线图
- HerdIndex 对比折线图
- Velocity / totalPosts 柱状图
- PropagationGraph 快照对比
- 综合差异摘要卡

## 5. 通过标准 (Gate)

- [ ] 至少支持 2 个 run 对比
- [ ] Polarization 对比图可见
- [ ] HerdIndex 对比图可见
- [ ] Velocity/Posts 摘要对比可见
- [ ] PropagationGraph 快照可切换
- [ ] 空状态和错误状态处理正常

## 6. 证据要求

- `artifacts/r6/r6_02_compare_panel.png`
- `artifacts/r6/r6_02_compare_result.json`
- `artifacts/r6/r6_02_report.md`
