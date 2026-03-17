# 任务卡：R6-01 Experiment Runner 前端控制台

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Frontend / Experiment Control / API Integration |
| **负责人** | 前端负责人 |
| **协作人** | 后端实验框架负责人、数据导入负责人 |
| **关联 Issue** | #30, #32, #34 |

---

## 1. 背景

R5-01 已经把“数据集 × 推荐策略 × 固定 seed × 指标输出”做成了实验管线，但它更偏脚本/后端能力。R6 的第一步，就是把这条能力接成前端控制台，让用户不用靠命令行或脚本，就能发起一次规范实验。

这也与 #30 “任务创建—执行—监控最小闭环”的方向一致。虽然 #30 的范围更大，但 R6-01 可以先把“实验运行”这条最小任务流前端化。

## 2. 目标

提供一个最小前端实验控制台，使用户可以：

- 选择导入数据集；
- 选择 2~3 个推荐器；
- 设置 steps / seed / platform；
- 点击运行实验；
- 查看运行状态与结果摘要。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| Experiment Runner 页面 | 批量任务并行调度 |
| 数据集下拉选择 | 复杂权限系统 |
| 推荐器多选 | 多用户协作控制 |
| steps / seed / platform 表单 | 完整任务失败恢复 |
| 运行按钮与 loading 状态 | |
| 实验结果摘要卡片 | |

## 4. 建议最小 API

- `POST /api/experiments/run`
- `GET /api/experiments/:id/result`

## 5. 建议页面布局

- **左侧**：配置表单
- **右侧**：最近一次运行结果摘要

摘要至少显示：`experimentId`, `dataset`, `recommenders`, `totalPosts`, `polarization_final`, `herdIndex_final`, `velocity_avg`。

## 6. 通过标准 (Gate)

- [ ] `/experiments` 页面可访问
- [ ] 可选择数据集并发起实验
- [ ] 可选择至少 2 个推荐器
- [ ] 可设置 steps / seed / platform
- [ ] 返回结果摘要可显示
- [ ] 错误状态有提示

## 7. 证据要求

- `artifacts/r6/r6_01_runner_page.png`
- `artifacts/r6/r6_01_run_result.json`
- `artifacts/r6/r6_01_report.md`
