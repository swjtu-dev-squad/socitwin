#!/usr/bin/env python3
"""
测试强制创建帖子功能

验证：
1. 每一步都有20%的agents被强制创建帖子
2. 新帖子能持续生成
3. 不会出现所有agents都DO_NOTHING的情况
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def test_force_create():
    """测试强制创建帖子功能"""

    print("=" * 60)
    print("测试：强制部分Agents创建帖子")
    print("=" * 60)

    # 创建引擎
    engine = RealOASISEngineV3(
        db_path="./test_force_create.db"
    )

    # 初始化（5个agents）
    print("\n🚀 初始化引擎...")
    result = await engine.initialize(
        agent_count=5,
        platform="reddit",
        topic="地球是平的"
    )

    if result["status"] != "ok":
        print(f"❌ 初始化失败: {result}")
        return

    print("✅ 初始化成功")

    # 执行10步
    print("\n🎯 执行10步模拟...")

    for step_num in range(10):
        print(f"\n{'=' * 60}")
        print(f"第 {step_num + 1} 步")
        print('=' * 60)

        result = await engine.step()

        if result["status"] != "ok":
            print(f"❌ 步骤失败: {result}")
            break

        # 显示结果
        print(f"\n📊 步骤 {step_num + 1} 结果:")
        print(f"  - 总帖子数: {result['total_posts']}")
        print(f"  - 活跃agents: {result['active_agents']}")
        print(f"  - 极化率: {result.get('polarization', 0.0):.3f}")
        print(f"  - 执行时间: {result['step_time']:.2f}秒")

        # 显示新的日志
        if result.get('new_logs'):
            print(f"\n📝 新日志 ({len(result['new_logs'])} 条):")
            for log in result['new_logs'][:5]:  # 只显示前5条
                action = log.get('action', 'unknown')
                agent_id = log.get('agent_id', '?')
                content = log.get('content', '')
                if content:
                    content = content[:50] + '...' if len(content) > 50 else content
                    print(f"  - Agent {agent_id}: {action} - {content}")
                else:
                    print(f"  - Agent {agent_id}: {action}")

            if len(result['new_logs']) > 5:
                print(f"  ... 还有 {len(result['new_logs']) - 5} 条日志")

    # 统计
    print(f"\n{'=' * 60}")
    print("📈 最终统计:")
    print(f"  - 总步数: {engine.current_step}")
    print(f"  - 总帖子数: {engine.total_posts}")
    print(f"  - 平均每步帖子数: {engine.total_posts / engine.current_step:.1f}")

    # 关闭引擎
    await engine.close()
    print("\n✅ 测试完成")

    # 清理测试数据库
    if os.path.exists("./test_force_create.db"):
        os.remove("./test_force_create.db")
        print("🗑️  测试数据库已删除")


if __name__ == "__main__":
    asyncio.run(test_force_create())
