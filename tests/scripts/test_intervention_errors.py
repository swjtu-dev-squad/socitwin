#!/usr/bin/env python3
"""
干预系统错误处理测试

验证：
1. 不存在的 agent_id
2. 不存在的 post_id
3. 空内容处理
4. 重复添加 controlled agent
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def test_intervention_errors():
    """错误处理测试"""

    print("\n" + "=" * 60)
    print("🧪 干预系统错误处理测试")
    print("=" * 60)

    # 初始化引擎
    print("\n📌 初始化引擎")
    engine = RealOASISEngineV3(db_path="./test_intervention_errors.db")

    init_result = await engine.initialize(
        agent_count=3,
        platform="reddit",
        topic="AI"
    )

    if init_result["status"] != "ok":
        print(f"❌ 初始化失败: {init_result}")
        return False

    print(f"✅ 初始化成功: {init_result['agent_count']} agents")

    # 测试 1: 不存在的 agent_id (force_agent_post)
    print("\n📌 测试 1: 不存在的 agent_id (force_agent_post)")
    result = await engine.force_agent_post(
        agent_id=999,
        content="This should fail"
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    if "不存在" not in result["message"] and "not found" not in result["message"].lower():
        print(f"❌ 错误消息不正确: {result['message']}")
        return False

    print(f"✅ Invalid agent_id handled correctly")
    print(f"   Error message: {result['message']}")

    # 测试 2: 不存在的 agent_id (force_agent_comment)
    print("\n📌 测试 2: 不存在的 agent_id (force_agent_comment)")
    result = await engine.force_agent_comment(
        agent_id=999,
        post_id=1,
        content="This should fail"
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    print(f"✅ Invalid agent_id handled correctly (comment)")
    print(f"   Error message: {result['message']}")

    # 测试 3: 不存在的 post_id
    print("\n📌 测试 3: 不存在的 post_id")
    result = await engine.force_agent_comment(
        agent_id=0,
        post_id=9999,
        content="This should fail"
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    if "不存在" not in result["message"] and "not found" not in result["message"].lower():
        print(f"❌ 错误消息不正确: {result['message']}")
        return False

    print(f"✅ Invalid post_id handled correctly")
    print(f"   Error message: {result['message']}")

    # 测试 4: 空内容 (force_agent_post)
    print("\n📌 测试 4: 空内容 (force_agent_post)")
    result = await engine.force_agent_post(
        agent_id=0,
        content=""
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    if "空" not in result["message"] and "empty" not in result["message"].lower():
        print(f"❌ 错误消息不正确: {result['message']}")
        return False

    print(f"✅ Empty content handled correctly (post)")
    print(f"   Error message: {result['message']}")

    # 测试 5: 空内容 (force_agent_comment)
    print("\n📌 测试 5: 空内容 (force_agent_comment)")
    result = await engine.force_agent_comment(
        agent_id=0,
        post_id=1,
        content=""
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    print(f"✅ Empty content handled correctly (comment)")
    print(f"   Error message: {result['message']}")

    # 测试 6: 只有空格的内容
    print("\n📌 测试 6: 只有空格的内容")
    result = await engine.force_agent_post(
        agent_id=0,
        content="   "
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    print(f"✅ Whitespace-only content handled correctly")
    print(f"   Error message: {result['message']}")

    # 测试 7: 未初始化的环境
    print("\n📌 测试 7: 未初始化的环境")
    engine2 = RealOASISEngineV3(db_path="./test_intervention_errors2.db")

    result = await engine2.add_controlled_agent(
        user_name="test_agent",
        content="This should fail"
    )

    if result["status"] != "error":
        print(f"❌ 应该返回错误，但返回了: {result}")
        return False

    print(f"✅ Uninitialized environment handled correctly")
    print(f"   Error message: {result['message']}")

    # 清理
    print("\n📌 清理测试环境")
    await engine.close()

    if os.path.exists("./test_intervention_errors.db"):
        os.remove("./test_intervention_errors.db")
        print("🗑️  测试数据库已删除")

    if os.path.exists("./test_intervention_errors2.db"):
        os.remove("./test_intervention_errors2.db")

    print("\n" + "=" * 60)
    print("✅ 所有错误处理测试通过！")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_intervention_errors())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试失败并抛出异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
