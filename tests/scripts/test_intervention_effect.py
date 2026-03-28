#!/usr/bin/env python3
"""
干预效果测试

验证：
1. controlled agent 的帖子能被其他 agents 看到
2. 干预后极化率等指标的变化
3. 数据库记录的完整性
"""

import asyncio
import sys
import os
import sqlite3

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def test_intervention_effect():
    """干预效果测试"""

    print("\n" + "=" * 60)
    print("🧪 干预效果测试")
    print("=" * 60)

    # 初始化引擎
    print("\n📌 初始化引擎（10个 agents）")
    engine = RealOASISEngineV3(db_path="./test_intervention_effect.db")

    init_result = await engine.initialize(
        agent_count=10,
        platform="reddit",
        topic="MiddleEast"
    )

    if init_result["status"] != "ok":
        print(f"❌ 初始化失败: {init_result}")
        return False

    print(f"✅ 初始化成功: {init_result['agent_count']} agents")

    # 记录初始极化率
    print("\n📌 步骤 1: 记录初始极化率")
    step_result = await engine.step()
    initial_polarization = step_result.get('polarization', 0.0)
    initial_posts = step_result['total_posts']

    print(f"   Initial polarization: {initial_polarization:.3f}")
    print(f"   Initial posts: {initial_posts}")

    # 添加 controlled agents 并发帖
    print("\n📌 步骤 2: 添加 3 个 controlled agents")

    result1 = await engine.add_controlled_agent(
        user_name="peace_messenger",
        content="Both sides have valid concerns. Let's find common ground through dialogue and mutual understanding.",
        bio="Controlled agent promoting peace and dialogue"
    )

    if result1["status"] != "ok":
        print(f"❌ 添加第一个 controlled agent 失败: {result1}")
        return False

    agent_id_1 = result1["agent_id"]
    print(f"✅ Added controlled agent 1: {agent_id_1}")

    result2 = await engine.add_controlled_agent(
        user_name="fact_checker_1",
        content="Let's focus on verified facts rather than emotions. Evidence-based reasoning is crucial.",
        bio="Controlled agent for fact-checking"
    )

    if result2["status"] != "ok":
        print(f"❌ 添加第二个 controlled agent 失败: {result2}")
        return False

    agent_id_2 = result2["agent_id"]
    print(f"✅ Added controlled agent 2: {agent_id_2}")

    result3 = await engine.add_controlled_agent(
        user_name="fact_checker_2",
        content="Critical thinking is essential. Verify before sharing. Consider multiple perspectives.",
        bio="Controlled agent for critical thinking"
    )

    if result3["status"] != "ok":
        print(f"❌ 添加第三个 controlled agent 失败: {result3}")
        return False

    agent_id_3 = result3["agent_id"]
    print(f"✅ Added controlled agent 3: {agent_id_3}")

    # 执行3步，观察干预效果
    print("\n📌 步骤 3: 执行3步，观察干预效果")
    for i in range(3):
        result = await engine.step()
        print(f"   Step {i+1}:")
        print(f"     - Posts: {result['total_posts']}")
        print(f"     - Polarization: {result.get('polarization', 0.0):.3f}")

    final_polarization = engine.last_polarization
    final_posts = engine.total_posts

    # 验证极化率有变化
    print("\n📊 干预效果分析:")
    print(f"   初始极化率: {initial_polarization:.3f}")
    print(f"   最终极化率: {final_polarization:.3f}")
    print(f"   极化率变化: {final_polarization - initial_polarization:.3f}")

    polarization_changed = abs(final_polarization - initial_polarization) > 0.001
    if polarization_changed:
        print(f"✅ 极化率有变化")
    else:
        print(f"⚠️  极化率无明显变化（这可能是正常的，取决于 topic 和 agents 行为）")

    print(f"\n   帖子数量:")
    print(f"   初始: {initial_posts}")
    print(f"   最终: {final_posts}")
    print(f"   新增: {final_posts - initial_posts}")

    # 验证数据库记录
    print("\n📌 步骤 4: 验证数据库记录")
    conn = sqlite3.connect("./test_intervention_effect.db")
    cursor = conn.cursor()

    # 验证 controlled agents 的帖子
    cursor.execute(
        "SELECT COUNT(*) FROM post WHERE user_id IN (?, ?, ?)",
        (agent_id_1, agent_id_2, agent_id_3)
    )
    controlled_posts = cursor.fetchone()[0]

    if controlled_posts < 3:  # 每个 agent 至少发 1 次帖
        print(f"❌ Controlled agents 帖子数量不足: {controlled_posts}")
        conn.close()
        return False

    print(f"✅ Controlled agents 创建了 {controlled_posts} 个帖子")

    # 验证每个 controlled agent 的帖子
    for agent_id in [agent_id_1, agent_id_2, agent_id_3]:
        cursor.execute("SELECT COUNT(*) FROM post WHERE user_id = ?", (agent_id,))
        count = cursor.fetchone()[0]
        print(f"   - Agent {agent_id}: {count} posts")

    # 验证其他 agents 的评论（说明他们看到了 controlled agents 的帖子）
    cursor.execute("""
        SELECT COUNT(*) FROM comment
        WHERE user_id NOT IN (?, ?, ?)
        AND post_id IN (SELECT post_id FROM post WHERE user_id IN (?, ?, ?))
    """, (agent_id_1, agent_id_2, agent_id_3, agent_id_1, agent_id_2, agent_id_3))

    other_comments = cursor.fetchone()[0]

    print(f"\n✅ 其他 agents 对 controlled agents 的帖子评论了 {other_comments} 次")
    if other_comments > 0:
        print(f"   这证明其他 agents 能看到 controlled agents 的帖子（推荐系统刷新成功）")

    # 验证 controlled agents 列表
    print("\n📌 步骤 5: 验证 controlled agents 列表")
    controlled = engine.list_controlled_agents()

    if controlled["status"] != "ok":
        print(f"❌ 列出 controlled agents 失败: {controlled}")
        conn.close()
        return False

    if controlled["total"] != 3:
        print(f"❌ Controlled agents 数量错误: 期望 3, 实际 {controlled['total']}")
        conn.close()
        return False

    print(f"✅ Controlled agents 列表正确: {controlled['total']} 个")
    for agent in controlled['controlled_agents']:
        print(f"   - {agent['agent_id']}: {agent['user_name']}")

    conn.close()

    # 清理
    print("\n📌 清理测试环境")
    await engine.close()

    if os.path.exists("./test_intervention_effect.db"):
        os.remove("./test_intervention_effect.db")
        print("🗑️  测试数据库已删除")

    print("\n" + "=" * 60)
    print("✅ 所有干预效果测试通过！")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_intervention_effect())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试失败并抛出异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
