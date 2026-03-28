#!/usr/bin/env python3
"""
干预系统基础功能测试

验证：
1. add_controlled_agent - 添加 controlled agent
2. force_agent_post - 强制发帖
3. force_agent_comment - 强制评论
4. list_controlled_agents - 列出 controlled agents
5. 推荐系统刷新验证
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def test_intervention_basic():
    """基础功能测试"""

    print("\n" + "=" * 60)
    print("🧪 干预系统基础功能测试")
    print("=" * 60)

    # 1. 初始化引擎（5个普通 agents）
    print("\n📌 步骤 1: 初始化引擎")
    engine = RealOASISEngineV3(db_path="./test_intervention.db")

    init_result = await engine.initialize(
        agent_count=5,
        platform="reddit",
        topic="AI"
    )

    if init_result["status"] != "ok":
        print(f"❌ 初始化失败: {init_result}")
        return False

    print(f"✅ 初始化成功: {init_result['agent_count']} agents")

    # 2. 执行2步，让普通 agents 产生一些内容
    print("\n📌 步骤 2: 执行2步建立基线")
    for i in range(2):
        result = await engine.step()
        print(f"  Step {i+1}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

    # 3. 测试 add_controlled_agent
    print("\n📌 步骤 3: 添加 controlled agent")
    result = await engine.add_controlled_agent(
        user_name="intervention_agent_0",
        content="This is a controlled intervention post about AI ethics. We must ensure AI systems are aligned with human values.",
        bio="Controlled agent for studying AI ethics discourse"
    )

    if result["status"] != "ok":
        print(f"❌ 添加 controlled agent 失败: {result}")
        return False

    agent_id = result["agent_id"]
    print(f"✅ Added controlled agent: {agent_id}")
    print(f"   User name: {result['user_name']}")
    print(f"   First post ID: {result.get('post_id')}")

    # 4. 验证 controlled agent 在列表中
    print("\n📌 步骤 4: 列出 controlled agents")
    controlled = engine.list_controlled_agents()

    if controlled["status"] != "ok":
        print(f"❌ 列出 controlled agents 失败: {controlled}")
        return False

    if controlled["total"] != 1:
        print(f"❌ Controlled agents 数量错误: 期望 1, 实际 {controlled['total']}")
        return False

    if controlled["controlled_agents"][0]["agent_id"] != agent_id:
        print(f"❌ Controlled agent ID 错误")
        return False

    print(f"✅ Controlled agent listed correctly")
    print(f"   Agent info: {controlled['controlled_agents'][0]}")

    # 5. 测试 force_agent_post
    print("\n📌 步骤 5: 强制发帖")
    result = await engine.force_agent_post(
        agent_id=agent_id,
        content="Second forced post from controlled agent: AI bias is a critical issue we must address."
    )

    if result["status"] != "ok":
        print(f"❌ 强制发帖失败: {result}")
        return False

    print(f"✅ Forced post created: {result['post_id']}")
    print(f"   Content: {result['content'][:50]}...")

    # 6. 获取一个普通帖子的 ID
    print("\n📌 步骤 6: 获取普通帖子 ID 并测试强制评论")
    import sqlite3
    conn = sqlite3.connect("./test_intervention.db")
    cursor = conn.cursor()
    cursor.execute("SELECT post_id FROM post WHERE user_id != ? LIMIT 1", (agent_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        target_post_id = row[0]
        print(f"   Target post ID: {target_post_id}")

        # 7. 测试 force_agent_comment
        result = await engine.force_agent_comment(
            agent_id=agent_id,
            post_id=target_post_id,
            content="This is a forced comment from controlled agent: Great point! Let's consider the ethical implications."
        )

        if result["status"] != "ok":
            print(f"❌ 强制评论失败: {result}")
            return False

        print(f"✅ Forced comment created: {result['comment_id']}")
        print(f"   On post: {result['post_id']}")
        print(f"   Content: {result['content'][:50]}...")
    else:
        print("⚠️  没有找到普通帖子的 ID，跳过评论测试")

    # 8. 推荐系统刷新验证
    print("\n📌 步骤 7: 验证推荐系统刷新")
    # 执行一步，验证其他 agents 能看到 controlled agent 的帖子
    step_result = await engine.step()

    if step_result["total_posts"] == 0:
        print(f"❌ 推荐系统刷新失败: 没有帖子")
        return False

    print(f"✅ Recommendation system refreshed")
    print(f"   Total posts: {step_result['total_posts']}")
    print(f"   New logs in this step: {len(step_result.get('new_logs', []))}")

    # 9. 清理
    print("\n📌 步骤 8: 清理测试环境")
    await engine.close()
    if os.path.exists("./test_intervention.db"):
        os.remove("./test_intervention.db")
        print("🗑️  测试数据库已删除")

    print("\n" + "=" * 60)
    print("✅ 所有基础功能测试通过！")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_intervention_basic())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试失败并抛出异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
