# 记忆架构实现审查检查清单

- 日期：2026-04-28
- 分支：`eval/memory-performance-evaluation`
- 状态：implementation-level checklist
- 目标：作为 [audit-master-plan-20260428.md](./audit-master-plan-20260428.md) 的从属代码级检查清单，从具体实现出发，对当前 `action_v1` 记忆架构的关键模块逐项核查

## 0. 与总审查计划的关系

本文档来自一次独立实现审查，里面有不少可以吸收的内容：问题簇划分、依赖关系图、逐模块检查表和审查输出格式都比总计划更细。它不替代总计划，也不定义新的审查顺序，而是作为实施阶段的 checklist 使用。

两份计划的分工如下：

| 文档 | 角色 | 主要回答 |
| --- | --- | --- |
| [audit-master-plan-20260428.md](./audit-master-plan-20260428.md) | 总审查计划 / source of truth | 记忆系统应该从模型交互、prompt 可见事实、memory contract、检索任务分型和行为闭环角度如何重审 |
| 本文档 | 实现审查检查清单 | 每个代码模块需要核对哪些粗糙实现、信息损失点、字段使用情况和验证缺口 |

因此后续审查顺序以总计划为准：

1. 先做 prompt trace 审查，确认模型每一步实际看见什么、recall note 如何进入 prompt、哪些字段只是内部 metadata。
2. 再按本文的问题簇和模块表做代码级细查，尤其是 `summary` 截断、query 构建、rerank、`ActionEpisode` 字段和 prompt budget。
3. 每个模块审查都需要回到总计划里的 memory contract、retrieval task taxonomy 和行为级闭环，不只停留在局部函数改法。

本文档中出现的行号只作为初始定位锚点。正式模块审查时需要重新核对当前分支代码，避免行号漂移导致误读。

本文档不能单独新增或改写审查阶段。如果 checklist 发现新的优先级、架构边界或实现方向，需要先更新 [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)，再回到本文档补充具体检查项。

## 1. 为什么要做这次审查

当前 `action_v1` 记忆架构已经跑通了基本功能链路，B 级评测也产出了第一轮可读结果（`b-level-post-linked-results-20260426`）。但是基本功能的跑通不代表实现质量的可用。当前系统存在大量"一拍脑袋实现"的情况——即在计划驱动下做出了功能上能跑但完全没有从系统运行和模型交互的底层原理出发来设计的实现。

具体表现包括但不限于：

- "摘要"就是截断固定字数
- 查询构建就是取第一个帖子的摘要
- 重排序就是 token overlap 计数
- 很多字段被机械式地填入但从未真正参与系统行为

这类问题不是个别几处小修小补能解决的，它们来自同一个根因：实现时没有从"系统到底要跟模型交互什么、需要如何影响模拟行为"这个底层出发来思考。

## 2. 审查原则

本次审查遵循以下原则：

1. **从底层原理出发**：每个模块的审查都要回答"它在系统与模型交互中承担什么角色？当前实现是否真的满足了这个角色？"
2. **从具体代码出发**：结论必须锚定到具体文件、函数、行号，不做架空分析
3. **以保真度为中心**：关注信息在链路中的损失、变形和污染，而非仅仅关注功能是否存在
4. **一次一个模块**：不试图一次性审查全部，按依赖关系和重要程度分批进行

## 3. 当前系统总体概况

### 3.1 架构总览

`action_v1` 记忆系统的核心链路如下：

```
平台环境 → Observation Shaping → Perception → Recall Planning
                                                    ↓
                                            Chroma 长期存储查询
                                                    ↓
                                            Prompt Assembly
                                                    ↓
                                            模型决策 + 工具执行
                                                    ↓
                                            Step Recording (StepSegment + ActionEvidence + ActionEpisode)
                                            ↗                    ↖
                                   短期维护 (Consolidator)    长期写入 (Chroma)
```

系统由一组 `backend/app/memory/` 模块共同组成。本文档后续按信息流和实现职责拆成可审查的模块，而不是预设模块数量本身有设计意义。

### 3.2 当前已跑通的部分

