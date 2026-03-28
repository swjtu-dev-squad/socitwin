#!/usr/bin/env python3
"""
干预系统配置文件测试

验证：
1. 从 prompts/intervention.json 加载配置
2. 批量添加不同类型的 controlled agents
3. 验证干预效果
"""

import asyncio
import sys
import os
import argparse

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def test_intervention_with_config():
    """使用配置文件测试干预系统"""

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="干预系统配置文件测试")
    parser.add_argument("--types", default="peace_messenger,fact_checker,moderator",
                       help="干预类型列表（逗号分隔）")
    parser.add_argument("--step", type=int, default=2,
                       help="在第几步添加干预（默认：2）")
    parser.add_argument("--num-normal-agents", type=int, default=10,
                       help="普通 agents 数量（默认：10）")
    parser.add_argument("--num-steps", type=int, default=5,
                       help="总步骤数（默认：5）")

    args = parser.parse_args()
    intervention_types = args.types.split(",")

    print("\n" + "=" * 60)
    print("🧪 干预系统配置文件测试")
    print("=" * 60)
    print(f"\n配置:")
    print(f"  普通 agents: {args.num_normal_agents}")
    print(f"  干预类型: {', '.join(intervention_types)}")
    print(f"  干预步骤: 第 {args.step} 步")
    print(f"  总步骤数: {args.num_steps}")

    # 初始化引擎
    print(f"\n📌 初始化引擎...")
    engine = RealOASISEngineV3(db_path="./test_intervention_config.db")

    init_result = await engine.initialize(
        agent_count=args.num_normal_agents,
        platform="reddit",
        topic="MiddleEast"  # 使用有争议的话题
    )

    if init_result["status"] != "ok":
        print(f"❌ 初始化失败: {init_result}")
        return False

    print(f"✅ 初始化成功: {init_result['agent_count']} agents")

    # 执行步骤到干预点
    if args.step > 1:
        print(f"\n📌 执行前 {args.step - 1} 步建立基线...")
        for i in range(1, args.step):
            result = await engine.step()
            print(f"  Step {i}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

        baseline_polarization = engine.last_polarization
        baseline_posts = engine.total_posts
        print(f"\n基线指标:")
        print(f"  极化率: {baseline_polarization:.3f}")
        print(f"  帖子数: {baseline_posts}")
    else:
        baseline_polarization = 0.0
        baseline_posts = 0

    # 添加干预
    print(f"\n📌 在第 {args.step} 步添加干预...")
    print(f"干预类型: {', '.join(intervention_types)}")

    intervention_result = await engine.add_controlled_agents_batch(
        intervention_types=intervention_types,
        initial_step=True
    )

    if intervention_result["status"] != "ok":
        print(f"❌ 添加干预失败: {intervention_result}")
        return False

    print(f"✅ 干预添加成功: {intervention_result['total']} 个 controlled agents")

    for agent_info in intervention_result["created_agents"]:
        print(f"  - Agent {agent_info['agent_id']}: {agent_info['user_name']}")
        print(f"    类型: {agent_info['type']}")
        print(f"    描述: {agent_info['description']}")
        if "post_id" in agent_info:
            print(f"    首帖子 ID: {agent_info['post_id']}")

    # 继续执行剩余步骤
    remaining_steps = args.num_steps - args.step
    if remaining_steps > 0:
        print(f"\n📌 执行剩余 {remaining_steps} 步...")
        for i in range(remaining_steps):
            step_num = args.step + i
            result = await engine.step()
            print(f"  Step {step_num}: Posts={result['total_posts']}, Polarization={result.get('polarization', 0.0):.3f}")

    # 最终结果
    final_polarization = engine.last_polarization
    final_posts = engine.total_posts

    print(f"\n" + "=" * 60)
    print("📈 最终结果")
    print("=" * 60)

    print(f"\n极化率变化:")
    if args.step > 1:
        print(f"  初始极化率: {baseline_polarization:.3f}")
        print(f"  最终极化率: {final_polarization:.3f}")
        print(f"  变化: {final_polarization - baseline_polarization:.3f}")
    else:
        print(f"  最终极化率: {final_polarization:.3f}")

    print(f"\n帖子数量:")
    if args.step > 1:
        print(f"  初始: {baseline_posts}")
    print(f"  最终: {final_posts}")
    if args.step > 1:
        print(f"  增加: {final_posts - baseline_posts}")

    # 列出 controlled agents
    controlled = engine.list_controlled_agents()
    print(f"\nControlled Agents: {controlled['total']}")
    for agent in controlled['controlled_agents']:
        print(f"  - Agent {agent['agent_id']}: {agent['user_name']}")

    # 清理
    print(f"\n📌 清理测试环境")
    await engine.close()

    if os.path.exists("./test_intervention_config.db"):
        os.remove("./test_intervention_config.db")
        print("🗑️  测试数据库已删除")

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_intervention_with_config())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试失败并抛出异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
