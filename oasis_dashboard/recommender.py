"""
统一推荐器接口与三平台最小实现

支持平台：TikTok、小红书（Xiaohongshu）、Pinterest
每个推荐器实现统一的 rank() 接口，通过加权公式对候选内容进行打分排序。
"""

from __future__ import annotations
import math
import time
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 统一接口基类
# ---------------------------------------------------------------------------

class Recommender:
    """推荐器基类，所有平台推荐器必须继承并实现 rank() 方法。"""

    platform: str = "base"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config: dict[str, Any] = config or {}

    def rank(
        self,
        user_id: int,
        candidates: list[dict],
        context: dict | None = None,
    ) -> list[dict]:
        """
        对候选内容进行排序。

        Parameters
        ----------
        user_id : int
            当前用户 ID
        candidates : list[dict]
            候选内容列表，每项包含 post_id, content, likes, reposts,
            completion_rate, freshness_hours 等字段
        context : dict, optional
            上下文信息（用户兴趣、搜索词等）

        Returns
        -------
        list[dict]
            按 score 降序排列的候选列表，每项附加 score 和 score_breakdown 字段
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement rank()")

    def _freshness(self, hours_ago: float) -> float:
        """时间衰减函数：指数衰减，半衰期 24 小时。"""
        return math.exp(-0.693 * hours_ago / 24.0)

    def _normalize(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """将值归一化到 [0, 1]。"""
        if max_val <= min_val:
            return 0.0
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    def _log_ranking(self, user_id: int, results: list[dict]) -> None:
        """记录排序日志，输出 chosen algorithm, top-K ids, scoring summary。"""
        top_k = results[:5]
        logger.info(
            "[Recommender] platform=%s user_id=%s top_k_ids=%s scoring_summary=%s",
            self.platform,
            user_id,
            [r.get("post_id") for r in top_k],
            [{"post_id": r.get("post_id"), "score": round(r.get("score", 0), 4)} for r in top_k],
        )


# ---------------------------------------------------------------------------
# TikTok 推荐器
# ---------------------------------------------------------------------------

class TikTokRecommender(Recommender):
    """
    TikTok 风格推荐器。

    加权公式：
        score = w1 * short_term_interest
              + w2 * completion_rate
              + w3 * engagement
              + w4 * freshness

    默认权重：w1=0.35, w2=0.25, w3=0.20, w4=0.20
    """

    platform = "tiktok"

    DEFAULT_CONFIG = {
        "short_term_weight": 0.35,
        "completion_weight": 0.25,
        "engagement_weight": 0.20,
        "freshness_weight": 0.20,
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._cfg = {**self.DEFAULT_CONFIG, **(config or {})}

    def rank(self, user_id: int, candidates: list[dict], context: dict | None = None) -> list[dict]:
        context = context or {}
        user_interests = set(context.get("interests", []))
        scored = []
        for c in candidates:
            # Short-term interest: keyword overlap between content and user interests
            content_words = set(str(c.get("content", "")).lower().split())
            interest_overlap = len(content_words & {i.lower() for i in user_interests})
            short_term = min(1.0, interest_overlap / max(1, len(user_interests)))

            # Completion rate (0–1)
            completion = float(c.get("completion_rate", 0.5))

            # Engagement: normalized likes + reposts
            likes = float(c.get("likes", 0))
            reposts = float(c.get("reposts", 0))
            engagement = self._normalize(likes + reposts * 2, 0, 100)

            # Freshness
            freshness = self._freshness(float(c.get("freshness_hours", 12)))

            score = (
                self._cfg["short_term_weight"] * short_term
                + self._cfg["completion_weight"] * completion
                + self._cfg["engagement_weight"] * engagement
                + self._cfg["freshness_weight"] * freshness
            )
            scored.append({
                **c,
                "score": round(score, 6),
                "score_breakdown": {
                    "short_term_interest": round(short_term, 4),
                    "completion_rate": round(completion, 4),
                    "engagement": round(engagement, 4),
                    "freshness": round(freshness, 4),
                },
            })
        results = sorted(scored, key=lambda x: x["score"], reverse=True)
        self._log_ranking(user_id, results)
        return results


# ---------------------------------------------------------------------------
# 小红书推荐器
# ---------------------------------------------------------------------------

class XiaohongshuRecommender(Recommender):
    """
    小红书风格推荐器。

    加权公式：
        score = w1 * content_quality
              + w2 * social_affinity
              + w3 * search_intent_match
              + w4 * freshness

    默认权重：w1=0.35, w2=0.30, w3=0.20, w4=0.15
    """

    platform = "xiaohongshu"

    DEFAULT_CONFIG = {
        "quality_weight": 0.35,
        "social_weight": 0.30,
        "search_weight": 0.20,
        "freshness_weight": 0.15,
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._cfg = {**self.DEFAULT_CONFIG, **(config or {})}

    def rank(self, user_id: int, candidates: list[dict], context: dict | None = None) -> list[dict]:
        context = context or {}
        search_query = str(context.get("search_query", "")).lower().split()
        followed_authors = set(context.get("followed_authors", []))

        scored = []
        for c in candidates:
            # Content quality: likes + saves as proxy
            likes = float(c.get("likes", 0))
            saves = float(c.get("saves", c.get("reposts", 0)))
            quality = self._normalize(likes * 0.6 + saves * 1.5, 0, 100)

            # Social affinity: whether author is followed
            author = str(c.get("author_id", c.get("username", "")))
            social_affinity = 1.0 if author in followed_authors else 0.2

            # Search intent match
            content_words = set(str(c.get("content", "")).lower().split())
            if search_query:
                match_count = sum(1 for w in search_query if w in content_words)
                search_match = min(1.0, match_count / len(search_query))
            else:
                # No query: use tag overlap with interests
                user_interests = set(i.lower() for i in context.get("interests", []))
                search_match = min(1.0, len(content_words & user_interests) / max(1, len(user_interests)))

            # Freshness
            freshness = self._freshness(float(c.get("freshness_hours", 24)))

            score = (
                self._cfg["quality_weight"] * quality
                + self._cfg["social_weight"] * social_affinity
                + self._cfg["search_weight"] * search_match
                + self._cfg["freshness_weight"] * freshness
            )
            scored.append({
                **c,
                "score": round(score, 6),
                "score_breakdown": {
                    "content_quality": round(quality, 4),
                    "social_affinity": round(social_affinity, 4),
                    "search_intent_match": round(search_match, 4),
                    "freshness": round(freshness, 4),
                },
            })
        results = sorted(scored, key=lambda x: x["score"], reverse=True)
        self._log_ranking(user_id, results)
        return results


# ---------------------------------------------------------------------------
# Pinterest 推荐器
# ---------------------------------------------------------------------------

class PinterestRecommender(Recommender):
    """
    Pinterest 风格推荐器。

    加权公式：
        score = w1 * long_term_interest
              + w2 * board_similarity
              + w3 * visual_or_topic_similarity
              + w4 * freshness

    默认权重：w1=0.40, w2=0.30, w3=0.20, w4=0.10
    """

    platform = "pinterest"

    DEFAULT_CONFIG = {
        "long_term_weight": 0.40,
        "board_weight": 0.30,
        "topic_weight": 0.20,
        "freshness_weight": 0.10,
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._cfg = {**self.DEFAULT_CONFIG, **(config or {})}

    def rank(self, user_id: int, candidates: list[dict], context: dict | None = None) -> list[dict]:
        context = context or {}
        long_term_interests = set(i.lower() for i in context.get("long_term_interests", context.get("interests", [])))
        user_boards = set(b.lower() for b in context.get("boards", []))

        scored = []
        for c in candidates:
            # Long-term interest: deep topic overlap
            content_tags = set(t.lower() for t in c.get("tags", []))
            content_words = set(str(c.get("content", "")).lower().split())
            all_content = content_tags | content_words
            if long_term_interests:
                lt_score = min(1.0, len(all_content & long_term_interests) / len(long_term_interests))
            else:
                lt_score = 0.3

            # Board similarity: whether post category matches user boards
            post_category = str(c.get("category", c.get("topic", ""))).lower()
            board_sim = 1.0 if post_category in user_boards else (0.5 if any(b in post_category or post_category in b for b in user_boards) else 0.1)

            # Visual/topic similarity: tag overlap with interests
            if long_term_interests:
                topic_sim = min(1.0, len(content_tags & long_term_interests) / max(1, len(long_term_interests)))
            else:
                topic_sim = 0.2

            # Freshness (less important for Pinterest)
            freshness = self._freshness(float(c.get("freshness_hours", 72)))

            score = (
                self._cfg["long_term_weight"] * lt_score
                + self._cfg["board_weight"] * board_sim
                + self._cfg["topic_weight"] * topic_sim
                + self._cfg["freshness_weight"] * freshness
            )
            scored.append({
                **c,
                "score": round(score, 6),
                "score_breakdown": {
                    "long_term_interest": round(lt_score, 4),
                    "board_similarity": round(board_sim, 4),
                    "visual_or_topic_similarity": round(topic_sim, 4),
                    "freshness": round(freshness, 4),
                },
            })
        results = sorted(scored, key=lambda x: x["score"], reverse=True)
        self._log_ranking(user_id, results)
        return results


# ---------------------------------------------------------------------------
# 推荐器工厂
# ---------------------------------------------------------------------------

RECOMMENDER_REGISTRY: dict[str, type[Recommender]] = {
    "tiktok": TikTokRecommender,
    "xiaohongshu": XiaohongshuRecommender,
    "pinterest": PinterestRecommender,
}


def get_recommender(platform: str, config: dict[str, Any] | None = None) -> Recommender:
    """
    根据平台名称获取推荐器实例。

    Parameters
    ----------
    platform : str
        平台名称，支持 'tiktok', 'xiaohongshu', 'pinterest'
    config : dict, optional
        自定义权重配置

    Returns
    -------
    Recommender
        对应平台的推荐器实例

    Raises
    ------
    ValueError
        若 platform 不在支持列表中
    """
    key = platform.lower().strip()
    if key not in RECOMMENDER_REGISTRY:
        raise ValueError(f"Unknown platform '{platform}'. Supported: {list(RECOMMENDER_REGISTRY.keys())}")
    return RECOMMENDER_REGISTRY[key](config)


# ---------------------------------------------------------------------------
# 最小 A/B 比较框架
# ---------------------------------------------------------------------------

def ab_compare(
    user_id: int,
    candidates: list[dict],
    context: dict | None = None,
    platforms: list[str] | None = None,
    top_k: int = 5,
    configs: dict[str, dict] | None = None,
) -> dict:
    """
    对同一批候选内容，使用多个推荐器分别排序，输出 top-K 差异报告。

    Parameters
    ----------
    user_id : int
        当前用户 ID
    candidates : list[dict]
        候选内容列表
    context : dict, optional
        上下文信息
    platforms : list[str], optional
        参与对比的平台列表，默认全部三个
    top_k : int
        每个推荐器取前 K 个结果
    configs : dict[str, dict], optional
        各平台的自定义权重配置

    Returns
    -------
    dict
        包含各平台 top-K 结果、差异分析和日志的报告
    """
    platforms = platforms or list(RECOMMENDER_REGISTRY.keys())
    configs = configs or {}
    context = context or {}

    report: dict = {
        "user_id": user_id,
        "candidate_count": len(candidates),
        "top_k": top_k,
        "platforms": {},
        "overlap_analysis": {},
        "diversity_score": 0.0,
    }

    top_k_sets: dict[str, set] = {}

    for platform in platforms:
        rec = get_recommender(platform, configs.get(platform))
        ranked = rec.rank(user_id, candidates, context)
        top = ranked[:top_k]
        top_ids = [r.get("post_id") for r in top]
        top_k_sets[platform] = set(top_ids)
        report["platforms"][platform] = {
            "top_k_ids": top_ids,
            "top_k_scores": [{"post_id": r.get("post_id"), "score": r.get("score"), "breakdown": r.get("score_breakdown")} for r in top],
        }

    # Overlap analysis
    platform_list = list(top_k_sets.keys())
    for i, p1 in enumerate(platform_list):
        for p2 in platform_list[i + 1:]:
            overlap = top_k_sets[p1] & top_k_sets[p2]
            key = f"{p1}_vs_{p2}"
            report["overlap_analysis"][key] = {
                "overlap_count": len(overlap),
                "overlap_ids": list(overlap),
                "jaccard": round(len(overlap) / max(1, len(top_k_sets[p1] | top_k_sets[p2])), 4),
            }

    # Diversity score: 1 - average Jaccard similarity
    if report["overlap_analysis"]:
        avg_jaccard = sum(v["jaccard"] for v in report["overlap_analysis"].values()) / len(report["overlap_analysis"])
        report["diversity_score"] = round(1 - avg_jaccard, 4)

    return report
