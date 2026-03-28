#!/usr/bin/env python3
"""
干预系统快速演示

展示如何使用配置文件批量添加不同类型的 controlled agents
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def demo():
    """演示干预系统"""

    print("\n" + "="*60)
    print("🎭 干预系统快速演示")
    print("="*60)

    # 1. 初始化
    print("\n📌 步骤 1: 初始化模拟（10 个普通 agents，话题：MiddleEast）")
    engine = RealOASISEngineV3(db_path="./demo_intervention.db")

    await engine.initialize(
        agent_count=10,
        platform="reddit",
        topic="MiddleEast"
    )

    print("✅ 初始化完成")

    # 2. 建立基线（执行 2 步）
    print("\n📌 步骤 2: 建立 2 步基线")
    for i in range(2):
        result = await engine.step()
        print(f"  Step {i+1}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

    baseline_pol = result.get('polarization', 0.0)

    # 3. 添加干预（3 种类型）
    print("\n📌 步骤 3: 添加 3 种类型的 controlled agents")
    print("  - peace_messenger (和平使者)")
    print("  - fact_checker (事实核查员)")
    print("  - moderator (中立调解员)")

    result = await engine.add_controlled_agents_batch(
        intervention_types=["peace_messenger", "fact_checker", "moderator"],
        initial_step=True
    )

    if result["status"] != "ok":
        print(f"❌ 添加干预失败: {result}")
        return

    print(f"✅ 成功添加 {result['total']} 个 controlled agents")
    for agent in result["created_agents"]:
        print(f"  ✓ Agent {agent['agent_id']}: {agent['user_name']} ({agent['type']})")

    # 4. 继续执行 3 步
    print("\n📌 步骤 4: 执行 3 步观察效果")
    for i in range(3):
        result = await engine.step()
        pol = result.get('polarization', 0.0)
        change = pol - baseline_pol
        print(f"  Step {i+3}: Polarization={pol:.3f} (变化: {change:+.3f})")

    # 5. 最终结果
    final_pol = engine.last_polarization
    print("\n📊 效果总结:")
    print(f"  基线极化率: {baseline_pol:.3f}")
    print(f"  最终极化率: {final_pol:.3f}")
    print(f"  变化: {final_pol - baseline_pol:+.3f}")

    # 6. 列出所有 controlled agents
    controlled = engine.list_controlled_agents()
    print(f"\n📋 Controlled Agents 总览:")
    for agent in controlled["controlled_agents"]:
        print(f"  - Agent {agent['agent_id']}: {agent['user_name']}")

    # 清理
    print("\n📌 清理")
    await engine.close()
    if os.path.exists("./demo_intervention.db"):
        os.remove("./demo_intervention.db")
        print("✅ 演示完成！")

    return True


if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
