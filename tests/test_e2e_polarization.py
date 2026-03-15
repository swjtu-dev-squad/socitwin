"""
End-to-end integration test for Polarization Analyzer

Tests the complete flow from engine initialization to polarization calculation.
"""

import pytest
import tempfile
from pathlib import Path


@pytest.mark.asyncio
async def test_polarization_integration_flow():
    """
    测试极化率分析的完整集成流程

    验证：
    1. 初始化引擎时极化分析器正确创建
    2. Step方法返回polarization字段
    3. 数据库缓存正确创建和使用
    """
    from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3
    from oasis_dashboard.context.config import ModelRuntimeSpec

    # 创建临时数据库路径
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "test.db")

        # 创建引擎实例
        engine = RealOASISEngineV3(
            model_platform="ollama",
            model_type="qwen3:8b",
            db_path=db_path
        )

        # 初始化（带topic）
        result = await engine.initialize(
            agent_count=5,
            platform="reddit",
            topic="地球是平的"
        )

        # 验证初始化成功
        assert result["status"] == "ok"
        assert engine.polarization_analyzer is not None
        assert engine.polarization_topic == "地球是平的"

        print("✅ 极化率分析器已成功初始化")

        # 验证step返回polarization字段
        # （由于可能没有实际帖子，polarization可能是0或使用降级策略）
        step_result = await engine.step()

        assert "polarization" in step_result
        assert isinstance(step_result["polarization"], (int, float))
        assert 0 <= step_result["polarization"] <= 1

        print(f"✅ Step返回极化率: {step_result['polarization']:.3f}")

        # 验证数据库缓存表存在
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='polarization_cache'
        """)
        result = cursor.fetchone()
        conn.close()

        assert result is not None, "缓存表应该被创建"

        print("✅ 数据库缓存表已创建")

        # 关闭引擎
        await engine.close()

        print("✅ 端到端集成测试通过")


@pytest.mark.asyncio
async def test_polarization_without_topic():
    """
    测试没有topic时的行为

    当topic为"general"时，不应该初始化极化分析器
    """
    from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3

    # 创建临时数据库路径
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "test.db")

        # 创建引擎实例
        engine = RealOASISEngineV3(
            model_platform="ollama",
            model_type="qwen3:8b",
            db_path=db_path
        )

        # 初始化（不带topic或使用general）
        result = await engine.initialize(
            agent_count=3,
            platform="reddit",
            topic="general"  # general topic
        )

        # 验证初始化成功
        assert result["status"] == "ok"

        # general topic不应该初始化极化分析器
        assert engine.polarization_analyzer is None

        # step应该返回polarization=0
        step_result = await engine.step()

        assert "polarization" in step_result
        assert step_result["polarization"] == 0.0

        print("✅ 无topic场景测试通过")

        # 关闭引擎
        await engine.close()


def test_polarization_metrics_calculation():
    """
    测试极化率计算的正确性

    不依赖LLM，只测试数学计算部分
    """
    from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

    # 测试用例
    test_cases = [
        {
            "name": "极端极化",
            "stances": [0.0, 0.0, 1.0, 1.0],
            "expected_polarization_range": (0.6, 1.0),
            "expected_std_range": (0.4, 0.6),
        },
        {
            "name": "完全中立",
            "stances": [0.5, 0.5, 0.5, 0.5, 0.5],
            "expected_polarization_range": (0.0, 0.1),
            "expected_std_range": (0.0, 0.1),
        },
        {
            "name": "轻度偏颇",
            "stances": [0.3, 0.4, 0.6, 0.7],
            "expected_polarization_range": (0.15, 0.25),
            "expected_std_range": (0.1, 0.2),
        },
    ]

    all_passed = True

    for test_case in test_cases:
        result = PolarizationAnalyzer._calculate_polarization_metrics(
            None,
            test_case["stances"]
        )

        pol = result["polarization"]
        std = result["std"]
        pol_min, pol_max = test_case["expected_polarization_range"]
        std_min, std_max = test_case["expected_std_range"]

        # 验证极化率
        if not (pol_min <= pol <= pol_max):
            print(
                f"❌ {test_case['name']} 极化率超出范围: "
                f"{pol:.3f} 不在 [{pol_min}, {pol_max}]"
            )
            all_passed = False
        else:
            print(f"✅ {test_case['name']} 极化率: {pol:.3f} (符合预期)")

        # 验证标准差
        if not (std_min <= std <= std_max):
            print(
                f"❌ {test_case['name']} 标准差超出范围: "
                f"{std:.3f} 不在 [{std_min}, {std_max}]"
            )
            all_passed = False
        else:
            print(f"✅ {test_case['name']} 标准差: {std:.3f} (符合预期)")

    assert all_passed, "部分测试用例失败"

    print("✅ 极化率计算测试全部通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
