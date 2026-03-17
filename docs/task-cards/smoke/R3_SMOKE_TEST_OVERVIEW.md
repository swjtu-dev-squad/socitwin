# 第三轮 Smoke Test 总览

第三轮 Smoke Test 的目标，是在已修复基础链路的前提下，验证系统能否在较高 agent 数和较长步数场景下持续产生非空社会模拟行为，并在此基础上验证极化动态性与 A/B 侧 long-term sidecar 契约闭合情况，为后续更复杂的传播可视化、推荐算法与任务调度能力提供可信输入。

## 任务卡列表

| 任务卡 | 标题 | 优先级 | 状态 |
|---|---|---|---|
| [R3-01](./R3-01-high-density-behavior-smoke.md) | 高强度行为产出 Smoke Test | P0 | Ready |
| [R3-02](./R3-02-polarization-dynamics-smoke.md) | 极化动态性 Smoke Test | P0 | Ready |
| [R3-03](./R3-03-sidecar-integration-smoke.md) | Sidecar 真联调 Smoke Test | P0 | Ready |

## 建议执行顺序

1.  **R3-01 高强度行为产出**
2.  **R3-02 极化动态性**
3.  **R3-03 Sidecar 真联调**

**理由**：没有内容，极化就不容易动；没有内容，episode 也会很瘦。先把 agent 说话频率提起来，再看分析和记忆才有意义。
