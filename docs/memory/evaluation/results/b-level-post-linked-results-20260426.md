# 长期记忆检索评测结果

- 日期：2026-04-26
- 分支：`eval/memory-performance-evaluation`
- 评测对象：`action_v1` 长期记忆检索链路
- 结果目录：
  - `backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426`
  - `backend/test-results/memory-eval/b-level-v05-s2-post-linked-final-20260426`

## 1. 本次测试测什么

本报告整理当前记忆路线第一版可用的真实模拟检索结果。

核心问题是：

> 对于某个 agent 在真实模拟过程中实际看见过的帖子，能不能用这个帖子在 prompt-visible observation 里的摘要，从该 agent 的最终长期记忆中找回它和这个帖子相关的动作记忆？

这个测试是“最终长期记忆库检索测试”，不是“逐步 runtime recall 回放测试”。

关键边界：

- 测试题目来自真实运行中的 `prompt_visible_snapshot`。
- 检索文本只使用 `visible_post.summary`。
- `post_id` 不进入检索文本，只用于判定正确答案和调试。
- 检索时按 `agent_id` 过滤，所以每个 probe 只查当前 agent 自己的长期记忆。
- 测试使用模拟结束后的最终 Chroma 长期记忆库。
- 本测试不判断模型后续行为是否真的使用了召回记忆。

## 2. 测试场景

两个场景的共同设置：

- 记忆模式：`action_v1`
- 长期记忆后端：Chroma + OpenAI-compatible embedding endpoint
- 嵌入模型：`nomic-embed-text:latest`
- 模拟步数：18
- probe limit：无限制，配置中记为 `0`
- 平台路线：Twitter-style OASIS route

### S1：稳定单话题场景

场景 ID：`s1_stable_single_topic`

场景目标：构造一个语义集中、相对稳定的单话题讨论，用来观察基础 Hit@1、Hit@3 和 MRR。

初始帖子：

> 新加坡式领导者培养路径通常强调精英教育、早期人才筛选、奖学金和结构化公共部门职业路径。英国式政治通常被描述为更开放、职业过滤更弱。哪一种模式更可能产生有能力且负责任的政治领导者？

智能体设定：

| 智能体                 | 角色说明                                                 |
| ---------------------- | -------------------------------------------------------- |
| Institutional Comparer | 从教育、公共部门训练和制度激励角度比较政治人才选拔系统。 |
| Open Politics Advocate | 关注民主开放性、社会流动性和封闭精英选拔的风险。         |
| Pragmatic Reformer     | 关注政治系统能否产生有效决策、公共信任和政策执行力。     |

### S2：相似话题干扰场景

场景 ID：`s2_similar_topic_interference`

场景目标：构造同主题、相似表达、不同立场的讨论，用来观察排序质量和跨 agent 污染风险。

初始帖子：

> 一篇新文章主张一种 Anglo-Gaullist 改革路线：更强的国家能力、更高的战略自主性，以及面向国家更新的政府机器。支持者认为这是重建制度的严肃方案；批评者认为这只是把人们原本偏好的政策包装成一个流行标签。

智能体设定：

| 智能体                     | 角色说明                                       |
| -------------------------- | ---------------------------------------------- |
| State Capacity Supporter   | 支持更强的国家规划能力、行政能力和战略自主性。 |
| Reform Label Skeptic       | 怀疑流行政治标签只是重新包装既有偏好。         |
| Implementation Critic      | 关注改革议程是否包含可执行的制度细节。         |
| Historical Analogy Checker | 质疑历史领导模式能否直接迁移到当代制度中。     |

## 3. 测试流程

1. 使用固定 agent 和一个 seed post 启动真实模拟场景。
2. 执行 18 个 official simulation step。
3. 将每个 agent 的动作转成 `ActionEpisode` 并写入长期记忆。
4. 记录每一步的 prompt-visible observation snapshot。
5. 用已写入的 `ActionEpisode` 构造 `VAL-LTM-05` 自检 probe。
6. 从 observation 历史中每个可见 post 构造 `VAL-RCL-11` 帖子关联 probe。
7. 使用当前 Chroma 检索链路取 top-3 长期记忆。
8. 统计 Hit@1、Hit@3、MRR、同 agent 错目标 和 跨 agent 污染。

## 4. 指标说明

