# Social Network Monitor Migration Plan

- Status: backend-first-wave-complete
- Audience: migration implementers, reviewers, frontend/backend maintainers
- Scope: migrate useful social network monitor page capabilities from `oasis-dashboard` into `socitwin`

## 1. Purpose

本页记录旧仓库社交网络监控页迁入新仓库的具体规划。

这次迁移的目标不是覆盖新仓库现有页面，而是：

1. 以旧仓库页面作为功能参考；
2. 保留新仓库已经更合理的前端结构和视觉能力；
3. 把旧页面中已经完成且对组会展示、调试和运行观察有价值的功能补入新仓库；
4. 按新仓库 FastAPI + service + memory debug 架构重新设计数据接口；
5. 不为了页面展示而贸然重开记忆主链语义。

## 2. Current Code Facts

### 2.1 Old repository route

旧仓库当前分支：

- `/home/grayg/oasis-dashboard`
- `feature/oasis-memory-ltm`

旧页面主链：

```text
frontend /agents
  -> GET /api/agents/monitor
  -> Node server.ts
  -> Python OASIS runtime snapshot + SQLite
  -> frontend AgentMonitorResponse
```

相关旧文件：

- `src/pages/Agents.tsx`
- `src/components/AgentDeepMonitor.tsx`
- `src/components/AgentBehaviorTable.tsx`
- `src/components/ForceGraph.tsx`
- `src/lib/agentMonitorApi.ts`
- `src/lib/agentMonitorTypes.ts`
- `src/lib/agentMemoryDisplay.ts`
- `server.ts`
- `oasis_dashboard/real_oasis_engine_v3.py`
- `docs/social_network_monitor/DEVELOPMENT_RECORD.md`
- `docs/social_network_monitor/add_memory/AGENT_MEMORY_INCREMENTAL_DELIVERY_GUIDE.md`
- `docs/social_network_monitor/vector_longterm_memory/DELIVERY.md`

旧页面已经完成的关键能力：

- 真实 monitor/detail 接口；
- Python 运行态 snapshot；
- SQLite 聚合；
- 图谱节点和关系边；
- agent 行为列表；
- 右侧 agent 详情；
- 最近轨迹；
- 最近看到的帖子；
- 动作文案格式化；
- 长期记忆和 retrieval 区块展示；
- step 后通过 `agents_dirty` socket 事件刷新。

### 2.2 New repository route

新仓库当前分支：

- `/home/grayg/socitwin`
- `feature/oasis-memory-migration-plan`

迁移前，新页面主链是：

```text
frontend /agents
  -> GET /api/sim/status
  -> frontend transformToMonitorResponse()
  -> page render

frontend selected agent
  -> GET /api/sim/agents/{agent_id}
  -> frontend transformToAgentDetail()
  -> detail render
```

相关新文件：

- `frontend/src/pages/Agents.tsx`
- `frontend/src/components/AgentDeepMonitor.tsx`
- `frontend/src/components/AgentBehaviorTable.tsx`
- `frontend/src/components/ForceGraph.tsx`
- `frontend/src/lib/agentMonitorApi.ts`
- `frontend/src/lib/agentMonitorTypes.ts`
- `frontend/src/lib/agentDataTransform.ts`
- `frontend/src/lib/agentMemoryDisplay.ts`
- `backend/app/api/simulation.py`
- `backend/app/services/simulation_service.py`
- `backend/app/core/oasis_manager.py`
- `backend/app/memory/agent.py`

新仓库当前已经有：

- `/api/sim/status`
- `/api/sim/agents`
- `/api/sim/agents/{agent_id}`
- `/api/sim/memory`
- `/api/sim/agents/monitor`
- `/api/sim/agents/{agent_id}/monitor`

其中 `/api/sim/memory` 已经能暴露 `action_v1` 的 memory debug 摘要：

- mode；
- context / generation budget；
- recent retained summary；
- compressed retained summary；
- observation shaping stage；
- prompt tokens；
- recall gate；
- recalled / injected counts；
- recalled / injected step ids；
- recall query；
- runtime failure；
- selected recent / compressed / recall ids。

注意：monitor 页第一版读取的是 memory debug summary，不是完整的 recent /
compressed / recall 渲染正文。它用于判断各层是否参与、占用和选入情况；
如果后续要展示每个 recent segment 或 compressed block 的完整文本，需要
在 memory snapshot 中新增更重的、可分页或可折叠的 detail 字段。

当前第一轮 monitor 迁移已经新增：

- `backend/app/models/agent_monitor.py`
- `backend/app/services/agent_monitor_service.py`
- `backend/tests/memory/integration/test_agent_monitor_api.py`

新页面当前主链已经调整为：

```text
frontend /agents
  -> GET /api/sim/agents/monitor
  -> page render

frontend selected agent
  -> GET /api/sim/agents/{agent_id}/monitor
  -> detail render
```

