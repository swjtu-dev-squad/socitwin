# Reddit Action V1 真实 E2E 测试记录 2026-04-18

- 状态：已完成
- 范围：`action_v1` 记忆路线，Reddit 平台，20 个智能体，30 轮
- 目的：验证迁移后的记忆路线能否在较长真实模拟中稳定运行，并观察智能体动作模式，重点关注评论行为、重复刷新、互动欲望和记忆模块介入情况。

## 1. 测试命令

执行命令：

```bash
backend/.venv/bin/python backend/tests/e2e/e2e_simulation_test.py \
  --platform reddit \
  --topic climate_change_debate \
  --agent-count 20 \
  --max-steps 30 \
  --memory-mode action_v1 \
  --max-tokens 1024 \
  --timeout 3600
```

运行目标：

- 后端 API：`http://localhost:8000`
- 平台：`reddit`
- 记忆模式：`action_v1`
- 主模型：`DEEPSEEK/DEEPSEEK_CHAT`
- 生成输出上限：`1024`
- 运行时报告的上下文 token 上限：`16384`

生成结果：

- E2E JSON：`backend/test-results/e2e/20260418_215026/test-result-20260418_215026.json`
- 图表：
  - `backend/test-results/e2e/20260418_215026/propagation-metrics-20260418_215026.png`
  - `backend/test-results/e2e/20260418_215026/herd-effect-metrics-20260418_215026.png`
  - `backend/test-results/e2e/20260418_215026/polarization-metrics-20260418_215026.png`
- SQLite 数据库：`backend/data/simulations/simulation_033d7289.db`

## 2. 测试前提和测试脚本说明

本次测试前，E2E 脚本已经修复了 20 个智能体以上测试时的后台任务等待问题。

后端会根据智能体数量估算单步耗时。20 个智能体时，`/api/sim/step` 会启动后台任务并立刻返回 `task_id`，不会同步等待所有 agent 动作完成。旧版 E2E 脚本把这个立即返回误当成“本轮已经完成”，导致之前出现过“50 轮几秒钟跑完、没有真实 agent 行为”的无效结果。当前脚本已经改为轮询 `/api/sim/step/{task_id}`，只有后台任务真正完成后才记录该轮结果。

本轮仍观察到一个测试脚本层面的记录问题：

- 第 11 轮显示 `Time: -6.38s`。
- 这是 E2E 计时/记录 bug，不是模拟逻辑 bug。
- 该轮实际成功完成，数据库状态有效。

另一个重要注意点：

- Reddit 的 `trace.created_at` 记录的是真实时间戳。
- 它不能像之前某些 Twitter 测试那样直接当作 step 编号使用。
- 本文中的“按轮动作分布”是根据 E2E 每轮 `interactions_added` 增量，对 SQLite `trace` 行按顺序切片后近似重建的。

## 3. 整体结果

本轮测试完整跑完：

| 指标 | 数值 |
| --- | ---: |
| 请求轮数 | 30 |
| 成功轮数 | 30 |
| 失败轮数 | 0 |
| 总耗时 | `1231.13s` |
| 平均单轮耗时 | `41.04s` |
| 最终帖子数 | 1 |
| 最终 trace / interactions 数 | 851 |
| 最终评论数 | 53 |
| 最终评论点赞数 | 56 |
| 最终帖子点赞数 | 20 |
| 最终关注数 | 3 |

总体判断：

- `action_v1` 路线可以在 Reddit 20 agents x 30 steps 的真实模拟中完整跑通。
- 运行中没有崩溃。
- 没有超过 16k 上下文设置。
- 长短期记忆相关调试信息在运行中持续可读。

## 4. 记忆运行状态

最终 memory debug 摘要：

| 字段 | 数值 |
| --- | ---: |
| `memory_mode` | `action_v1` |
| `agent_count` | 20 |
| `context_token_limit` | 16384 |
| `generation_max_tokens` | 1024 |
| `total_recent_retained` | 20 |
| `total_compressed_retained` | 530 |
| `total_recall_injected` | 7 |
| `max_prompt_tokens` | 10897 |
| `max_observation_tokens` | 9301 |

观察到的记忆行为：

- 高保真 recent 一开始增长到 `60`，从第 6 轮开始下降并稳定在 `20`。
- compressed 从第 4 轮开始出现，并持续累积到 `530`。
- 长期记忆 recall 在前几轮之后开始间歇性注入。
- E2E 记录中的最大 prompt token 大约到 `11347`，最终为 `10897`，仍低于 16k 上下文上限。
- 从上下文增长角度看，本轮 30 步测试中没有出现失控膨胀。

解释：