- 链路功能完整：observation → shaping → perception → recall → prompt → 模型决策 → episode 写入 → 长期存储 → 短期维护，全链路可运行
- Agent 隔离正确：B 级评测中跨 agent 污染为 0，agent_id 过滤正常工作
- 自检索基本可用：self Hit@3 达到 0.90，说明写入/embedding/rerank/agent filter 基础通道畅通
- 评测框架可工作：harness 能产出可读的 Hit@K、MRR、污染统计

### 3.3 识别的关键问题簇

以下按照信息流方向，列出已识别的所有关键问题簇：

#### 簇 0：Observation 层的"摘要"问题（根因层）

**位置**：`observation_semantics.py:9-19` `summarize_text()`，`observation_shaper.py` 全文

**问题**：整个系统的"摘要"概念，从 observation 到 perception 到 episode 到 query 构建，底层全部依赖 `summarize_text()`，而这个函数的本质就是硬截断到固定字符数（如 120 chars for posts, 96 for comments）。这意味着：

- "摘要"丢失了帖子正文的主体语义，只保留了开头
- 当开头恰好是寒暄、引语或不完整表达时，语义错位
- 所有下游模块（perception topic、semantic anchors、target_snapshot、episode document、recall query）都在用这个截断后的字符串
- 这是一个全链路语义退化源

**审查重点**：这是最底层的根因问题之一，需要在审查 Observation 模块时优先处理。

#### 簇 A：ActionEpisode 字段臃肿与语义空洞

**位置**：`episodic_memory.py:102-161` `ActionEpisode`，`longterm.py:26-50` `REQUIRED_ACTION_EPISODE_KEYS`

**问题**：
- `ActionEpisode` 定义 27 个字段（不含 dataclass 继承），`REQUIRED_ACTION_EPISODE_KEYS` 强制 18 个必填
- 多个字段在实际运行中经常为空或仅有占位值：
  - `evidence_quality` / `degraded_evidence`：写入但不影响检索排序
  - `action_significance`：通过简单启发式推断（`action_significance.py`），区分度很低
  - `idle_step_gap`：仅第一个 persistable episode 会被赋值，其余总是 0
  - `summary_text`：`to_payload()` 中硬编码为空字符串 `""`
  - `metadata`：`to_payload()` 中硬编码为空字典 `{}`
- `state_changes` 虽然结构上合理（如 `liked_post:123`），但形式过于简单，且仅在 `DefaultPlatformMemoryAdapter.derive_state_changes()` 中以大型 if-elif 链生成
- `action_fact` 本质上是 `tool_name(tool_args)` 的字符串化，语义信息有限

**审查重点**：哪些字段真正参与了检索排序和模型决策？哪些只是"看起来有用但从未被用"的元数据？需要从检索和 prompt 使用两个方向反向审查。

#### 簇 B：检索文档构造与排序的 Token-Overlap 依赖

**位置**：`longterm.py:464-481` `_episode_document()`，`longterm.py:542-575` `_rerank_retrieved_payloads()` / `_score_action_episode()`

**问题**：
- Embedding 文档由 `_episode_document()` 拼装：一个扁平的 `字段名: 值` 多行文本
- 查询文本和 episode 文档之间的 embedding 相似度是第一层召回
- 第二层重排序 `_score_action_episode()` 是纯 token overlap 计数：
  - 查询字符串整个出现在字段中 → 权重 × 2
  - 查询的每个 token 是否在字段中出现 → ＋权重
- 评分权重 `ACTION_SCORING_WEIGHTS` 是手工设定的魔数：topic:4, action_name:5, action_category:2, action_fact:5, target_snapshot:5, authored_content:4, local_context:3, outcome:2, state_changes:1

**审查重点**：这直接解释了 B 级评测的核心发现——like_post/repost 等语义贫乏的动作被 quote_post 等长文本动作在排序中压过。需要审查排序方案是否应该引入结构匹配（如 exact target_id 匹配、parent_post.post_id 匹配）和语义匹配。

#### 簇 C：Recall 查询构建过于简单

**位置**：`retrieval_policy.py:16-54` `build_request()`

**问题**：
- 当前查询构建是一个简单的优先级链：
  1. 有 topic → 直接用 topic 字符串查询
  2. 无 topic → 用前 2 个 semantic anchors 拼接
  3. 无 anchors → 用前 5 个 entities 拼接
  4. 都没有 → 用最近 2 个 action seed 的 target summary / authored content 拼接
