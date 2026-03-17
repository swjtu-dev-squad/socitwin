# R4-01 传播可视化最小闭环 — 证据报告

| 属性 | 值 |
|---|---|
| **任务** | R4-01 Propagation Visualization |
| **状态** | PASS |
| **Gate 通过率** | 14 / 14 |
| **执行时间** | 2026-03-17 |

---

## 实现摘要

### 后端（`server.ts`）

新增三个 REST API 接口，均基于 SQLite 数据库实时计算，无硬编码假数据：

| 接口 | 功能 |
|---|---|
| `GET /api/analytics/propagation-summary` | 返回传播节点、边、指标（velocity/coverage/herdIndex） |
| `GET /api/analytics/opinion-distribution` | 基于 `polarization_cache.stance_score` 计算 Left/Center/Right 分布 |
| `GET /api/analytics/herd-index` | 基于 `trace` 表计算 HHI 趋势 |

### 前端（`src/components/PropagationGraph.tsx`）

新建 `PropagationGraph` 组件，特性：

- 基于 `react-force-graph-2d` 渲染力导向图
- 节点类型：`agent`（紫色）/ `content`（绿色）
- 边类型：`create`（靛蓝）/ `like`（琥珀）/ `follow`（翠绿）/ `reply`（蓝色）
- 支持点击节点查看详情
- 支持边类型筛选（全部/create/like/follow/reply）
- 每 15 秒自动刷新
- 顶部显示节点数、边数、覆盖率、羊群指数

### Analytics 页面（`src/pages/Analytics.tsx`）

- 传播节点分析区域从 "Coming Soon" 占位替换为 `<PropagationGraph />`
- 新增 `StatsHistoryEntry` 类型导入，修复编译错误

---

## Gate 验证结果

| Gate | 描述 | 结果 |
|---|---|---|
| propagation-summary API available | HTTP 200 | **PASS** |
| nodes > 0 | nodes=4 | **PASS** |
| metrics returned | 7 个指标字段 | **PASS** |
| PropagationGraph.tsx exists | 组件文件存在 | **PASS** |
| ForceGraph2D used | react-force-graph-2d 集成 | **PASS** |
| node click handler | 交互式节点选择 | **PASS** |
| PropagationGraph imported | Analytics 页面已导入组件 | **PASS** |
| Coming Soon removed from propagation | 占位内容已移除 | **PASS** |
| opinion-distribution API available | HTTP 200 | **PASS** |
| distribution has 3 categories | Left/Center/Right | **PASS** |
| distribution sums to ~100% | sum=100.0% | **PASS** |
| herd-index API available | HTTP 200 | **PASS** |
| current herd index returned | current=1 | **PASS** |
| TypeScript compilation passes | 无编译错误 | **PASS** |

---

## API 样例输出

### `/api/analytics/propagation-summary`

```json
{
  "nodes": [
    {"id": "agent_0", "type": "agent", "label": "agent_0"},
    {"id": "agent_1", "type": "agent", "label": "agent_1"},
    {"id": "agent_2", "type": "agent", "label": "agent_2"},
    {"id": "post_1", "type": "content", "label": "As an AI skeptic, I'm increasingly conce..."}
  ],
  "edges": [
    {"source": "agent_2", "target": "post_1", "type": "create"}
  ],
  "metrics": {
    "velocity": 1.0,
    "coverage": 0.3333,
    "herdIndex": 0.6016,
    "totalNodes": 4,
    "totalEdges": 1,
    "activeAgents": 1,
    "totalPosts": 1
  }
}
```

### `/api/analytics/opinion-distribution`

```json
{
  "distribution": [
    {"name": "Left", "value": 0, "count": 0},
    {"name": "Center", "value": 0, "count": 0},
    {"name": "Right", "value": 100, "count": 1}
  ],
  "total": 1
}
```
