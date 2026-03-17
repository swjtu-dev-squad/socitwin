"""
R4-03 Unified Recommender Interface Gate Verification Script
"""
import sys
import os
import json
import subprocess

ARTIFACTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(ARTIFACTS_DIR))
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python")

sys.path.insert(0, PROJECT_DIR)

results = {}

def gate(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results[name] = {"status": status, "detail": detail}
    icon = "✅" if condition else "❌"
    print(f"  {icon} Gate: {name} -> {status}")
    if detail:
        print(f"     {detail}")
    return condition

print("=" * 60)
print("R4-03 Unified Recommender Interface Gate Verification")
print("=" * 60)

# ---- Import recommender module ----
try:
    from oasis_dashboard.recommender import (
        Recommender, TikTokRecommender, XiaohongshuRecommender, PinterestRecommender,
        get_recommender, ab_compare, RECOMMENDER_REGISTRY
    )
    import_ok = True
except ImportError as e:
    import_ok = False
    print(f"  ❌ Import failed: {e}")

# ---- Test candidates ----
CANDIDATES = [
    {"post_id": "p1", "content": "AI technology machine learning deep learning", "likes": 80, "reposts": 20, "completion_rate": 0.85, "freshness_hours": 2, "tags": ["AI", "tech"], "category": "technology", "saves": 15},
    {"post_id": "p2", "content": "Sports football game championship winner", "likes": 120, "reposts": 40, "completion_rate": 0.60, "freshness_hours": 5, "tags": ["sports", "football"], "category": "sports", "saves": 5},
    {"post_id": "p3", "content": "Cooking recipe food healthy nutrition", "likes": 50, "reposts": 10, "completion_rate": 0.90, "freshness_hours": 1, "tags": ["food", "cooking"], "category": "food", "saves": 30},
    {"post_id": "p4", "content": "Travel adventure mountain hiking nature", "likes": 200, "reposts": 60, "completion_rate": 0.70, "freshness_hours": 48, "tags": ["travel", "nature"], "category": "travel", "saves": 50},
    {"post_id": "p5", "content": "Fashion design style clothing trends", "likes": 90, "reposts": 25, "completion_rate": 0.75, "freshness_hours": 8, "tags": ["fashion", "design"], "category": "fashion", "saves": 20},
    {"post_id": "p6", "content": "AI robotics automation future technology", "likes": 60, "reposts": 15, "completion_rate": 0.80, "freshness_hours": 3, "tags": ["AI", "robotics"], "category": "technology", "saves": 10},
    {"post_id": "p7", "content": "Fitness workout gym health exercise", "likes": 70, "reposts": 18, "completion_rate": 0.65, "freshness_hours": 6, "tags": ["fitness", "health"], "category": "sports", "saves": 8},
]

CONTEXT = {
    "interests": ["AI", "technology", "machine learning"],
    "long_term_interests": ["travel", "nature", "adventure"],  # Pinterest favors travel content
    "followed_authors": ["alice", "bob"],
    "boards": ["travel", "nature", "outdoor"],  # Pinterest boards = travel
    "search_query": "AI technology",  # XHS search = AI
}

# Gate 1: T1 - 三平台推荐器均可实例化并调用 rank()
print("\n[Gate 1] T1: 三平台推荐器均可实例化并调用 rank()")
if import_ok:
    for platform in ["tiktok", "xiaohongshu", "pinterest"]:
        try:
            rec = get_recommender(platform)
            results_ranked = rec.rank(1, CANDIDATES, CONTEXT)
            gate(f"{platform} instantiates and ranks", len(results_ranked) == len(CANDIDATES), f"ranked {len(results_ranked)} items")
            gate(f"{platform} has score field", all("score" in r for r in results_ranked), "all items have score")
            gate(f"{platform} has score_breakdown", all("score_breakdown" in r for r in results_ranked), "all items have breakdown")
        except Exception as e:
            gate(f"{platform} instantiates and ranks", False, str(e))
            gate(f"{platform} has score field", False, "failed")
            gate(f"{platform} has score_breakdown", False, "failed")
else:
    for platform in ["tiktok", "xiaohongshu", "pinterest"]:
        gate(f"{platform} instantiates and ranks", False, "import failed")
        gate(f"{platform} has score field", False, "import failed")
        gate(f"{platform} has score_breakdown", False, "import failed")

# Gate 2: T2 - 相同候选集，不同推荐器排序有差异
print("\n[Gate 2] T2: 相同候选集，不同推荐器排序有差异")
if import_ok:
    try:
        tiktok_ranked = get_recommender("tiktok").rank(1, CANDIDATES, CONTEXT)
        xhs_ranked = get_recommender("xiaohongshu").rank(1, CANDIDATES, CONTEXT)
        pin_ranked = get_recommender("pinterest").rank(1, CANDIDATES, CONTEXT)

        tiktok_top3 = [r["post_id"] for r in tiktok_ranked[:3]]
        xhs_top3 = [r["post_id"] for r in xhs_ranked[:3]]
        pin_top3 = [r["post_id"] for r in pin_ranked[:3]]

        tiktok_vs_xhs_diff = tiktok_top3 != xhs_top3
        tiktok_vs_pin_diff = tiktok_top3 != pin_top3
        xhs_vs_pin_diff = xhs_top3 != pin_top3

        gate("TikTok vs 小红书 top-3 differs", tiktok_vs_xhs_diff, f"TikTok={tiktok_top3}, XHS={xhs_top3}")
        gate("TikTok vs Pinterest top-3 differs", tiktok_vs_pin_diff, f"TikTok={tiktok_top3}, Pinterest={pin_top3}")
        gate("小红书 vs Pinterest top-3 differs", xhs_vs_pin_diff, f"XHS={xhs_top3}, Pinterest={pin_top3}")

        # Save rank comparison
        rank_compare = {
            "candidates": [c["post_id"] for c in CANDIDATES],
            "context": CONTEXT,
            "rankings": {
                "tiktok": [{"post_id": r["post_id"], "score": r["score"], "breakdown": r["score_breakdown"]} for r in tiktok_ranked],
                "xiaohongshu": [{"post_id": r["post_id"], "score": r["score"], "breakdown": r["score_breakdown"]} for r in xhs_ranked],
                "pinterest": [{"post_id": r["post_id"], "score": r["score"], "breakdown": r["score_breakdown"]} for r in pin_ranked],
            }
        }
        with open(os.path.join(ARTIFACTS_DIR, "r4_03_rank_compare.json"), "w") as f:
            json.dump(rank_compare, f, indent=2, ensure_ascii=False)
        print(f"     Saved rank comparison to r4_03_rank_compare.json")
    except Exception as e:
        gate("TikTok vs 小红书 top-3 differs", False, str(e))
        gate("TikTok vs Pinterest top-3 differs", False, str(e))
        gate("小红书 vs Pinterest top-3 differs", False, str(e))
else:
    for g in ["TikTok vs 小红书 top-3 differs", "TikTok vs Pinterest top-3 differs", "小红书 vs Pinterest top-3 differs"]:
        gate(g, False, "import failed")

# Gate 3: T3 - 参数变化影响排序
print("\n[Gate 3] T3: 参数变化影响排序")
if import_ok:
    try:
        # Default TikTok
        default_ranked = get_recommender("tiktok").rank(1, CANDIDATES, CONTEXT)
        default_top3 = [r["post_id"] for r in default_ranked[:3]]

        # Modified: boost freshness weight heavily to force freshest content to top
        modified_config = {"short_term_weight": 0.05, "completion_weight": 0.05, "engagement_weight": 0.05, "freshness_weight": 0.85}
        modified_ranked = get_recommender("tiktok", modified_config).rank(1, CANDIDATES, CONTEXT)
        modified_top3 = [r["post_id"] for r in modified_ranked[:3]]

        gate("param change affects ranking", default_top3 != modified_top3, f"default={default_top3}, modified={modified_top3}")
        # Freshest candidates: p3(1h), p1(2h), p6(3h) - with 85% freshness weight, p3 should rank higher than default
        default_p3_rank = next((i for i, r in enumerate(default_ranked) if r["post_id"] == "p3"), 99)
        modified_p3_rank = next((i for i, r in enumerate(modified_ranked) if r["post_id"] == "p3"), 99)
        gate("freshness boost improves p3 rank", modified_p3_rank <= default_p3_rank, f"p3 rank: default={default_p3_rank}, modified={modified_p3_rank} (lower=better)")
    except Exception as e:
        gate("param change affects ranking", False, str(e))
        gate("freshness boost improves p3 rank", False, str(e))
else:
    gate("param change affects ranking", False, "import failed")
    gate("freshness boost improves p3 rank", False, "import failed")

# Gate 4: A/B 比较框架
print("\n[Gate 4] A/B 比较框架可运行")
if import_ok:
    try:
        ab_result = ab_compare(1, CANDIDATES, CONTEXT, top_k=3)
        gate("ab_compare returns report", "platforms" in ab_result, f"keys={list(ab_result.keys())}")
        gate("ab_compare has all 3 platforms", len(ab_result["platforms"]) == 3, f"platforms={list(ab_result['platforms'].keys())}")
        gate("ab_compare has overlap_analysis", "overlap_analysis" in ab_result, f"overlap keys={list(ab_result.get('overlap_analysis', {}).keys())}")
        gate("diversity_score > 0", ab_result.get("diversity_score", 0) > 0, f"diversity={ab_result.get('diversity_score')}")

        # Save AB report
        with open(os.path.join(ARTIFACTS_DIR, "r4_03_ab_result.json"), "w") as f:
            json.dump(ab_result, f, indent=2, ensure_ascii=False)
        print(f"     Saved AB result to r4_03_ab_result.json")
    except Exception as e:
        gate("ab_compare returns report", False, str(e))
        for g in ["ab_compare has all 3 platforms", "ab_compare has overlap_analysis", "diversity_score > 0"]:
            gate(g, False, str(e))
else:
    for g in ["ab_compare returns report", "ab_compare has all 3 platforms", "ab_compare has overlap_analysis", "diversity_score > 0"]:
        gate(g, False, "import failed")

# Gate 5: 推荐器切换不影响主链运行
print("\n[Gate 5] 推荐器切换不影响主链运行")
if import_ok:
    try:
        for platform in ["tiktok", "xiaohongshu", "pinterest"]:
            rec = get_recommender(platform)
            # Simulate switching mid-run
            ranked1 = rec.rank(1, CANDIDATES[:3], CONTEXT)
            ranked2 = rec.rank(2, CANDIDATES[3:], CONTEXT)
            gate(f"{platform} switch mid-run stable", len(ranked1) == 3 and len(ranked2) == 4, f"run1={len(ranked1)}, run2={len(ranked2)}")
    except Exception as e:
        gate("platform switch stable", False, str(e))
else:
    gate("platform switch stable", False, "import failed")

# Gate 6: 输出日志可解释排序原因
print("\n[Gate 6] 输出日志可解释排序原因（score_breakdown 字段）")
if import_ok:
    try:
        rec = get_recommender("tiktok")
        ranked = rec.rank(1, CANDIDATES, CONTEXT)
        first = ranked[0]
        breakdown = first.get("score_breakdown", {})
        expected_keys = {"short_term_interest", "completion_rate", "engagement", "freshness"}
        gate("TikTok breakdown has all keys", expected_keys.issubset(set(breakdown.keys())), f"keys={list(breakdown.keys())}")
        gate("breakdown values in [0,1]", all(0 <= v <= 1 for v in breakdown.values()), f"values={breakdown}")

        xhs_ranked = get_recommender("xiaohongshu").rank(1, CANDIDATES, CONTEXT)
        xhs_breakdown = xhs_ranked[0].get("score_breakdown", {})
        xhs_expected = {"content_quality", "social_affinity", "search_intent_match", "freshness"}
        gate("XHS breakdown has all keys", xhs_expected.issubset(set(xhs_breakdown.keys())), f"keys={list(xhs_breakdown.keys())}")

        pin_ranked = get_recommender("pinterest").rank(1, CANDIDATES, CONTEXT)
        pin_breakdown = pin_ranked[0].get("score_breakdown", {})
        pin_expected = {"long_term_interest", "board_similarity", "visual_or_topic_similarity", "freshness"}
        gate("Pinterest breakdown has all keys", pin_expected.issubset(set(pin_breakdown.keys())), f"keys={list(pin_breakdown.keys())}")
    except Exception as e:
        gate("TikTok breakdown has all keys", False, str(e))
        gate("breakdown values in [0,1]", False, str(e))
        gate("XHS breakdown has all keys", False, str(e))
        gate("Pinterest breakdown has all keys", False, str(e))
else:
    for g in ["TikTok breakdown has all keys", "breakdown values in [0,1]", "XHS breakdown has all keys", "Pinterest breakdown has all keys"]:
        gate(g, False, "import failed")

# Gate 7: API endpoint available
print("\n[Gate 7] REST API 接口可用")
import requests
try:
    r = requests.get("http://localhost:3000/api/recommender/platforms", timeout=5)
    data = r.json()
    gate("platforms API available", r.status_code == 200, f"HTTP {r.status_code}")
    gate("3 platforms listed", len(data.get("platforms", [])) == 3, f"count={len(data.get('platforms', []))}")
except Exception as e:
    gate("platforms API available", False, str(e))
    gate("3 platforms listed", False, str(e))

# Test rank API
try:
    payload = {
        "platform": "tiktok",
        "user_id": 1,
        "candidates": CANDIDATES[:3],
        "context": CONTEXT,
    }
    r = requests.post("http://localhost:3000/api/recommender/rank", json=payload, timeout=15)
    data = r.json()
    gate("rank API available", r.status_code == 200, f"HTTP {r.status_code}, keys={list(data.keys())}")
    gate("rank API returns ranked list", "ranked" in data and len(data["ranked"]) == 3, f"ranked count={len(data.get('ranked', []))}")
except Exception as e:
    gate("rank API available", False, str(e))
    gate("rank API returns ranked list", False, str(e))

# Summary
print("\n" + "=" * 60)
passed = sum(1 for v in results.values() if v["status"] == "PASS")
total = len(results)
print(f"R4-03 Gates: {passed}/{total} PASS")
print("=" * 60)

report = {
    "task": "R4-03",
    "gates": results,
    "summary": {"passed": passed, "total": total, "status": "PASS" if passed == total else "FAIL"}
}
with open(os.path.join(ARTIFACTS_DIR, "r4_03_gate_results.json"), "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"\nSaved gate results to r4_03_gate_results.json")

sys.exit(0 if passed == total else 1)
