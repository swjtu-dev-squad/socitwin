# 任务卡：R2-01 多 Agent 非空产出 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Smoke Test / Behavior Validation |
| **负责人** | @后端 / @引擎负责人 |
| **协作人** | @前端联调负责人 |
| **关联 Issue** | #2, #22, #24 |

---

## 1. 背景

第一轮 Smoke Test 虽验证了主链路可运行，但已观察到“空跑”现象：`step` 很快完成，但帖子（Post）产出很弱甚至为零。第二轮必须首先验证，在更合理的智能体（Agent）数量和步数下，系统是否能真正产生帖子、互动和状态变化。Analytics 页面与三大核心指标的进一步验证，也依赖于此。若无非空行为，#22 的三幅图和 #24 的三大指标就容易沦为分析虚空。

## 2. 目标

验证系统在 3-5 个智能体、10-20 步的场景下：

*   能产生非空的帖子或互动行为；
*   不同步之间存在增量变化；
*   至少有两个以上智能体出现可区分行为；
*   `status`、`history`、`logs` 三者数据保持一致。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| 引擎 `step` 行为 | 推荐算法质量优劣 |
| `totalPosts` / `logs` / `interactions` | 传播图复杂可视化 |
| Dashboard 状态变化 | 长期记忆 Sidecar 联调 |
| 行为样本抽查 | |

## 4. 前置条件

*   已按文档设置环境变量，尤其是 `OASIS_MODEL_URL`。
*   `pnpm dev` 可正常启动。
*   第一轮 ST-05 日志重复 bug 已修复完成。

## 5. 执行步骤

**(1) 启动服务**

```bash
pnpm dev
```

**(2) 运行配置 A（中等最小验证）**

*   **Agent Count**: 3
*   **Platform**: Reddit
*   **Topic**: AI
*   连续 **Step 10 次**

**(3) 运行配置 B（更强行为触发验证）**

*   **Agent Count**: 5
*   **Platform**: Reddit
*   **Topics**: AI + politics / mixed
*   连续 **Step 20 次**

**(4) 记录以下字段**

*   `currentStep`
*   `totalPosts`
*   `activeAgents`
*   `polarization`
*   新增日志数
*   有内容的帖子样本

## 6. 通过标准 (Gate)

*   [ ] 配置 A 中 `totalPosts > 0`
*   [ ] 配置 B 中 `totalPosts` 随 `step` 有增长
*   [ ] 至少观察到 2 个不同智能体的行为记录
*   [ ] 日志内容不是完全机械重复
*   [ ] `status` / `history` / `logs` 数量关系合理
*   [ ] 无 `traceback` / 白屏 / `step` 卡死

## 7. 失败标准

*   10-20 步后依然完全无产出。
*   只有 `system-level` 空日志，无真实帖子或互动。
*   行为样本完全同质化。
*   状态和日志不一致。

## 8. 证据要求

*   `artifacts/smoke/r2_01_nonempty_behavior.md`
*   `artifacts/smoke/r2_01_steps.csv`
*   3-5 条代表性日志样本
*   页面截图与后端日志截图

## 9. 备注

这张卡是第二轮的起点。先确认系统不是在“优雅空转”，再去谈记忆压缩和图表可信性。
