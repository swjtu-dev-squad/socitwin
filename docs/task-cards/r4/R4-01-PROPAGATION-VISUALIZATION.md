# 任务卡：R4-01 传播可视化最小闭环

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Visualization / Backend-Frontend Integration |
| **负责人** | 可视化负责人 |
| **协作人** | 后端负责人、前端状态管理负责人 |
| **关联 Issue** | #33, #22, #24 |

---

## 1. 背景

Issue #33 要求实现传播分析的核心功能，包括 propagation 数据结构、SQLite 查询、传播图组件、观点分布与 HerdIndex 计算，以及前端图表接入。技术栈已指定为 Node.js + Express + SQLite、React + TypeScript、Recharts 和 react-force-graph-2d。

当前 Analytics 页面已经有观点分布图的 UI 框架和“传播节点分析”卡片，但传播分析区域仍是占位状态，说明 UI 落点已存在，缺的是后端数据和图组件本体。

## 2. 目标

构建一个最小但真实的传播可视化闭环，使系统能从现有日志/行为数据中生成：

- 传播节点与边
- 传播速度等基础指标
- 观点分布
- HerdIndex 趋势
- 前端可交互的最小传播图

## 3. 范围

### In Scope

- `propagation` 数据结构
- SQLite 查询与聚合
- `PropagationGraph` 组件
- `SimulationStore` 扩展
- Analytics 页面接入：
  - `propagationData`
  - `propagationMetrics`
  - `opinionDistribution`
  - `herdIndex`

### Out of Scope

- 完整因果传播恢复
- 时间轴高级动画
- 大规模图性能优化
- 复杂社区检测算法

## 4. 当前问题

系统虽已打通行为产出和 sidecar，但缺少一条“把行为看见”的主线。许多数据能生成，却无法可视化，特别是传播节点分析区域仍未落地。

## 5. 修复/实现方案

### 5.1 后端：`propagation` 最小数据模型

最小版本可基于现有 `trace` / `post` / `interaction` 数据派生，统一输出：

```typescript
type PropagationNode = {
  id: string;
  type: "agent" | "content";
  label: string;
  step?: number;
  opinionBucket?: string;
};

type PropagationEdge = {
  source: string;
  target: string;
  type: "create" | "like" | "follow" | "reply";
  step: number;
};

type PropagationMetrics = {
  velocity: number;
  coverage: number;
  conversionRate?: number;
  herdIndex: number;
};
```

### 5.2 后端：查询接口

新增最小接口，可合并为一个 summary 接口：

- `GET /api/analytics/propagation`
- `GET /api/analytics/opinion-distribution`
- `GET /api/analytics/herd-index`
- **(可选合并)** `GET /api/analytics/propagation-summary`

### 5.3 前端：`PropagationGraph` 最小组件

基于 `react-force-graph-2d`，支持：

- 节点类型：`agent` / `content`
- 边类型：`create` / `like` / `follow` / `reply`
- 点击节点查看详情
- 缩放/拖拽
- `step` 范围筛选（slider 或 dropdown）

### 5.4 OpinionDistribution 与 HerdIndex

- **OpinionDistribution**: Left / Center / Right 三分法
- **HerdIndex**: 行为集中度（HHI 或同步率近似）

## 6. 具体子任务

1. 在后端补全 `propagation` 查询和 `metrics` 计算。
2. 扩展 `SimulationStore`，加入 `propagationData` 和 `propagationMetrics`。
3. 新建 `PropagationGraph.tsx`。
4. 在 Analytics 页面将“传播节点分析”占位区替换为真实图表。
5. 激活 `HerdIndex` 指标卡与趋势图。

## 7. 测试用例

- **T1**: 非空行为下 `propagation` 接口返回非空数据（节点数 > 0, 边数 > 0, metrics 可计算）。
- **T2**: `PropagationGraph` 能正常渲染（页面不报错, 节点/边可见, 支持点击与缩放）。
- **T3**: `OpinionDistribution` 有真实值（数据非全 0, 与模拟结果可追溯）。
- **T4**: `HerdIndex` 趋势可更新（非空场景下随 step 变化, 非恒定值）。

## 8. 通过标准 (Gate)

- [ ] `propagation` 查询接口可用
- [ ] `PropagationGraph` 可渲染真实数据
- [ ] Analytics 中传播节点分析不再是占位
- [ ] `OpinionDistribution` 图表由真实数据驱动
- [ ] `HerdIndex` 卡片与趋势图被激活
- [ ] 非空行为场景下页面无报错

## 9. 失败标准

- 传播图仍为占位
- `propagationData` 为空或无法追溯
- `OpinionDistribution` / `HerdIndex` 仍为假数据
- 页面渲染异常或性能崩溃

## 10. 证据要求

- `artifacts/r4/r4_01_propagation_graph.png`
- `artifacts/r4/r4_01_metrics.json`
- `artifacts/r4/r4_01_report.md`
- 一份 API 样例输出

## 11. 建议提交信息

```bash
git commit -m "feat(analytics): add minimal propagation visualization pipeline"
```