| 指标 | 含义 |
| --- | --- |
| 写入 episode 数 | 写入长期记忆的 `ActionEpisode` 数量。它表示本轮真实模拟实际形成了多少条可检索的动作记忆。 |
| 自检 Hit@1 / Hit@3 / MRR | 来自 `VAL-LTM-05`。它用每条 `ActionEpisode` 自身字段构造查询，检查该记忆自身能不能被找回。 |
| 帖子 Hit@1 / Hit@3 / MRR | 来自 `VAL-RCL-11`。它用真实 observation 中可见帖子的 summary 构造查询，检查能否找回同 agent 和该帖子结构相关的长期记忆。 |
| 可见帖子 probe / 帖子 probe 数 | agent 在真实 observation 中“看见某个帖子”的测试样本数。同一个帖子可能被多个 agent 看见，也可能在多个 step 反复出现，所以它不是去重帖子数。 |
| 去重可见帖子 | `post_id` 去重后的可见帖子数量。它表示这些帖子 probe 实际覆盖了多少个不同帖子。 |
| 有正确答案的帖子 probe | 该 agent 的最终长期记忆中存在与该帖子结构相关的动作事件，因此可以参与 Hit@1 / Hit@3 / MRR 计算。 |
| 无正确答案 | agent 看见了这个帖子，但最终长期记忆中没有与该帖子结构相关的动作事件。它不算检索失败，也不进入 Hit@K 分母。代码和原始 JSON 中可能记为 `no_ground_truth`。 |
| 跨 agent 污染 / 跨 agent top-3 | top-3 检索结果中出现其他 agent 的记忆。理想情况应为 0。代码和原始 JSON 中可能记为 `cross_agent_contamination`。 |
| 同 agent 错目标 | 检索到了同一个 agent 的记忆，但不是当前帖子或当前 episode 的正确记忆，通常说明同主题相似内容排序混淆。代码和原始 JSON 中可能记为 `same_agent_wrong_target`。 |

`可见帖子 probe`、`有正确答案的帖子 probe` 和 `无正确答案` 的关系是：

```text
可见帖子 probe = 有正确答案的帖子 probe + 无正确答案
```

例如 S1 中：

```text
150 = 118 + 32
```

这里的 `去重可见帖子` 不参与这个加法，它只是对 `post_id` 去重后的覆盖数量。

## 5. 主要结果

### 5.1 总览表

| 场景            | 写入 episode 数 | 自检 Hit@1 | 自检 Hit@3 | 自检 MRR | 帖子 probe 数 | 有正确答案的帖子 probe | 帖子 Hit@1 | 帖子 Hit@3 | 帖子 MRR | 跨 agent top-3 | 同 agent 错目标 |
| --------------- | --------------: | ---------: | ---------: | -------: | ------------: | ----------------------: | ---------: | ---------: | -------: | -------------: | --------------: |
| S1 稳定单话题   |              74 |     0.6622 |     0.9054 |   0.7635 |           150 |                     118 |     0.6356 |     0.7966 |   0.7133 |              0 |              24 |
| S2 相似话题干扰 |              80 |     0.7125 |     0.9000 |   0.7979 |           124 |                      89 |     0.6966 |     0.9663 |   0.7921 |              0 |               3 |

### 5.2 Episode 自检索能力

`VAL-LTM-05` 测的是：一条已经写入长期记忆的 `ActionEpisode`，在用自身字段构造查询时，能不能把自己找回来。代码中这组指标对应 `real_self_action_retrievability`。

它主要检查写入文档、embedding、rerank 和 agent filter 是否基本可用。

| 场景 | query 数 |  Hit@1 |  Hit@3 |    MRR | 跨 agent top-3 |
| ---- | -------: | -----: | -----: | -----: | -------------: |
| S1   |       74 | 0.6622 | 0.9054 | 0.7635 |              0 |
| S2   |       80 | 0.7125 | 0.9000 | 0.7979 |              0 |

解释：

- 两轮 自检索能力 的 Hit@3 都达到 0.9 左右，说明长期记忆写入和基础检索链路是通的。
- 两轮 跨 agent 污染 都是 0，说明本轮样本中没有发现 agent 过滤失效。
- Hit@1 明显低于 Hit@3，说明正确记忆通常能进前三，但不一定排第一。

### 5.3 帖子关联最终检索

`VAL-RCL-11` 测的是：从真实 observation 里取可见帖子摘要，能不能在最终长期记忆中找回同 agent 和该帖子相关的动作事件。代码中这组指标对应 `post_linked_final_lookup`。