- 这里 topic 来自 `extract_topics_from_snapshot()` = 第一个 post 的 summary（即截断 120 字符）
- semantic anchors 来自 `extract_semantic_anchors_from_snapshot()` = `post#ID: summary` 格式
- 查询本质上就是当前 observation 中第一个帖子的前 120 字符
- 没有多查询融合、没有查询扩展、没有利用 post_id/target_id 做结构查询

**审查重点**：查询是否应该包含目标帖子的 structure key（post_id）、是否应该做多查询并行然后合并、是否应该利用 local_context 提供更多约束。

#### 簇 D：Observation 退化链的语义损失追踪

**位置**：`observation_shaper.py:74-135` `shape()` 主链，4 个退化阶段

**问题**：
- 退化链是 raw_guards → long_text_cap → interaction_shrink → physical_fallback
- 每一层的退化都是定量的（减少 comment 数量、截断 text 长度），不是定性的（语义压缩、优先级排序）
- 进入 physical_fallback 时，信息几乎全部丢失：帖子只剩 2 个 sample，所有 comment 丢失，group 退化为计数
- `render_stats` 能追踪退化了多少（truncated_field_count 等），但不能追踪退化了什么（哪些语义被丢弃）
- `summarize_text()` 截断后的 `...[compacted from N chars]` 标记本身占用了宝贵的 token 预算

**审查重点**：退化链是否应该引入语义压缩层（用模型做真正的摘要），而不是纯粹的定量裁剪？render_stats 是否需要追踪"丢失了什么"而不只是"丢了多少"？

#### 簇 E：短期记忆维护的机械性

**位置**：`consolidator.py` 全文，`working_memory.py` 全文

**问题**：
- Recent → Compressed 的驱逐决策基于 token 计数，没有考虑内容重要性
- Action Summary Block 的合并条件是"相邻步骤"且"span 不超过 max_summary_merge_span"，非常机械
- Heartbeat 的合并同样是相邻即合并
- 没有对"哪些行为值得在 compressed 层保留更久"做任何区分
- 驱逐策略是 FIFO + token budget，没有重要性权重

**审查重点**：短期记忆是否应该区分重要动作的保留优先级？合并策略是否可以引入语义相似度判断而不仅是相邻性判断？

#### 簇 F：Recall Gate 的触发条件设计

**位置**：`recall_planner.py:171-238` `_should_retrieve()`

**问题**：
- 四个 primary trigger：topic_trigger、anchor_trigger、recent_action_trigger、self_authored_trigger
- 触发条件全部是"是否存在非空值"的二元判断
- 没有对触发信号强度的分级（如 topic 的语义匹配程度）
- `recent_action_rehit` 检查的是最近动作的 target 是否在当前 snapshot 中再出现——这个设计方向对，但实现只看最近 2 个 segment 的 target refs
- cooldown 和重复查询抑制是纯步数/字符串判断

**审查重点**：trigger 是否应该从"是否存在"升级为"是否相关"的强度信号？recent_action_rehit 的窗口是否合理？

#### 簇 G：Prompt Assembly 的预算与选择

**位置**：`prompt_assembler.py` 全文

**问题**：
- recent/compressed/recall 各分配固定比例的 token 预算（35%/10%/10%）
- 三个区域的预算分配是否合理取决于场景，当前是硬编码比例
- recall candidate 的去重（overlap filtering）只有 exact action key 和 conservative step 两种策略
- 没有对 recall candidate 做重要性排序后再过滤

**审查重点**：预算分配的硬编码比例在不同场景下是否合理？overlap 过滤是否过于保守（过滤掉可能互补的信息）？

#### 簇 H：评测框架的覆盖缺口

**位置**：`evaluation_harness.py` 全文

**问题**（已从评测报告中确认）：
- 没有评估召回记忆是否最终注入 prompt（VAL-RCL-10 只测了 trace 级注入）
- 没有评估模型行为是否真的使用了召回记忆（行为级评估）
- 没有测试 follow/mute 等关系记忆（author-based recall）
- 没有 group memory 测试
- 每个场景只跑一轮，不具统计稳定性
- 没有使用真实 runtime 的 `last_recall_query_text` 做 trace replay

