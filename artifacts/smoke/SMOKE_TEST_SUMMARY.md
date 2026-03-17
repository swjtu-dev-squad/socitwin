# 第一批 Smoke Test 执行总结报告

**执行时间**：2026-03-17  
**执行环境**：Ubuntu 22.04 / Node.js 22.13.0 / Python 3.11 / gpt-4.1-mini  
**测试配置**：1 agent / Reddit / AI topic / 5 steps

---

## 执行结果总览

| 任务卡 | 标题 | 结论 | 关键发现 |
|---|---|---|---|
| **ST-01** | Context / Memory 最小链路 | ✅ **PASS** | 引擎和模型服务正常，context 链路可用 |
| **ST-02** | 初始化 → step → status 主链路 | ✅ **PASS** | API 全链路通畅，reset 正常归零 |
| **ST-05** | WebSocket 增量日志与去重回归 | ❌ **FAIL** | Issue #13 日志重复 bug 仍存在（重复率 50%） |
| **ST-03** | Analytics 真数据/假数据甄别 | ✅ **PASS** | 无伪装数据，未实现指标诚实标注 |
| **ST-04** | 三大指标最小可计算 | ✅ **PASS** | 三项指标全部可计算并有真实输出 |

**总体**：4 PASS / 1 FAIL

---

## 完成标准核查

| 完成标准 | 状态 | 说明 |
|---|---|---|
| 1 agent / reddit / AI / 5 steps 能稳定跑通 | ✅ | ST-02 验证，5 步全部成功 |
| 无 traceback / 白屏 / step 卡死 | ✅ | 服务稳定，无崩溃 |
| status / history / logs / analytics 数据源可追溯 | ✅ | ST-03 完整审计 |
| 未实现指标不再伪装成真实数据 | ✅ | Coming Soon 标注清晰 |
| 历史重复日志 bug 未回归 | ❌ | **Issue #13 仍存在，重复率 50%** |

---

## ST-01 详情：Context / Memory 最小链路

**结论**：✅ PASS

- Python 引擎可正常导入（camel-oasis 安装成功）
- Context 模块初始化正常，token limit = 4096
- Memory window 机制可用
- 模型服务（gpt-4.1-mini via OpenAI-compatible API）响应正常

---

## ST-02 详情：初始化 → step → status 主链路

**结论**：✅ PASS

| 接口 | 结果 |
|---|---|
| POST /api/sim/config | ✅ 1 agent 初始化成功，耗时 1.54s |
| POST /api/sim/step × 5 | ✅ 全部成功，currentStep 1→5 |
| GET /api/sim/status | ✅ 状态正确反映 |
| POST /api/sim/reset | ✅ currentStep 归零，running=false |

**附加发现**：`better-sqlite3` 原生模块需手动编译（`npm install` in 模块目录），建议补充到 README。

---

## ST-05 详情：WebSocket 增量日志与去重回归

**结论**：❌ FAIL

**Bug 位置**：`real_oasis_engine_v3.py` → `_read_posts_table()` — 每次 step 返回全量历史帖子而非增量

| step | 日志总数 | 唯一内容 | 重复率 |
|---|---|---|---|
| 1 | 2 | 2 | 0% |
| 2 | 3 | 3 | 0% |
| 3 | 4 | 3 | 25% |
| 4 | 5 | 3 | 40% |
| 5 | 6 | 3 | **50%** |

**修复方案**：在 `_get_real_agent_actions()` 中引入 `last_post_id` 水位线，只返回 `post_id > last_post_id` 的新记录。

---

## ST-03 详情：Analytics 真数据/假数据甄别

**结论**：✅ PASS

| 指标 | 数据类型 | 状态 |
|---|---|---|
| 群体极化率 | REAL（LLM 计算） | ✅ 可追溯 |
| 信息传播速度 | DERIVED（真实数据派生） | ✅ 可追溯 |
| 从众效应指数 | NOT_IMPLEMENTED | ✅ 诚实标注 |
| A/B 测试偏差 | NOT_IMPLEMENTED | ✅ 诚实标注 |
| 意见分布 | HARDCODED_ZERO + TODO | ✅ 诚实标注 |
| 极化趋势图 | REAL（WebSocket 事件流） | ✅ 可追溯 |

**无 FAKE_REAL 指标**，相比 Issue #2 描述的旧版本已完成清理。

---

## ST-04 详情：三大指标最小可计算

**结论**：✅ PASS（三项全部可计算）

| 指标 | 公式 | 值 | 数据来源 |
|---|---|---|---|
| 极化指数 | LLM 立场分析 → 方差归一化 | **0.1600**（16%） | PolarizationAnalyzer |
| 传播速度 | Δposts / Δtime | **0.0408 posts/s** | totalPosts + 时间戳 |
| 羊群指数 | HHI = Σ(p_a)²，归一化 | **0.2500** | trace 表动作分布 |

---

## 后续行动建议

**P0 — 立即修复**：

1. **ST-05 Bug Fix**：修复 `_read_posts_table()` 全量返回问题，引入水位线机制。对应 Issue #13。

**P1 — 近期改进**：

2. **better-sqlite3 编译**：在 README 或 `package.json` 的 `postinstall` 脚本中自动化编译步骤。
3. **羊群指数 API 集成**：将 HHI 计算集成到 `/api/sim/status` 或新增 `/api/sim/metrics` 端点。

**P2 — 中期规划**：

4. **意见分布**：在 Issue #23 中明确要求 agent 具备 ideology 属性，解锁该指标。
5. **多 agent 验证**：当前所有测试均为 1 agent，建议在 3~5 agent 场景下重跑全套 Smoke Test。

---

*本报告由自动化 Smoke Test 脚本生成，所有数据均来自真实仿真运行。*