它更接近我们关心的实际问题：当环境中再次出现某个帖子时，长期记忆能否提供这个 agent 过去与该帖子的互动记忆。

| 场景 | 可见帖子 probe | 去重可见帖子 | 有正确答案的 probe |  Hit@1 |  Hit@3 |    MRR | 无正确答案 | 同 agent 错目标 |
| ---- | --------------: | --------------: | -----------------: | -----: | -----: | -----: | ---------: | --------------: |
| S1   |             150 |              24 |                118 | 0.6356 | 0.7966 | 0.7133 |         32 |              24 |
| S2   |             124 |              27 |                 89 | 0.6966 | 0.9663 | 0.7921 |         35 |               3 |

解释：

- S1 样本量充足，但排序混淆更明显。
- S2 虽然设计为相似话题干扰场景，但这一轮 帖子关联 Hit@3 更高。由于真实模拟存在随机性，这不能直接说明 S2 一定更容易。
- `无正确答案` 不是失败，而是该 agent 虽然看见了帖子，但最终长期记忆中没有和该帖子结构相关的动作事件。
- 当前主要失败类型是 同 agent 错目标，尤其在 S1 中更明显。

## 6. 结果分析

### 6.1 当前已经跑通的部分

当前 action 路线能够在真实模拟中产生可用数量的长期记忆：

- S1 写入 74 条 ActionEpisode。
- S2 写入 80 条 ActionEpisode。
- 两轮测试都没有 skipped usable probe。

agent 过滤在本轮样本中表现正常：

- S1 跨 agent top-3 数：0
- S2 跨 agent top-3 数：0

长期记忆检索基本可用：

- S1 self Hit@3：0.9054
- S2 self Hit@3：0.9000
- S1 帖子关联 Hit@3：0.7966
- S2 帖子关联 Hit@3：0.9663

### 6.2 当前主要问题

主要问题不是跨 agent 污染，而是同 agent 内部的错目标检索。

S1 的 24 个帖子关联未命中全部是同 agent 错目标。典型模式是：

- 正确答案：与当前帖子相关的 `like_post` 或 `repost`。
- 实际 top-3：同一个 agent、同一大主题下语义更丰富的 `quote_post`。

这和当前实现一致：

- `like_post` 和 `repost` 自身文本语义较弱。
- `quote_post` 通常包含较长的自然语言内容。
- 当前 rerank 主要依赖字段/token overlap，所以内容更丰富的 quote 可能压过结构上更准确的 like/repost。

### 6.3 两个场景的差异

本轮 S1 的 帖子关联 Hit@3 低于 S2：

- S1：0.7966
- S2：0.9663

但这不能直接解释为 S1 天然更难或 S2 天然更容易。真实模拟中模型输出和动作分布有随机性，本轮只能说明：

- 当前 harness 已经能产出可读、可解释的检索指标。
- 不同真实运行可能产生不同记忆分布。
- 如果要汇报稳定 benchmark 数值，后续需要做多轮重复实验。

## 7. 当前限制

本次评测有参考价值，但还不是完整记忆能力评测。

当前限制：

- 没有评估召回记忆是否最终注入 prompt。
- 没有评估模型行为是否真的使用了召回记忆。
- 没有测试 follow、mute、重复关注等作者关系记忆。
- 没有测试 group memory。
- 每个场景目前只跑了一轮，不具备统计稳定性。
- 没有使用真实 runtime 的 `last_recall_query_text` 做完整 trace replay。

## 8. 阶段性结论

当前 milestone 下，可以给出一个相对稳妥的 B 级检索结果：

- action 路线可以完成真实模拟，并持久化长期 `ActionEpisode`。
- Chroma 长期记忆链路已经接通，能够返回相关记忆。
- 本轮样本中 agent 过滤正常，没有发现跨 agent 污染。
- top-3 检索整体可用。
- 当前最明显的检索弱点是同 agent、同主题排序混淆，也就是同一个 agent 在相似主题下产生多条动作记忆时，系统能找回相近记忆，但不一定把结构上最准确的那条排在最前。

建议下一步：

1. 加强 同 agent 错目标 样例的诊断展示。
2. 审查 `_episode_document()` 和 rerank 对 `like_post`、`repost` 的处理。
3. 考虑加入轻量结构加权，例如 exact `target_id`、`parent_post.post_id`、`state_changes`。
4. 对 S1/S2 做多轮重复实验，再汇报稳定均值。
5. 单独设计 author-based recall 测试，用于评估 follow/mute 等关系记忆。