**审查重点**：评测框架需要在哪些方面增强以支撑对上述 A-G 簇问题的验证？

### 3.4 问题簇之间的依赖关系

```
簇 0 (summary 截断) ──→ 簇 C (查询构建) ──→ 簇 B (排序)
     │                      │
     └──────────────────────┴──→ 簇 F (recall gate)
     │
     └──→ 簇 A (episode 字段质量)
              │
              └──→ 簇 B (排序质量)
              
簇 D (退化链) ──→ 簇 0 ──→ 簇 C

簇 E (短期维护) ──→ 簇 G (prompt assembly)

簇 H (评测覆盖) 依赖所有上述簇的问题被解决
```

**实现级审查顺序建议**：簇 0 → 簇 C → 簇 B → 簇 A → 簇 D → 簇 F → 簇 E → 簇 G → 簇 H

这遵循"从信息源头到信息消费者"的自底向上顺序。

但这不是总审查的第一步。总计划仍然先做 prompt trace，因为只有先确认模型实际输入和记忆注入形态，后续才能判断每个底层字段和查询信号是否真的服务于模型决策。

## 4. 审查模块计划

以下按建议审查顺序排列。每个模块的审查将产出一份独立文档。

### Round 1：Observation 与信息源头

| 模块 | 文件 | 审查重点 |
|------|------|---------|
| **O1. 文本摘要** | `observation_semantics.py` `summarize_text()` | 硬截断 vs 真摘要的语义损失量化；对下游全链路的影响 |
| **O2. Observation Shaper** | `observation_shaper.py` | 四层退化的保真度追踪；退化策略是否应该从定量转向定性 |
| **O3. Snapshot 构建** | `observation_semantics.py` `build_prompt_visible_snapshot()` | summary/evidence_quality/self_authored 的实际使用率；relation_anchor 的语义空洞 |
| **O4. Perception 派生** | `observation_policy.py` | topic/anchor 选择策略是否合理（取第一个 post 的 summary 作为 topic） |

### Round 2：长期记忆写入

| 模块 | 文件 | 审查重点 |
|------|------|---------|
| **L1. ActionEpisode 字段精简** | `episodic_memory.py` `ActionEpisode` | 字段使用率审计；冗余字段；必需字段的语义必要性 |
| **L2. Episode 构造链路** | `episodic_memory.py` `build_action_episodes()` | 从 evidence 到 episode 的信息映射是否完整；字段填充质量 |
| **L3. Evidence 构建** | `action_evidence.py` | target_snapshot 解析的覆盖率；resolution_status 的判定是否准确 |
| **L4. State Changes 生成** | `episodic_memory.py` `derive_state_changes()` | if-elif 链的可维护性；state_changes 在下游的实际使用 |

### Round 3：长期记忆检索

| 模块 | 文件 | 审查重点 |
|------|------|---------|
| **R1. Episode Document** | `longterm.py` `_episode_document()` | 文档构造的策略；字段选择是否最优；结构化信息利用 |
| **R2. 查询构建** | `retrieval_policy.py` `build_request()` | 查询质量；多方面查询的缺失；structure key 未利用 |
| **R3. 排序与 Rerank** | `longterm.py` `_rerank_retrieved_payloads()` / `_score_action_episode()` | Token overlap 的不足；是否需要结构匹配加权；排序权重校准 |
| **R4. Embedding 与存储** | `longterm.py` `ChromaLongtermStore` | Embedding 模型选择；payload 序列化效率；filter 正确性 |

### Round 4：短期记忆与 Prompt 装配

| 模块 | 文件 | 审查重点 |
|------|------|---------|
| **S1. Working Memory** | `working_memory.py` | ActionItem/ActionSummaryBlock 的信息密度；overlap 过滤策略 |
| **S2. Consolidator** | `consolidator.py` | 驱逐策略的机械性；合并策略的语义空洞；Heartbeat 的价值 |
| **S3. Prompt Assembler** | `prompt_assembler.py` | 预算分配合理性；三类记忆（recent/compressed/recall）的注入质量 |
| **S4. Recall Planner** | `recall_planner.py` | Gate 触发条件的粒度；cooldown 策略；query 与 gate 的耦合 |
| **S5. Budget Recovery** | `budget_recovery.py` | 恢复策略的实际触发频率；降级路径的质量 |

