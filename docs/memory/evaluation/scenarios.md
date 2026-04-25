# Long-Term Memory Evaluation Scenarios

- Status: draft scenario plan
- Audience: implementers, evaluators
- Doc role: define data construction and scenario groups for long-term memory evaluation

## 1. Data Construction

当前建议保留三类数据来源。

更完整的数据集和可靠性设计见：

- [dataset-and-reliability.md](./dataset-and-reliability.md)

### 1.1 Real-Run Episode Replay

流程：

1. 真实运行一段 `action_v1` simulation。
2. 从 long-term store 中抽取真实 `ActionEpisode`。
3. 为 episode 构造 probe query / probe snapshot。
4. 回查当前 recall / retrieval 路径。
5. 统计 exact episode hit、MRR、cross-agent contamination。

优点：

- 最接近真实系统；
- 能覆盖真实 episode 构造质量；
- 可复用现有 `real-scenarios`。

缺点：

- 受主模型随机性影响；
- episode 分布不可完全控制；
- 不适合作为唯一回归集。

当前代码里的 `real-scenarios` 属于这一层的雏形，但还不是完整的固定 scenario pack benchmark。

### 1.2 Controlled Episode Benchmark

流程：

1. 人工构造 20 到 50 个 `ActionEpisode` payload。
2. 覆盖 post、comment、follow、group message 等核心动作。
3. 每个 episode 配 1 到 3 个 probe query。
4. 直接写入 long-term store 后执行 retrieval benchmark。

优点：

- 可复现；
- 适合比较 embedding / rerank 调整；
- 适合 CI 或轻量回归。

约束：

- 必须使用当前真实 `ActionEpisode` payload 结构；
- 不能引入当前系统不存在的理想字段；
- 不能替代真实 simulation，只能作为稳定回归补充。

这里应优先包含：

- same-agent near-duplicate hard negatives；
- cross-agent similar-topic guardrail cases；
- negative probes；
- invalid / non-persistable 边界。

### 1.3 Behavioral Scenario Runs

流程：

1. 固定 topic、agent config、step count 和 memory mode。
2. 同一场景重复运行多次。
3. 记录 recall 是否注入、行为是否连续、是否出现矛盾或自我记忆错乱。
4. 报告均值、波动和失败样本。

约束：

- 不应把单次行为结果作为长期记忆能力结论；
- 第一阶段只做观察和后续设计，不作为硬门槛。

## 2. Existing High-Priority Scenarios

第一阶段优先复用这些已有场景：

| Scenario | Purpose | First-phase use |
| --- | --- | --- |
| `VAL-LTM-01` | persistable / non-persistable 边界 | 检查无效 episode 不污染长期层 |
| `VAL-LTM-05` | 真实自我行为写入与可检索性 | 主 retrieval KPI 来源 |
| `VAL-RCL-08` | 真实行为连续性 recall probe | 检查 gate + retrieval |
| `VAL-RCL-09` | 空 observation recall suppression | 检查 false trigger |
| `VAL-RCL-10` | 长窗口真实 recall 注入 | 检查 injected trace |

这些是当前代码里已经存在的事实场景，不等于 B 级目标设计已经实现为固定 scenario packs。

## 2.1 B-Level Evolution

当前更稳妥的路线是：

- `B-level v0`
  - 继续复用现有 `real-scenarios / real-longwindow`；
  - 补固定输入、usable probe 统计、validity gate。
- `B-level v1`
  - 再引入固定 scenario packs 和多次运行聚合。

当前 `B-level v0` 已有两个固定输入 pack：

- `s1_stable_single_topic`
  - 来源：脱敏改写后的 `Singapore's Elite Leader Path vs UK's Political Rise`；
  - 目标：稳定产生 post/comment 类 `ActionEpisode`；
  - 重点指标：persisted episode count、usable probe count、Hit@1、Hit@3、MRR。
- `s2_similar_topic_interference`
  - 来源：脱敏改写后的 `Ben Judah Proposes Anglo-Gaullist Overhaul for Britain`；
  - 目标：保留同主题、相似表达、不同 agent 的结构；
  - 重点指标：Hit@1、Hit@3、MRR、cross-agent contamination。

运行入口示例：

```bash
uv run python -m app.memory.evaluation_harness \
  --phase real-scenarios \
  --scenario-pack s1_stable_single_topic \
  --scenario-steps 10
```

```bash
uv run python -m app.memory.evaluation_harness \
  --phase real-scenarios \
  --scenario-pack s2_similar_topic_interference \
  --scenario-steps 12
```

如果不传 `--scenario-pack`，`real-scenarios` 保持旧的 template agent 行为，避免破坏已有调试入口。

## 3. New Scenario Candidates

下面这些适合后续补充，不建议第一轮全部实现。

### 3.1 Self-Authored Continuity

验证 agent 是否能延续“我之前发过/评论过”的历史事实。

关注：

- self-memory consistency；
- exact episode hit；
- injection；
- 行为是否避免把自己的内容当成陌生人的内容。

### 3.2 Target Continuity

验证 agent 后续再次遇到同一 post / comment thread 时，是否能正确关联历史目标对象。

关注：

- target resolution continuity；
- contradiction rate；
- target episode injection。

### 3.3 Group Context Continuity

验证加入群组、群消息、群组语境是否能形成连续记忆。

关注：

- group-context continuity；
- group message retrieval；
- cross-agent contamination。

### 3.4 Invalid Action Pollution

验证 invalid target、hallucinated action、失败 tool result 不会污染长期层。

关注：

- invalid persist rate；
- false recall trigger；
- contradiction rate。

### 3.5 Multi-Action Step Pairing

当前 `ActionEpisode.outcome` 仍可能带有 step-level 语义。

该场景用于检查一步多动作时：

- action result 是否与 episode 正确配对；
- recall 是否把 step-level outcome 误当成单动作 outcome；
- 多动作场景下的 ground truth 是否仍能准确定位。

### 3.6 Cross-Agent Similar Topic

多个 agent 在同主题下发表相似内容，检查检索是否把别人的历史召回成自己的历史。

当前正常 recall 路径已经按 `agent_id` 过滤长期记忆，因此这个场景主要用于验证过滤边界不会回归，而不是验证常态 rerank 质量。

关注：

- cross-agent contamination rate；
- same-agent top-k ratio；
- exact episode hit。

同时需要补 same-agent near-duplicate cases；否则无法充分测试“候选能否区分相似但不同的历史事件”。

## 4. Scenario Priority

第一阶段优先级：

1. 真实 episode exact hit。
2. agent filter guardrail / cross-agent contamination regression。
3. 空 observation false trigger。
4. 长窗口 injected trace。
5. persistable / invalid persist 边界。

如果进入 B 级 v1，建议按下面三个 pack 扩展：

- `S1 stable single-topic pack`
- `S2 similar-topic interference pack`
- `S3 group / multi-context pack`

第二阶段再补：

- controlled episode benchmark；
- self-authored continuity；
- target continuity；
- group continuity。
