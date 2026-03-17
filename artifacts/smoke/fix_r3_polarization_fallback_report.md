# FIX-R3-POLARIZATION-FALLBACK 修复验证报告

| 属性 | 值 |
|---|---|
| **任务卡** | FIX-R3-POLARIZATION-FALLBACK |
| **日期** | 2026-03-17 |
| **最终结果** | **PASS** |
| **关联任务** | R3-02 |

---

## 1. 问题背景

R3-02 的修复通过"当无新帖子时，对历史均值加入高斯噪声"实现了极化曲线的动态变化。然而，这些 fallback 扰动值被直接写回 `polarization_analyzer.history`，导致：

(1) fallback 值污染 analyzer 主历史；
(2) 后续均值越来越依赖噪声（"噪声喂噪声"）；
(3) "真实分析值"和"UI 动态扰动值"混在一起，语义不清。

## 2. 修复方案

### 2.1 核心变更（`real_oasis_engine_v3.py`）

在 `_update_polarization()` 中引入分层逻辑：

**(1) 真实分析来源识别**

```python
REAL_ANALYSIS_SOURCES = {'llm', 'heuristic', 'heuristic_empty_llm_fallback'}
source = result.get('source', 'analyzed')
is_fallback = result.get('is_fallback', source not in REAL_ANALYSIS_SOURCES)
```

通过检查 `polarization_analyzer.analyze()` 返回的 `source` 字段，区分真实分析（`llm`、`heuristic`）和降级值（`history_dynamic`、`db_cache` 等）。

**(2) 条件写入主历史**

```python
should_write_history = ("polarization" in result and not is_fallback)
if should_write_history:
    self.polarization_analyzer.history.append(result["polarization"])
```

只有真实分析值才写入主历史，fallback 动态值不写入。

**(3) 显式标注返回字段**

```python
result['is_fallback'] = is_fallback
result['history_written'] = should_write_history
```

返回值中显式包含 `source`、`is_fallback`、`history_written` 三个字段，供 trace 和前端区分。

## 3. 验证结果

### 3.1 Gate 通过情况

| Gate | 描述 | 结果 |
|---|---|---|
| 1 | 真实分析值写入主 history | **PASS** |
| 2 | fallback 动态值不写入主 history | **PASS** |
| 3 | 返回结果显式标注 source | **PASS** |
| 4 | trace 中可分辨 analyzed / history_dynamic | **PASS** |
| 5 | 多步 fallback 不导致主 history 被噪声污染 | **PASS** |
| 6 | R3-02 的"曲线不静止"特性仍然保留 | **PASS** |

### 3.2 Trace 数据摘要（15 步）

| 步骤类型 | 步骤数 | source | history_written |
|---|---|---|---|
| 真实分析（LLM 分析新帖子） | 1 | `llm` | `True` |
| fallback 动态（无新帖子） | 14 | `history_dynamic` | `False` |

**关键观测**：
- 14 步 fallback 期间，`history` 长度保持稳定（不增长）
- 极化值在 15 步中产生 15 个不同值（范围 0.2965 ~ 0.3790）
- 主历史均值基于真实分析值，不被噪声侵蚀

### 3.3 调试日志样本

```
📊 [Polarization] step=2 last_analyzed_post_id=5 total_posts=5
📊 [Polarization] dynamic update (no new posts): base=0.3153 noise=+0.0214 result=0.3367
    source=history_dynamic is_fallback=True history_written=False
📊 [Polarization] step=3 last_analyzed_post_id=5 total_posts=5
📊 [Polarization] dynamic update (no new posts): base=0.3153 noise=-0.0045 result=0.3108
    source=history_dynamic is_fallback=True history_written=False
```

## 4. 结论

修复成功实现了极化 fallback 历史隔离，满足任务卡所有通过标准。真实分析值与 fallback 动态值现在处于完全隔离的语义层，后续极化分析不会受到噪声污染。