### Round 5：评测与验证

| 模块 | 文件 | 审查重点 |
|------|------|---------|
| **E1. Harness 增强** | `evaluation_harness.py` | 评测覆盖缺口清单；增强优先级 |
| **E2. 指标设计** | `evaluation_harness.py` 指标部分 | 现有指标的局限性；需要补充的指标 |
| **E3. 场景补全** | evaluation fixtures/scenarios | follow/mute 关系记忆测试；group memory 测试；多轮稳定性 |

## 5. 可吸收进总计划的内容

本文档相比总计划更细的部分，应该被吸收到后续模块审查模板中：

1. **问题簇依赖图**
   - 有助于解释为什么 `summary` 截断不是单点问题，而是同时影响 query、episode document、rerank 和 recall gate 的上游语义退化源。
2. **逐文件模块表**
   - 可以作为分模块审查的任务拆分基础，尤其是 Observation、ActionEpisode、Longterm Retrieval、Prompt Assembly、Evaluation Harness 这几组。
3. **字段使用率视角**
   - 对 `ActionEpisode`、`REQUIRED_ACTION_EPISODE_KEYS`、`summary_text`、`metadata`、`evidence_quality`、`degraded_evidence` 等字段，应统一追问“是否进入检索、prompt 或行为决策”，而不是只看是否被写入。
4. **结构匹配优先级**
   - 对 `like_post`、`repost`、`follow`、`mute`、`join_group` 等弱文本动作，应优先检查 target/post/user/group/thread 结构键是否被用于过滤或 rerank。
5. **评测反向约束**
   - 评测缺口不只列在 evaluation 文档里，也要在每个模块审查中说明“这个问题需要哪类 `VAL-*` 或 B/C-level 场景验证”。

## 6. 与已有审查文档的关系

本次审查是在以下已有文档基础上的深化：

- [audit-and-validation.md](./audit-and-validation.md)：已识别风险簇的台账（AUD-OBS-01, AUD-LTM-02, AUD-RCL-02 等）。本次审查将逐一核对这些风险在代码层面的具体表现。
- [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)：总审查计划。本文档提供更细的实现级问题簇和模块 checklist。
- [../current-architecture.md](../current-architecture.md)：架构事实文档。本次审查将以此为基础，但深入到具体实现的代码质量层面。
- [../observation-and-evidence.md](../observation-and-evidence.md)：observation 链路的事实文档。本次审查将对其中的"当前接受限制"做更细致的代码级验证。
- [../evaluation/results/b-level-post-linked-results-20260426.md](../evaluation/results/b-level-post-linked-results-20260426.md)：第一轮评测结果。本次审查将以评测发现为导向，反向溯源实现根因。

## 7. 审查输出格式

每个模块的审查将产出独立 Markdown 文件，包含：

1. **该模块在系统中的角色**：从系统与模型交互的角度说明它的职责
2. **当前实现分析**：关键函数/类的代码级走读
3. **与上下游的交互检查**：输入来源、输出去向、信息损失点
4. **已识别问题清单**：具体到行号的问题描述 + 影响评估
5. **与已有 audit 条目的对照**：对应 AUD-xxx 条目，确认或更新状态
6. **改进方向建议**：非具体的实现方案，而是改进需要满足的约束和方向
7. **验证回路**：该问题需要哪个 deterministic test、`VAL-*` 场景、B-level replay 或 C-level behavior scenario 才能证明被修复

## 8. 下一步

先按总计划完成 prompt trace 审查，建议路径仍放在 audit 目录下，例如：

```text
docs/memory/audit/prompt-trace-audit-20260428.md
```

完成 prompt trace 后，再从 **Round 1 O1（文本摘要）** 开始第一份实现级详细审查。`summary` 截断是最上游的根因层之一，但它的优先级和修复方向需要先由 prompt trace 证明：模型实际依赖了哪些 summary、哪些 summary 进入了 runtime query、哪些 summary 又被写入 `ActionEpisode` 或 long-term document。
