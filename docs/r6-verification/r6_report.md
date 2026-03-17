# R6 实现报告

**提交时间**：2026-03-17  
**仓库**：swjtu-dev-squad/oasis-dashboard  
**验证结果**：35/35 Gate 全部通过

---

## 一、任务卡文件（已入库）

三张任务卡存放于 `docs/task-cards/r6/`：

| 文件 | 描述 |
|---|---|
| `R6-01-EXPERIMENT-RUNNER-CONSOLE.md` | 实验运行控制台：后端 API + ExperimentRunnerPanel 前端组件 |
| `R6-02-COMPARE-PANEL-FRONTEND.md` | 对比面板前端：ExperimentComparePanel + 4 类图表 |
| `R6-03-EXPERIMENT-ARCHIVE-UI.md` | 历史归档 UI：ExperimentArchiveTable + ExperimentDetailDrawer |

---

## 二、R6-01：Experiment Runner Console

### Gate 通过情况（13/13）

| Gate | 结果 |
|---|---|
| POST /api/experiments/run 返回 200 | PASS |
| success=True | PASS |
| experimentId 存在 | PASS |
| runs 包含指定推荐器数量 | PASS |
| 每个 run 包含 polarization_final | PASS |
| 每个 run 包含 herd_index_final | PASS |
| 每个 run 包含 velocity_avg | PASS |
| 每个 run 包含 total_posts | PASS |
| polarization_final 在 [0,1] | PASS |
| herd_index_final 在 [0,1] | PASS |
| GET /api/experiments/:id/result 返回 200 | PASS |
| result 包含 runs | PASS |
| 空 recommenders 返回 400 | PASS |

### 实现说明

新增后端 API 端点：
- `POST /api/experiments/run`：接收实验配置，调用 `run_experiment_helper.py`，返回完整实验结果
- `GET /api/experiments/:id/result`：读取指定实验的 `result.json`
- `GET /api/experiments`：列出所有历史实验目录

新增前端组件 `ExperimentRunnerPanel.tsx`：
- 表单配置：实验名称、推荐器多选（TikTok/小红书/Pinterest）、平台、步数、随机种子、Agent 数量
- 实时进度展示：运行中状态指示
- 结果预览：各推荐器指标对比表格

---

## 三、R6-02：Compare Panel Frontend

### Gate 通过情况（15/15）

| Gate | 结果 |
|---|---|
| GET /api/experiments 返回 200 | PASS |
| experiments 字段存在 | PASS |
| 至少有 1 个历史实验 | PASS |
| 实验包含 experimentId | PASS |
| 实验包含 recommenders | PASS |
| 实验包含 summary | PASS |
| ExperimentRunnerPanel.tsx 存在 | PASS |
| ExperimentComparePanel.tsx 存在 | PASS |
| ExperimentArchiveTable.tsx 存在 | PASS |
| ExperimentDetailDrawer.tsx 存在 | PASS |
| Experiments.tsx 页面存在 | PASS |
| App.tsx 包含 /experiments 路由 | PASS |
| DashboardLayout.tsx 包含实验控制台 | PASS |
| experimentApi.ts 存在 | PASS |
| compareApi.ts 存在 | PASS |

### 实现说明

新增前端组件 `ExperimentComparePanel.tsx`：
- 实验选择器：从历史实验列表中选择 1-3 个实验进行对比
- 4 类对比图表（基于 Recharts）：
  - 极化曲线（Polarization Trend）：多推荐器极化值随步数变化
  - 羊群指数曲线（Herd Index Trend）：多推荐器羊群效应随步数变化
  - 传播速度柱状图（Velocity Comparison）：各推荐器平均传播速度
  - 综合雷达图（Radar Chart）：极化/羊群/速度三维对比

新增 API 封装：
- `experimentApi.ts`：实验运行、结果查询接口
- `compareApi.ts`：对比分析接口

---

## 四、R6-03：Experiment Archive UI

### Gate 通过情况（7/7）

| Gate | 结果 |
|---|---|
| artifacts/experiments 目录存在 | PASS |
| 至少 2 个实验目录 | PASS（6 个） |
| 至少 2 个实验有完整 result.json + config.json | PASS（3 个） |
| result.json 包含 stepsTrace | PASS |
| stepsTrace 非空 | PASS（15 步） |
| 前端构建产物 dist/ 存在 | PASS |
| dist/index.html 存在 | PASS |

### 实现说明

新增前端组件：
- `ExperimentArchiveTable.tsx`：历史实验列表，支持排序、筛选、分页
- `ExperimentDetailDrawer.tsx`：实验详情侧边抽屉，展示完整指标和步骤轨迹

新增页面 `Experiments.tsx`：三个 Tab 整合 R6-01/02/03 全部功能：
- Tab 1：运行实验（ExperimentRunnerPanel）
- Tab 2：对比分析（ExperimentComparePanel）
- Tab 3：历史归档（ExperimentArchiveTable + ExperimentDetailDrawer）

导航集成：`DashboardLayout.tsx` 新增"实验控制台"菜单项（FlaskConical 图标）

---

## 五、新增文件清单

### 后端
- `oasis_dashboard/run_experiment_helper.py`（实验运行辅助脚本）
- `server.ts`（新增 3 个 R6 API 端点）

### 前端
- `src/components/ExperimentRunnerPanel.tsx`
- `src/components/ExperimentComparePanel.tsx`
- `src/components/ExperimentArchiveTable.tsx`
- `src/components/ExperimentDetailDrawer.tsx`
- `src/pages/Experiments.tsx`
- `src/lib/experimentApi.ts`
- `src/lib/compareApi.ts`
- `src/lib/experimentArchiveApi.ts`

### 验证
- `artifacts/r6/verify_r6_all.py`（综合验证脚本）
- `artifacts/r6/r6_verify_result.json`（验证结果 JSON）