当前应把这条线理解为：

- monitor/detail 的后端第一版已经完成；
- 它已经不再是 memory 主链迁移的阻塞项；
- 后续剩余工作主要是展示增强、真实长跑验证和非阻塞清理。

## 3. Migration Position

### 3.1 What this is

这是一次页面功能迁移和接口对齐：

- 旧页面提供功能参考；
- 新页面保留现有更合理的 UI 基础；
- 新后端按 FastAPI service 架构提供 monitor/detail 聚合接口；
- 记忆展示按 `action_v1` 当前真实 debug 数据重新解释。

### 3.2 What this is not

这不是：

- 直接用旧页面覆盖新页面；
- 直接迁移旧 Node `server.ts`；
- 直接复活旧 Qdrant memory monitor 合同；
- 为页面展示重构 long-term / recall 主链；
- 把 memory 内部状态继续塞进 `/api/sim/status`。

## 4. Page Capability Target

### 4.1 Keep from new page

新页面已有且应保留的部分：

- 当前整体布局；
- 顶部传播规模 / 深度 / 广度 / 从众效应展示；
- `safeDisplay` 数值格式化；
- 新版 `ForceGraph` 的活跃度热力图；
- 新版 `ForceGraph` 的 hover 指标；
- Vite + React 当前组件结构。

### 4.2 Bring from old page

旧页面中应迁入的能力：

- 专用 monitor/detail 数据合同；
- 表格中的 memory / recall 摘要；
- 右侧详情中的长期记忆 / recall 区块；
- 更完整的 profile 属性展示；
- 最近动作；
- 最近轨迹；
- 最近看到的帖子；
- 动作文案格式化；
- graph interaction edges；
- step 后刷新机制。

### 4.3 Reinterpret for action_v1

这些旧展示项可以保留页面位置，但字段语义必须按新记忆路线重新解释：

- `memory.length`
  - 旧语义偏向 `system prompt token + retrieval token`；
  - 新语义更适合显示 `last_prompt_tokens` 或 memory retained summary。
- `memory.contentSource`
  - 旧语义是 `system_prompt | retrieval`；
  - 新语义不应强行套旧二分，必要时可在 UI 上显示 `action_v1 recall/debug`。
- `retrieval.content`
  - 旧语义是被注入 prompt 的长期记忆文本；
  - 新仓库当前 `/api/sim/memory` 只保证 recall query、reason trace、step ids 和 counts；
  - 若要显示召回正文，需要后端新增 per-agent recall item summaries。
- `retrieval.items`
  - 旧语义是 Qdrant retrieval item；
  - 新语义应对应 recalled / injected episodes，至少包含 step id、score/source/content summary。

## 5. Display Requirements

### 5.1 Monitor overview

页面首屏应展示：

| UI 区块 | 展示内容 | 当前新仓库状态 | 迁移处理 |
|---|---|---|---|
| 顶部状态 | platform, topic, polarization, propagation, herd index | 部分已有 | 保留并补 topic/recsys |
| 图谱节点 | agent id/name/influence/activity/status | 已有 | 保留 |
| 图谱边 | follow + interaction | follow 不完整，interaction 缺失 | 后端聚合生成 |
| 行为表 | agent, influence, activity, last action, memory summary | 基础已有，memory 缺失 | 补后端字段和旧摘要逻辑 |
| 选中详情 | profile, status, action, timeline, seen posts, memory | 详情偏基础 | 补完整 detail contract |

### 5.2 Agent detail

右侧详情建议展示：

| 区块 | 展示内容 | 数据来源 |
|---|---|---|
| 基本信息 | name, user_name, role/persona, bio, tags | agent profile / config / DB |
| 社交指标 | influence, activity, follow/follower, interaction | SQLite + service 聚合 |
| 最新动作 | action type, readable content, reason/time | trace + formatter |
| 最近轨迹 | recent trace timeline | SQLite trace |
| 最近看到的帖子 | rec table 或 runtime seen posts | SQLite rec/post/user 或 runtime snapshot |
| 记忆状态 | memory mode, prompt tokens, recent/compressed retained | `/api/sim/memory` |
| 长期召回 | recall gate, query, recalled/injected count, step ids, status | `/api/sim/memory` |
| 召回条目 | optional content summaries | 需要新增后端字段 |
| 本轮 prompt 构成 | selected recent ids, selected compressed keys, selected recall ids | `/api/sim/memory` |

### 5.3 Memory display states

前端应明确区分：

| 状态 | 显示含义 |
|---|---|
| `not_configured` | 当前模式不支持长期记忆，或 long-term backend 未启用 |
| `ready` | 最近一次 recall 有 recalled 或 injected 结果 |
| `empty` | recall gate / retrieval 被触发，但没有可用召回 |
| `error` | memory runtime failure 或 retrieval backend failure |
| `idle` 或空态 | 尚未执行到足以产生 memory debug 的阶段 |