- `action_v1` 的短期记忆压缩机制在生效。
- 长期记忆召回在生效，但不是每一轮都注入。
- prompt 没有无限增长。
- 但后期 observation 占用仍然较大，最终 `max_observation_tokens=9301`，说明 Reddit 单帖长评论区也会带来较高 observation 压力。

## 5. 全局动作分布

最终 SQLite 动作分布：

| 动作 | 数量 |
| --- | ---: |
| `refresh` | 643 |
| `like_comment` | 56 |
| `create_comment` | 53 |
| `trend` | 52 |
| `sign_up` | 20 |
| `like_post` | 20 |
| `follow` | 3 |
| `search_user` | 2 |
| `search_posts` | 1 |
| `create_post` | 1 |

派生统计：

- 总 trace 行数：`851`
- refresh 行数：`643`
- 本文口径下的有意义非刷新动作数：`188`
- 有意义动作占比约：`22.1%`
- `do_nothing`：`0`

解释：

- `refresh` 数量很高，一部分原因是每个 agent 会频繁刷新/观察环境，这属于结构性记录，不应简单理解为“agent 只会刷新”。
- 但 `refresh` 占比确实偏高，后续测试应该继续监控有意义动作占比。
- 本轮没有出现 `do_nothing` 坍缩。

## 6. 按轮动作模式

E2E 每轮增量显示：

- 第 1 轮：81 条 trace。
- 第 2-7 轮：每轮 40-46 条 trace。
- 第 8-30 轮：多数轮为 21-28 条 trace。

根据 SQLite 行顺序和 E2E 每轮增量近似重建的按轮动作分布如下：

| 轮次 | 总数 | Refresh | Trend | Create Comment | Like Comment | Like Post | Create Post | Follow | Search | Other | Meaningful |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 81 | 53 | 7 | 0 | 0 | 0 | 1 | 0 | 0 | 20 | 8 |
| 2 | 42 | 22 | 14 | 2 | 0 | 4 | 0 | 0 | 0 | 0 | 20 |
| 3 | 40 | 22 | 8 | 2 | 0 | 8 | 0 | 0 | 0 | 0 | 18 |
| 4 | 40 | 22 | 1 | 9 | 0 | 7 | 0 | 0 | 1 | 0 | 18 |
| 5 | 46 | 21 | 7 | 6 | 11 | 1 | 0 | 0 | 0 | 0 | 25 |
| 6 | 44 | 20 | 3 | 2 | 17 | 0 | 0 | 0 | 2 | 0 | 24 |
| 7 | 45 | 20 | 4 | 4 | 14 | 0 | 0 | 3 | 0 | 0 | 25 |
| 8 | 22 | 20 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| 9 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 10 | 24 | 20 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| 11 | 24 | 21 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| 12 | 22 | 20 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| 13 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 14 | 22 | 20 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 2 |
| 15 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 16 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 17 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 18 | 25 | 20 | 1 | 1 | 3 | 0 | 0 | 0 | 0 | 0 | 5 |
| 19 | 28 | 21 | 1 | 1 | 5 | 0 | 0 | 0 | 0 | 0 | 7 |
| 20 | 22 | 20 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| 21 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 22 | 24 | 21 | 0 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 3 |
| 23 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 24 | 24 | 20 | 0 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 4 |
| 25 | 22 | 20 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| 26 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 27 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 28 | 23 | 20 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 3 |
| 29 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 30 | 21 | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

关键解释：

- 第 2-7 轮动作类型更丰富。
- 从第 8 轮开始，几乎每轮都变成 `20 refresh + 1-7 个有意义动作`。
- 后期大部分有意义动作是评论或评论点赞。
- 没有 `do_nothing` 坍缩。
- 也没有完全失去互动，但有意义动作密度在早期之后明显下降。

## 7. 评论行为

本轮测试确认 Reddit agent 可以使用评论动作：

- `create_comment=53`
- `like_comment=56`
- SQLite `comment` 表有 `53` 行
- SQLite `comment_like` 表有 `56` 行

这和之前 Twitter 20-agent 测试不同。原因是 OASIS 默认动作空间不同：

- Twitter 默认动作不包含 `CREATE_COMMENT`。
- Reddit 默认动作包含 `CREATE_COMMENT`、`LIKE_COMMENT` 和 `DISLIKE_COMMENT`。

因此，之前 Twitter 测试中 `comment=0` 不是 action_v1 记忆路线失败导致的，而是因为 OASIS 官方 Twitter 默认动作列表本来就没有把评论工具开放给 agent。

## 8. 评论质量和重复倾向

虽然评论动作正常产生，但评论内容出现明显模板化倾向。

常见重复开头包括：

- `This is such an important discussion!`
- `This is such a rich and important discussion!`
- `This is such a crucial conversation!`
- `I'm really appreciating this deep and nuanced discussion!`

观察到的行为：

