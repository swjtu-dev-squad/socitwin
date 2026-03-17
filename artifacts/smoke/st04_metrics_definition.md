# ST-04 三大指标定义文档

**版本**：v1.0  
**日期**：2026-03-17  
**关联 Issue**：#22, #24

---

## 指标 1：极化指数 (Polarization Index)

**定义**：衡量群体在某一话题上的观点分裂程度，值域 [0, 1]，越高表示越极化。

**计算公式**：

```
polarization = variance(stance_scores) / max_variance
```

其中 `stance_scores` 由 LLM 对每条帖子分析立场后打分（-1 到 +1），`max_variance` 为理论最大方差（所有人意见完全对立时）。

**实现位置**：`oasis_dashboard/polarization_analyzer.py` → `PolarizationAnalyzer.analyze()`

**数据来源**：SQLite `post` 表中的帖子内容 → LLM 立场分析 → 方差归一化

**本次测试结果**：

| step | polarization |
|---|---|
| 1 | 0.1600 |
| 2 | 0.1600 |
| 3 | 0.1600 |
| 4 | 0.1600 |
| 5 | 0.1600 |

**说明**：1 agent / AI 话题下，极化率稳定在 16%，说明该 agent 的帖子内容具有一定的立场倾向性（AI skeptic）。

---

## 指标 2：传播速度 (Information Velocity)

**定义**：单位时间内新增的信息量（帖子数），衡量信息在社交网络中的扩散速率。

**计算公式**：

```
velocity(t) = Δposts / Δtime = (posts_t - posts_{t-1}) / (time_t - time_{t-1})
```

单位：posts/s（帖子/秒）

**实现位置**：前端 `src/pages/Analytics.tsx` → `informationVelocity` useMemo

**数据来源**：`/api/sim/status.totalPosts` + 时间戳差值

**本次测试结果**：

| step | delta_posts | delta_time_s | velocity (posts/s) |
|---|---|---|---|
| 1 | 1 | 4.90 | 0.2041 |
| 2 | 0 | 0.95 | 0.0000 |
| 3 | 0 | 0.96 | 0.0000 |
| 4 | 0 | 0.93 | 0.0000 |
| 5 | 0 | 0.94 | 0.0000 |

**平均速度**：0.0408 posts/s

**说明**：1 agent 场景下，agent 在第 1 步创建了 1 条帖子，后续 4 步均为 refresh 操作，故速度为 0。多 agent 场景下该指标才有实际参考价值。

---

## 指标 3：羊群指数 (Herd Index / HHI)

**定义**：衡量 agent 行为的集中程度，使用赫芬达尔-赫希曼指数（HHI）计算动作多样性。值越高（接近 1）表示行为越集中（羊群效应越强），越低（接近 0）表示行为越多样。

**计算公式**：

```
H = Σ(p_a)^2          # 原始 HHI，其中 p_a 为动作类别 a 的占比
H_norm = (H - 1/n) / (1 - 1/n)   # 归一化 HHI，消除类别数量影响
```

**实现位置**：`artifacts/smoke/st04_metrics_smoke_result.csv`（当前为离线计算，待集成到后端）

**数据来源**：SQLite `trace` 表中的 `action` 字段分布

**本次测试结果**：

| 动作类型 | 次数 | 占比 |
|---|---|---|
| refresh | 4 | 66.7% |
| create_post | 1 | 16.7% |
| sign_up | 1 | 16.7% |

- 原始 HHI：0.5000
- 归一化 HHI：**0.2500**（分散，弱羊群效应）

**说明**：1 agent 场景下，agent 主要执行 refresh 操作（66.7%），行为较为分散，羊群指数偏低。多 agent 场景下，若大多数 agent 都倾向于 like 某类帖子，HHI 会显著升高。

---

## 总结

| 指标 | 可计算 | 当前值 | 数据来源 | 备注 |
|---|---|---|---|---|
| 极化指数 | ✅ | 0.1600 | LLM + SQLite | 已集成到 API |
| 传播速度 | ✅ | 0.0408 posts/s | totalPosts + 时间戳 | 已在前端计算 |
| 羊群指数 | ✅ | 0.2500 | trace 表动作分布 | 待集成到后端 API |

**三项指标全部可计算，ST-04 ✅ PASS。**
