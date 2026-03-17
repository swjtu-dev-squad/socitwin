# 任务卡：FIX-R3-POLARIZATION-FALLBACK 极化 fallback 历史隔离修复

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Analytics Integrity / Fallback Isolation / Regression Safety |
| **负责人** | @分析负责人 |
| **协作人** | @引擎负责人、@前端负责人 |
| **关联任务** | R3-02 |
| **关联文件** | `oasis_dashboard/real_oasis_engine_v3.py`、`oasis_dashboard/polarization_analyzer.py`（可选）、`src/pages/Analytics.tsx`（前端，若展示 source） |

**预期产出：**
- fallback 值与真实分析值隔离
- polarization trace 改进
- 回归测试
- source 字段与调试日志

---

## 1. 背景

当前 `_update_polarization()` 会在每一步调用分析器，并把得到的 `polarization` 追加到 `polarization_analyzer.history` 中。代码已经明确显示：

- step 每步调用 `_update_polarization()`；
- 若结果中有 `polarization`，则直接 `append` 到 `history`；
- `history` 保留最近 100 条。

R3-02 的修复通过"当无新帖子时，对历史均值加入高斯噪声"实现了极化曲线的动态变化。这对 smoke 很有帮助，但如果这些 fallback 扰动值继续写回主历史，就会导致：

- fallback 值污染 analyzer 主历史；
- 后续均值越来越依赖噪声；
- "真实分析值"和"UI 动态扰动值"混在一起，语义不清。

## 2. 目标

将极化结果分层处理，满足：

- 真实 analyzer 输出与 fallback 动态值分离；
- fallback 动态值不污染 analyzer 主历史；
- 返回结果显式标注 `source`；
- 前端或日志可区分"真实极化分析"与"动态降级值"。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| `_update_polarization()` 历史写入策略 | 极化模型数学重构 |
| `source` / `degraded` / `cached` 等标志 | 观点传播理论模型重写 |
| fallback 动态值隔离 | 推荐算法与极化联动 |
| 调试日志与 trace | |
| 回归测试 | |

## 4. 当前问题

当前逻辑会把所有 `polarization` 都推进 `history`。如果 fallback 动态值也这样做，历史均值就会逐步偏向"历史噪声轨迹"，从而让 analyzer 未来的降级基础越来越失真。

## 5. 修复方案

### 5.1 方案核心

把极化结果分成两层：

**A. 真实分析结果**
- 来源：analyzer 真正对新帖子/真实输入做出的计算
- 可写入主历史（如 `analysis_history`）

**B. fallback 动态值**
- 来源：无新帖子时，用历史基线 + 微扰生成
- 只用于：当前 step 返回、UI 动态展示、降级 trace
- **不写入 analyzer 主历史**

### 5.2 推荐字段

在返回值中增加或统一以下字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `source` | `str` | `"analyzed"` / `"history_dynamic"` / `"historical_fallback"` / `"error_fallback"` |
| `is_fallback` | `bool` | 是否为降级/扰动值 |
| `history_written` | `bool` | 本步是否写入了主历史 |

## 6. 实现建议

### 6.1 修改 `_update_polarization()`

```python
result = await self.polarization_analyzer.analyze()

source = result.get("source", "analyzed")
is_fallback = source != "analyzed"

self.last_polarization = result.get("polarization", 0.0)

should_write_history = (
    "polarization" in result and
    not is_fallback
)

if should_write_history:
    self.polarization_analyzer.history.append(result["polarization"])
    if len(self.polarization_analyzer.history) > 100:
        self.polarization_analyzer.history.pop(0)

result["history_written"] = should_write_history
result["is_fallback"] = is_fallback
return result
```

### 6.2 fallback 动态分支显式标 `source`

```python
result = dict(result)
result["polarization"] = dynamic_pol
result["source"] = "history_dynamic"
result["is_fallback"] = True
result["history_written"] = False
```

### 6.3 可选：分离两类历史

如果需要更干净的实现，可以把：
- `analysis_history`：只存真实 analyzer 输出
- `display_history`：存给 UI 的最终值

但最小修复先做到"不把 fallback 值写回主 `history`"就够了。

## 7. 测试用例

### T1：真实分析结果写入 history

**步骤：**
(1) 构造有新帖输入
(2) 调用 `_update_polarization()`

**预期：**
- `source="analyzed"`（或等价真实来源）
- `history_written=True`
- `history` 长度 +1

### T2：无新帖 fallback 动态值不写 history

**步骤：**
(1) 连续两步，第二步无新帖
(2) 触发 `history_dynamic`

**预期：**
- `source="history_dynamic"`
- `is_fallback=True`
- `history_written=False`
- `history` 长度不增长

### T3：多步 fallback 不污染主历史

**步骤：**
(1) 连续多步无新帖
(2) 多次触发动态扰动

**预期：**
- `history` 长度保持稳定
- 返回值可动态变化
- 主历史均值不被噪声持续侵蚀

### T4：前端/trace 可区分 source

**步骤：**
(1) 导出 polarization trace
(2) 查看 `source` 字段

**预期：**
- 能区分 `analyzed` 与 `history_dynamic`
- 页面或调试日志中能看出本步是否为降级值

## 8. 通过标准（Gate）

- [ ] 真实分析值写入主 `history`
- [ ] fallback 动态值不写入主 `history`
- [ ] 返回结果显式标注 `source`
- [ ] trace 中可分辨 `analyzed` / `history_dynamic`
- [ ] 多步 fallback 不导致主 `history` 被噪声污染
- [ ] R3-02 的"曲线不静止"特性仍然保留

## 9. 失败标准

- fallback 值仍持续写入主历史
- `source` 不可区分
- 曲线虽然在动，但全靠污染 `history` 实现
- 修复后又回到水平直线且无合理解释

## 10. 证据要求

- `artifacts/smoke/fix_r3_polarization_fallback_report.md`
- `artifacts/smoke/fix_r3_polarization_trace.csv`
- 至少一段 analyzer 调试日志
- `history` 长度变化记录（真实分析 vs fallback）

## 11. 风险与备注

这张卡的目的不是否定 R3-02，而是给它"装隔离层"。现在的 fallback 对 smoke 很有帮助，但必须防止它悄悄升级成"主分析事实来源"。

## 12. 建议提交信息

```
git commit -m "fix(polarization): isolate fallback dynamics from analyzer history"
```