- 很多评论都集中在同一个初始帖子下。
- 部分用户反复生成语义相近的高度概括式赞同评论。
- 用户 `10` 产生了大量非常相似的评论。
- 后期很多轮只新增 1 条评论或 1 条评论点赞。

可能原因：

- 当前测试主题只创建了一个强 seed post。
- Reddit 默认动作空间更鼓励围绕帖子评论区互动，而不是持续发新帖。
- observation 很可能持续把同一个主帖和已有评论推给 agent。
- prompt 对“不要重复表达、引入新角度、结合自身身份差异”约束不足。
- 当前事件化和记忆召回能保留讨论上下文，但并不会主动惩罚重复话术或重复赞同。

这个问题不阻断路线稳定运行，但会影响长程社交模拟质量，后续需要单独审查。

## 9. 指标观察

最终 OASIS 指标：

| 指标 | 数值 |
| --- | ---: |
| 传播规模 scale | 1 |
| 传播深度 depth | 0 |
| 最大传播宽度 max breadth | 1 |
| 羊群效应 conformity index | 0.000 |
| 平均帖子得分 average post score | 20.000 |
| 极化平均幅度 | 0.000 |
| 极化评估 agent 数 | 0 |

这些指标在本轮测试中参考价值有限。

原因：

- 全程只有一个帖子，因此传播指标几乎没有变化空间。
- 主要讨论发生在评论区，但当前传播指标更偏帖子级。
- 最终极化指标没有评估任何 agent，因此不能支持实质结论。
- 羊群指标中的 `average_post_score=20.0` 主要来自唯一帖子积累点赞，不能说明复杂群体传播。

结论：

- 本轮 E2E 对“路线是否稳定运行”和“动作分布”有价值。
- 但在当前 Reddit 单主帖场景下，不适合用来评估传播深度、极化变化等效果指标。

## 10. 稳定性判断

正向发现：

- `action_v1` 完整跑完 30 轮，没有崩溃。
- 长期记忆召回在运行。
- 短期记忆压缩在运行。
- prompt token 没有超过 16k 上下文限制。
- Reddit 评论工具真实触发，并写入 SQLite。
- 没有出现 `do_nothing` 坍缩。

问题和风险：

- 第 7 轮之后有意义动作密度下降。
- refresh 占 trace 体量过高。
- 后期行为集中在单个主帖评论区。
- 初始主题帖之后没有继续新增帖子。
- E2E 计时存在一次负数记录 bug。
- metrics summary 的 step 语义不一致，最终 `metrics_summary.current_step` 显示为 `1`，但 E2E 实际完成 30 轮。
- 当前传播和极化指标不能很好反映 Reddit 评论区行为。

## 11. 与 Twitter 测试的对比

之前 Twitter 长测试表现为：

- 新帖和 quote post 很多。
- 没有评论，因为 Twitter 默认动作列表没有开放 `CREATE_COMMENT`。
- 帖子级活动更强。

本轮 Reddit 测试表现为：

- 只有一个帖子。
- 有大量评论和评论点赞。
- 更像单帖评论区讨论。
- 帖子级传播很弱。

主要差异来自平台默认动作空间，而不是记忆路线本身。

直接含义：

- 如果项目希望 Twitter agent 具备“回复/评论”能力，可以考虑只在 `action_v1 + twitter` 中扩展 `CREATE_COMMENT`。
- 如果项目希望 upstream 保持 OASIS 官方原生行为，upstream 的 Twitter 默认动作列表不应改。

## 12. 后续建议

优先修复：

1. 修复 E2E 负耗时记录 bug。
2. 在 E2E JSON 中直接记录每轮结构化动作分布，不要事后靠 SQLite 行切片重建。
3. 修复或记录 metrics summary 中 `current_step=1` 的语义问题。
4. 在测试摘要中加入动作分布：
   - refresh 数
   - do_nothing 数
   - create_post 数
   - create_comment 数
   - like / like_comment 数
   - 有意义动作占比

优先分析：

1. 决定是否给 `action_v1 + twitter` 添加 `CREATE_COMMENT`。
2. 审查 Reddit agent 为什么在 seed post 之后几乎不再创建新帖子。
3. 审查 observation 排序和 recall 是否让 agent 反复聚焦同一个帖子/评论线程。
4. 增加多 seed post 或多 topic 测试，判断重复是否来自单主题单主帖设计。
5. 增加评论质量诊断：
   - 重复开头
   - 重复作者行为
   - 评论语义相似度
   - 目标帖子/评论集中度

较低优先级改进：

- 让 metrics 更适配 Reddit 评论区行为。
- 如果前端需要历史行为而不只是当前 agent 状态，可以增加 monitor history 接口或持久化 monitor snapshot。
- 在路线稳定后，再考虑通过 prompt 约束减少“泛泛赞同式”重复评论。