如继续沿用旧类型 `AgentMemoryRetrievalStatus = "not_configured" | "ready" | "empty" | "error"`，则 `idle` 可以先映射成 `not_configured` 加中文说明，避免马上扩展前端类型。

## 6. Backend Contract Plan

### 6.1 Recommended endpoints

当前已新增：

```text
GET /api/sim/agents/monitor
GET /api/sim/agents/{agent_id}/monitor
```

原因：

- 保持新仓库 API 前缀一致；
- 不污染 `/api/sim/status`；
- 让前端不用继续通过 `agentDataTransform.ts` 做复杂推断；
- 便于后续把 monitor 页面和 memory debug 页面分离。

### 6.2 Service boundary

当前已新增：

```text
backend/app/services/agent_monitor_service.py
```

这比放进 `SimulationService` 更干净，因为 monitor 不是单纯 simulation lifecycle，而是页面级聚合视图。

职责：

- 调用 `SimulationService.get_status()` 或直接使用 `OASISManager`；
- 读取 SQLite；
- 读取 `OASISManager.get_memory_debug_info()`；
- 生成 graph nodes/edges；
- 格式化 action content；
- 生成 memory/retrieval display snapshot；
- 输出 frontend-ready contract。

### 6.3 Data sources

| 数据 | 首选来源 | 备用来源 |
|---|---|---|
| agent 基础信息 | OASIS runtime agent.user_info | SQLite user |
| follow/follower | SQLite follow | status.agents.following |
| recent actions | SQLite trace | runtime snapshot |
| recent posts | SQLite post | 空态 |
| seen posts | SQLite rec + post + user | runtime observation snapshot |
| graph follow edges | SQLite follow | status following |
| graph interaction edges | SQLite like/comment/post | trace fallback |
| memory status | `OASISManager.get_memory_debug_info()` | empty snapshot |
| recall item content | `memory_debug.last_recall_candidate_items / last_selected_recall_items` | future richer per-agent snapshot |

## 7. Frontend Contract Plan

### 7.1 Types

`frontend/src/lib/agentMonitorTypes.ts` 应补齐：

- `retrieval.length: number`
- optional action_v1 memory debug fields，或新增更明确的 `memoryDebug` 子字段。

短期兼容方案：

- 保留旧 `AgentMemorySnapshot`；
- 在后端把 action_v1 debug 归一化成旧 UI 可读形状；
- 新增字段只作为扩展，不破坏现有组件。

长期更清晰方案：

```ts
interface AgentMemorySnapshot {
  length: number;
  content: string;
  contentSource: "system_prompt" | "retrieval" | "action_v1";
  systemPrompt: { length: number; content: string };
  retrieval: {
    length: number;
    enabled: boolean;
    status: AgentMemoryRetrievalStatus;
    content: string;
    items: AgentMemoryRetrievalItem[];
  };
  debug?: {
    memoryMode: string;
    recentRetainedStepIds: number[];
    compressedRetainedStepCount: number;
    lastPromptTokens: number;
    lastRecallGate: boolean | null;
    lastRecallQueryText: string;
    lastRecallReasonTrace: string;
    lastRecalledStepIds: number[];
    lastInjectedStepIds: number[];
    lastRuntimeFailureCategory: string;
  };
}
```

### 7.2 API client

`frontend/src/lib/agentMonitorApi.ts` 当前已改为调用专用 monitor 接口：

```text
GET /api/sim/agents/monitor
GET /api/sim/agents/{agent_id}/monitor
```

`agentDataTransform.ts` 当前仍保留，主要避免一次性删除旧兼容转换造成额外风险。

### 7.3 Components

建议处理方式：

- `Agents.tsx`
  - 保留现有布局；
  - 接新 monitor API；
  - 恢复选择切换时的 detail loading 清理，避免旧 detail 闪烁。
- `AgentBehaviorTable.tsx`
  - 保留新 safe display；
  - 迁回旧的 retrieval-aware memory summary。
- `AgentDeepMonitor.tsx`
  - 保留新 profile 基础区块；
  - 加回旧的长期记忆/召回区块；
  - 文案改成 action_v1 语义。
- `ForceGraph.tsx`
  - 保留新图谱；
  - 只确保输入 edges 更完整。

## 8. Refresh Strategy

旧仓库靠 Socket.IO：

```text
POST /api/sim/step
  -> io.emit("agents_dirty")
  -> frontend reload monitor/detail
```

新仓库当前前端仍监听 `agents_dirty`，但 FastAPI 后端没有对应 Socket.IO emit。

第一版可选路线：

1. 简单轮询；
2. step API 成功后前端主动刷新；
3. 后续再接 WebSocket/SSE。

