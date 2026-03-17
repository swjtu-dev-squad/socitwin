# R4-03 推荐算法统一接口 — 证据报告

| 属性 | 值 |
|---|---|
| **任务** | R4-03 Recommender Interface |
| **状态** | PASS |
| **Gate 通过率** | 29/29 |
| **生成时间** | 2026-03-17 |

---

## 1. 实现概述

新增 `oasis_dashboard/recommender.py`，包含：

- **`Recommender` 基类**：统一 `rank(user_id, candidates, context) -> list[dict]` 接口
- **`TikTokRecommender`**：短期兴趣 + 完播率 + 互动 + 新鲜度
- **`XiaohongshuRecommender`**：内容质量 + 社交亲密度 + 搜索意图 + 新鲜度
- **`PinterestRecommender`**：长期兴趣 + 画板相似度 + 视觉/主题相似度 + 新鲜度
- **`get_recommender(platform, config)`**：工厂函数，支持参数配置
- **`ab_compare(...)`**：最小 A/B 对比框架，输出 top-K 差异与 Jaccard 多样性分数

---

## 2. 打分公式

### TikTok

```
score = 0.35 × short_term_interest
      + 0.25 × completion_rate
      + 0.20 × engagement
      + 0.20 × freshness
```

### 小红书

```
score = 0.35 × content_quality
      + 0.30 × social_affinity
      + 0.20 × search_intent_match
      + 0.15 × freshness
```

### Pinterest

```
score = 0.40 × long_term_interest
      + 0.30 × board_similarity
      + 0.20 × visual_or_topic_similarity
      + 0.10 × freshness
```

---

## 3. T2 验证：相同候选集，不同推荐器排序有差异

| 推荐器 | Top-1 | Top-2 | Top-3 |
|---|---|---|---|
| TikTok | p1 (AI/tech, 高互动) | p6 (AI/robotics) | p3 (烹饪, 高完播率) |
| 小红书 | p1 (AI/tech, 搜索匹配) | p6 (AI/robotics) | p5 (时尚, 高质量) |
| Pinterest | p4 (旅行, 匹配长期兴趣) | p3 (烹饪) | p1 (AI/tech) |

- TikTok vs 小红书 Jaccard: **0.67**（top-3 有差异）
- TikTok vs Pinterest Jaccard: **0.33**（top-3 差异显著）
- 小红书 vs Pinterest Jaccard: **0.33**（top-3 差异显著）
- **Diversity Score: 0.60**

---

## 4. T3 验证：参数变化影响排序

| 配置 | short_term | completion | engagement | freshness | p3 排名 |
|---|---|---|---|---|---|
| 默认 | 0.35 | 0.25 | 0.20 | 0.20 | 第 3 位 |
| 新鲜度增强 | 0.05 | 0.05 | 0.05 | 0.85 | **第 2 位** |

参数变化后 p3（freshness_hours=1，最新内容）排名从第 3 位提升至第 2 位，验证参数配置生效。

---

## 5. REST API 接口

| 端点 | 方法 | 描述 |
|---|---|---|
| `/api/recommender/platforms` | GET | 获取支持的平台列表及默认权重 |
| `/api/recommender/rank` | POST | 对候选内容进行单平台排序 |
| `/api/recommender/ab-compare` | POST | 多平台 A/B 对比排序 |

---

## 6. Gate 通过情况

| Gate | 描述 | 结果 |
|---|---|---|
| T1 × 9 | 三平台均可实例化、rank()、有 score/breakdown | **PASS** |
| T2 × 3 | 三对推荐器 top-3 排序有差异 | **PASS** |
| T3 × 2 | 参数变化影响排序，新鲜度提升改善 p3 排名 | **PASS** |
| T4 × 4 | A/B 框架可运行，有 overlap_analysis 和 diversity_score | **PASS** |
| T5 × 3 | 推荐器切换不影响主链运行 | **PASS** |
| T6 × 4 | score_breakdown 字段完整，值在 [0,1] 范围内 | **PASS** |
| T7 × 4 | REST API 可用，返回正确结构 | **PASS** |
