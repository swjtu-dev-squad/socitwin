# 任务卡：R3-01 高强度行为产出 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Smoke Test / Behavior Density Validation |
| **负责人** | @引擎负责人 |
| **协作人** | @前端联调负责人 |
| **关联 Issue** | #2, #22, #24 |

---

## 1. 背景

R2 已经确认 LLM 调用链路能通，但 5 步仅 1 帖的产出密度太低，导致极化值、传播速度、羊群指数很难真正“动起来”。当前主问题不再是系统能不能运行，而是 agent 会不会持续产出足够多的新内容供后续分析使用。

`context_smoke.py` 现已支持自定义 agent 数和步数，因此可以直接作为这一轮高强度行为验证的基础入口。

## 2. 目标

在更高配置下验证：

- agent 会持续产出新帖子或互动；
- 行为不是只集中在 step 1；
- 至少多个 agent 有可区分输出；
- 为 R3-02 和 R3-03 提供足够的输入数据。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| 多 agent 行为产出 | 推荐算法优劣 |
| `totalPosts` 增长 | 图表视觉效果优化 |
| `new_logs` 连续性 | long-term recall 质量 |
| 行为样本抽查 | |
| step 时间统计 | |

## 4. 前置条件

- `pnpm dev` 可正常启动。
- Python 子进程环境变量已正确注入。
- ST-05 日志重复修复未回归。
- `totalPosts` 计数链路已修复。

## 5. 测试配置

### 配置 A（基础放大）

- **agents**: 10
- **steps**: 20
- **platform**: reddit
- **topic**: AI
- **recsys**: hot-score

### 配置 B（多主题刺激）

- **agents**: 10
- **steps**: 20
- **platform**: reddit
- **topics**: AI politics
- **recsys**: hot-score

## 6. 执行步骤

**(1) CLI 跑配置 A**

```bash
.venv/bin/python -m oasis_dashboard.context_smoke \
  --agent-count 10 \
  --steps 20 \
  --platform reddit \
  --topic AI \
  --json > artifacts/smoke/r3_01_output_a.json
```

**(2) CLI 跑配置 B**

```bash
.venv/bin/python -m oasis_dashboard.context_smoke \
  --agent-count 10 \
  --steps 20 \
  --platform reddit \
  --topics "AI politics" \
  --json > artifacts/smoke/r3_01_output_b.json
```

**(3) Dashboard 手动抽查**

在 UI 中查看：

- `Current Step` 是否递增
- `totalPosts` 是否增长
- `Logs` 是否持续新增
- 不同 agent 是否有不同内容样本

**(4) 记录每步字段**

- `currentStep`
- `totalPosts`
- `step_time`
- `new_logs_count`
- `unique_agent_count`
- `representative_post_samples`

## 7. 通过标准 (Gate)

- [ ] 20 步内 `totalPosts` >= 5
- [ ] 至少 3 个不同 agent 有行为记录
- [ ] step 2~20 中不止一轮有新增日志
- [ ] 日志内容不是完全机械重复
- [ ] 无 traceback / 400 / 401 / 模型路由错误
- [ ] `status` / `logs` / `totalPosts` 相互一致

## 8. 失败标准

- 20 步后仍接近空跑
- 只有 step 1 有内容，后续长时间沉默
- 只有单个 agent 有输出
- `totalPosts` 与真实日志样本不一致

## 9. 证据要求

- `artifacts/smoke/r3_01_output.json`
- `artifacts/smoke/r3_01_behavior_report.md`
- `artifacts/smoke/r3_01_steps.csv`
- 至少 5 条代表性内容样本

## 10. 备注

这张卡的目标非常朴素：先把“内容量”打出来。
没有足够帖子和互动，后面的极化和 long-term 都是在分析寂静。
