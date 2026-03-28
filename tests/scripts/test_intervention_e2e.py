#!/usr/bin/env python3
"""
干预系统端到端测试

模拟完整的干预场景：
1. 初始化模拟
2. 运行几步建立基线
3. 在关键时机介入
4. 观察干预效果
"""

import asyncio
import sys
import os
import sqlite3

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def test_intervention_e2e():
    """端到端干预测试"""

    print("\n" + "🚀" * 30)
    print("  干预系统端到端测试")
    print("  模拟完整的干预场景")
    print("🚀" * 30)

    # 初始化引擎
    engine = RealOASISEngineV3(db_path="./test_intervention_e2e.db")

    # 阶段 1: 初始化并建立基线
    print("\n" + "=" * 60)
    print("📌 阶段 1: 初始化并建立基线")
    print("=" * 60)

    init_result = await engine.initialize(
        agent_count=15,
        platform="reddit",
        topic="MiddleEast"
    )

    if init_result["status"] != "ok":
        print(f"❌ 初始化失败: {init_result}")
        return False

    print(f"✅ 初始化成功: {init_result['agent_count']} agents")

    print("\n执行 5 步建立基线...")
    for i in range(5):
        result = await engine.step()
        print(f"  Step {i+1}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

    baseline_polarization = engine.last_polarization
    baseline_posts = engine.total_posts
    print(f"\n📊 基线指标:")
    print(f"  极化率: {baseline_polarization:.3f}")
    print(f"  帖子数: {baseline_posts}")

    # 阶段 2: 第一次干预（添加3个意见领袖）
    print("\n" + "=" * 60)
    print("📌 阶段 2: 第一次干预 - 添加3个意见领袖")
    print("=" * 60)

    print("\n添加意见领袖 1: 冲突解决专家")
    controlled_1 = await engine.add_controlled_agent(
        user_name="opinion_leader_1",
        content="I've studied this conflict for 20 years. Violence only breeds more violence. We need dialogue.",
        bio="Academic expert on conflict resolution"
    )

    if controlled_1["status"] != "ok":
        print(f"❌ 添加意见领袖 1 失败: {controlled_1}")
        return False

    print(f"✅ Added: {controlled_1['agent_id']} - {controlled_1['user_name']}")

    print("\n添加意见领袖 2: 人道主义工作者")
    controlled_2 = await engine.add_controlled_agent(
        user_name="opinion_leader_2",
        content="The human cost of this conflict is devastating. Let's prioritize humanitarian aid.",
        bio="Humanitarian worker"
    )

    if controlled_2["status"] != "ok":
        print(f"❌ 添加意见领袖 2 失败: {controlled_2}")
        return False

    print(f"✅ Added: {controlled_2['agent_id']} - {controlled_2['user_name']}")

    print("\n添加意见领袖 3: 经济学家")
    controlled_3 = await engine.add_controlled_agent(
        user_name="opinion_leader_3",
        content="Economic sanctions hurt ordinary people. Diplomacy is the only way forward.",
        bio="Economist specializing in sanctions"
    )

    if controlled_3["status"] != "ok":
        print(f"❌ 添加意见领袖 3 失败: {controlled_3}")
        return False

    print(f"✅ Added: {controlled_3['agent_id']} - {controlled_3['user_name']}")

    print(f"\n✅ 成功添加 3 个意见领袖: {controlled_1['agent_id']}, {controlled_2['agent_id']}, {controlled_3['agent_id']}")

    # 执行3步，观察效果
    print("\n执行 3 步，观察第一次干预效果...")
    for i in range(3):
        result = await engine.step()
        print(f"  Step {i+1}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

    intervention_1_polarization = engine.last_polarization
    print(f"\n📊 第一次干预后:")
    print(f"  极化率: {intervention_1_polarization:.3f}")
    print(f"  变化: {intervention_1_polarization - baseline_polarization:.3f}")

    # 阶段 3: 第二次干预（controlled agents 评论热门帖子）
    print("\n" + "=" * 60)
    print("📌 阶段 3: 第二次干预 - Controlled agents 评论热门帖子")
    print("=" * 60)

    # 获取最热的帖子（点赞数最多）
    conn = sqlite3.connect("./test_intervention_e2e.db")
    cursor = conn.cursor()
    cursor.execute("SELECT post_id FROM post ORDER BY num_likes DESC LIMIT 3")
    hot_posts = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"\n找到 3 个热门帖子: {hot_posts}")

    # 让 controlled agents 评论热门帖子
    print("\n让 controlled agents 评论热门帖子...")
    agent_ids = [controlled_1['agent_id'], controlled_2['agent_id'], controlled_3['agent_id']]

    for i, post_id in enumerate(hot_posts):
        agent_id = agent_ids[i]
        result = await engine.force_agent_comment(
            agent_id=agent_id,
            post_id=post_id,
            content=f"This is an evidence-based perspective on post {post_id}. Let's consider the facts and multiple viewpoints."
        )

        if result["status"] != "ok":
            print(f"❌ Agent {agent_id} 评论失败: {result}")
            return False

        print(f"  ✅ Agent {agent_id} commented on post {post_id}")

    # 再执行3步
    print("\n执行 3 步，观察第二次干预效果...")
    for i in range(3):
        result = await engine.step()
        print(f"  Step {i+1}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

    final_polarization = engine.last_polarization
    final_posts = engine.total_posts

    # 最终结果
    print("\n" + "=" * 60)
    print("📈 最终结果汇总")
    print("=" * 60)

    print(f"\n极化率变化:")
    print(f"  初始极化率: {baseline_polarization:.3f}")
    print(f"  第一次干预后: {intervention_1_polarization:.3f} (变化: {intervention_1_polarization - baseline_polarization:+.3f})")
    print(f"  最终极化率: {final_polarization:.3f} (变化: {final_polarization - baseline_polarization:+.3f})")

    print(f"\n帖子数量:")
    print(f"  初始: {baseline_posts}")
    print(f"  最终: {final_posts}")
    print(f"  增加: {final_posts - baseline_posts}")

    # 验证 controlled agents 列表
    print(f"\nControlled Agents 列表:")
    controlled = engine.list_controlled_agents()

    if controlled["status"] != "ok":
        print(f"❌ 获取 controlled agents 列表失败: {controlled}")
        return False

    print(f"  总数: {controlled['total']}")
    for agent in controlled['controlled_agents']:
        print(f"    - {agent['agent_id']}: {agent['user_name']}")

    # 验证数据库记录
    print(f"\n数据库记录验证:")
    conn = sqlite3.connect("./test_intervention_e2e.db")
    cursor = conn.cursor()

    # 验证 controlled agents 的帖子
    cursor.execute(
        "SELECT COUNT(*) FROM post WHERE user_id IN (?, ?, ?)",
        (controlled_1['agent_id'], controlled_2['agent_id'], controlled_3['agent_id'])
    )
    controlled_posts = cursor.fetchone()[0]
    print(f"  Controlled agents 帖子数: {controlled_posts}")

    # 验证 controlled agents 的评论
    cursor.execute(
        "SELECT COUNT(*) FROM comment WHERE user_id IN (?, ?, ?)",
        (controlled_1['agent_id'], controlled_2['agent_id'], controlled_3['agent_id'])
    )
    controlled_comments = cursor.fetchone()[0]
    print(f"  Controlled agents 评论数: {controlled_comments}")

    conn.close()

    # 清理
    print("\n" + "=" * 60)
    print("📌 清理测试环境")
    print("=" * 60)

    await engine.close()

    if os.path.exists("./test_intervention_e2e.db"):
        os.remove("./test_intervention_e2e.db")
        print("🗑️  测试数据库已删除")

    print("\n" + "🚀" * 30)
    print("  ✅ 端到端测试完成！")
    print("🚀" * 30)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_intervention_e2e())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试失败并抛出异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