当前第一轮落地：

- 前端继续监听旧 `agents_dirty`；
- 同时新增 5 秒轻量轮询作为 FastAPI 后端未发 socket 事件时的兜底；
- 不为了一个页面立刻引入完整 Socket.IO 服务；
- 如果后续主前端需要全局实时事件，再统一设计 WebSocket/SSE。

## 9. Implementation Phases

### Phase A: Freeze UI/data contract

任务：

- 固定 `AgentMonitorResponse` 和 `AgentDetailResponse`；
- 固定 action_v1 memory display mapping；
- 确认哪些字段暂时显示 step ids，哪些后续补正文。

验收：

- 文档有字段级数据来源；
- 不需要读旧 `server.ts` 才知道页面要什么。

状态：已完成第一版。

### Phase B: Backend monitor aggregation

任务：

- 新增 monitor service；
- 新增 `/api/sim/agents/monitor`；
- 新增 `/api/sim/agents/{agent_id}/monitor`；
- 聚合 status、SQLite、memory debug；
- 生成 graph edges；
- 生成 readable action content；
- 生成 memory snapshot。

验收：

- 无前端也能 curl 拿到完整页面数据；
- upstream 下 memory 显示合理空态；
- action_v1 下 memory 显示 recall/debug 摘要。

状态：已完成第一版，已加 integration test。

### Phase C: Frontend wiring

任务：

- API client 改接新接口；
- 移除或降级 `agentDataTransform.ts` 复杂推断；
- 表格补 memory summary；
- 详情补 memory / recall 区块；
- 保留新 ForceGraph。

验收：

- 页面加载真实 agent；
- 点击图谱/表格切换 detail；
- memory 区块不再长期为空；
- 没有 TypeScript build 错误。

状态：已完成第一版，已通过 frontend build。

### Phase D: Refresh and verification

任务：

- 选择短期刷新策略；
- 增加最小 API test；
- 增加最小页面数据 contract test；
- 真实 step 后验证 monitor 数据变化。

验收：

- step 后页面数据可刷新；
- graph edge 数随互动变化；
- recent timeline 随 trace 更新；
- action_v1 memory debug 随 step 更新。

状态：后端第一版已完成。当前采用 SSE/轮询混合刷新兜底，真实 step 长跑验证待后续进行。

## 10. Open Questions

当前需要后续实现时边做边核对的问题：

1. 是否需要后端继续暴露比当前 recall item summaries 更完整的 episode 正文；
2. `memory.length` 当前在 monitor 中使用 `last_prompt_tokens`，UI 第一版显示为 `Prompt Tokens`；
3. `contentSource` 第一版仍保持旧类型 `system_prompt | retrieval`，没有扩展 `action_v1`；
4. `currentViewpoint` 是否保留旧启发式推断，还是暂时删除；
5. 刷新机制第一版已采用 `agents_dirty` listener + 5 秒轮询兜底；
6. `agentDataTransform.ts` 第一版暂时保留，后续确认无引用后再清理。

## 12. Current Implementation Notes

第一轮已经落地：

- 后端新增 monitor response model；
- 后端新增 `AgentMonitorService`；
- 后端新增 `/api/sim/agents/monitor`；
- 后端新增 `/api/sim/agents/{agent_id}/monitor`；
- monitor 聚合 `SimulationStatus`、SQLite 与 memory debug；
- memory debug 覆盖 recent retained、compressed retained、recall 和本轮 selected recent/compressed/recall；
- graph edges 支持 follow、like、comment 形成的 interaction；
- action content 在后端格式化为可读文案；
- 前端 API client 改接专用 monitor 接口；
- 行为表恢复角色列和 retrieval-aware memory summary；
- 右侧详情新增“记忆与召回”区块；
- 保留新版 ForceGraph；
- 前端增加轮询兜底；
- 新增 monitor API integration test。

当前仍未解决：

- recall item content 当前已经能显示 candidate/selected recall item summary，但还不是真实 episode 全正文；
- recent / compressed 当前展示的是 count、ids、keys，不展示完整块正文；
- `currentViewpoint` 仍是轻量启发式，后续可按需要确认是否保留；
- `agentDataTransform.ts` 仍保留为兼容残留，后续可清理；
- 尚未跑真实浏览器页面和真实 step 长跑，只完成 API contract test 与 frontend build。

## 11. Guardrails

实施时必须遵守：

- 不覆盖新页面；
- 不迁旧 Node server；
- 不把旧 Qdrant monitor 合同当成新 memory 事实；
- 不为了页面展示改写 recall 算法；
- 不把 memory debug 大量塞回 `/api/sim/status`；
- 页面上缺数据时先补 monitor/debug 输出，只有确认 memory 模块没有保存必要事实时，才考虑补 memory snapshot；
- 所有新增字段必须能解释其数据来源和语义。
