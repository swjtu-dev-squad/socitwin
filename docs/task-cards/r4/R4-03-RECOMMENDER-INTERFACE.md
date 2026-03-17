# 任务卡：R4-03 推荐算法统一接口与三平台最小实现

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P1 |
| **类型** | Recommender / Algorithm Interface / Experimentation |
| **负责人** | 推荐算法负责人 |
| **协作人** | 后端负责人、实验框架负责人 |
| **关联 Issue** | #32, #30 |

---

## 1. 背景

Issue #32 明确了三类推荐算法（TikTok, 小红书, Pinterest）的核心机制和平台特点，并要求建立统一推荐接口、A/B 测试框架、性能监控和参数化配置。当前前端配置区已有算法选择 UI，说明算法入口位已存在。

## 2. 目标

建立统一接口和三平台最小可运行策略，使系统能够：

- 以统一方式调用不同推荐器
- 在实验中切换 TikTok / 小红书 / Pinterest 风格
- 进行最小 A/B 对比
- 支持参数配置和日志输出

## 3. 范围

### In Scope

- 统一 `rank()` 接口
- TikTok 最小打分器
- 小红书最小打分器
- Pinterest 最小打分器
- 参数配置
- 最小 A/B 对比

### Out of Scope

- LightFM/Implicit 全量训练接入
- 视觉特征深模型
- 复杂向量召回系统
- 大规模离线评估平台

## 4. 当前问题

系统虽有算法选择入口，但缺少“统一推荐器接口 + 三平台语义”的真正实现。若不先统一接口，后续各推荐策略将独立发展，难以整合。

## 5. 修复/实现方案

### 5.1 统一接口

```python
class Recommender:
    def rank(self, user_id: int, candidates: list[dict], context: dict) -> list[dict]:
        raise NotImplementedError
```

### 5.2 三平台最小实现（加权公式）

- **TikTok**: `0.35 * short_term_interest + 0.25 * completion_rate + 0.20 * engagement + 0.20 * freshness`
- **小红书**: `0.35 * content_quality + 0.30 * social_affinity + 0.20 * search_intent_match + 0.15 * freshness`
- **Pinterest**: `0.40 * long_term_interest + 0.30 * board_similarity + 0.20 * visual_or_topic_similarity + 0.10 * freshness`

### 5.3 参数配置

允许通过配置调整权重，如 `tiktok.short_term_weight`。

### 5.4 最小 A/B 框架

- 同一批候选内容
- 不同推荐器分别排序
- 输出 top-K 差异与简单日志

## 6. 具体子任务

1. 新建推荐器基类与三平台实现。
2. 将当前算法选择区映射到推荐器实例。
3. 在后端加入日志，记录 `chosen algorithm`, `top-K ids`, `scoring summary`。
4. 创建最小 A/B 比较脚本或 API。

## 7. 测试用例

- **T1**: 统一接口可实例化三种推荐器（均可调用 `rank()`）。
- **T2**: 相同候选集，不同推荐器排序有差异（top-K 结果不同）。
- **T3**: 参数变化影响排序（修改权重后排序变化可观察）。
- **T4**: 推荐器切换不影响主链运行。

## 8. 通过标准 (Gate)

- [ ] 三平台推荐器接口统一
- [ ] 三个最小打分器可运行
- [ ] 参数可配置
- [ ] 有最小 A/B 比较入口
- [ ] 推荐器切换不影响主链运行
- [ ] 输出日志可解释排序原因

## 9. 失败标准

- 三平台实现逻辑互不兼容
- 算法切换只改名不改行为
- 参数配置不生效
- 排序不可解释

## 10. 证据要求

- `artifacts/r4/r4_03_rank_compare.json`
- `artifacts/r4/r4_03_ab_report.md`
- 三种推荐器的示例 top-K 输出
- 参数调节前后对比

## 11. 建议提交信息

```bash
git commit -m "feat(recsys): add unified recommender interface and three platform scorers"
```
