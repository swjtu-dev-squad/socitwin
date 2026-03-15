#!/usr/bin/env python3
"""
详细分析 Agents 的行为模式

追踪并统计每个 agent 在每一步选择的所有动作类型
"""

import asyncio
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def analyze_agent_behavior():
    """分析 agent 行为模式"""

    print("=" * 60)
    print("Agent 行为模式分析")
    print("=" * 60)

    # 创建引擎
    engine = RealOASISEngineV3(
        model_platform="ollama",
        model_type="qwen3:8b",
        db_path="./behavior_analysis.db"
    )

    # 初始化
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

    # 行为统计
    action_counter = Counter()
    agent_actions = {}  # 使用字典，支持任意agent_id
    action_details = []

    # 执行3步（快速测试）
    print("\n🎯 执行3步模拟并追踪行为...")

    for step_num in range(3):
        print(f"\n{'=' * 60}")
        print(f"第 {step_num + 1} 步")
        print('=' * 60)

        result = await engine.step()

        if result["status"] != "ok":
            print(f"❌ 步骤失败: {result}")
            break

        # 分析新日志
        new_logs = result.get('new_logs', [])

        if not new_logs:
            print("⚠️  本步没有新的行为日志")
        else:
            print(f"\n📊 本步行为统计:")

            step_actions = Counter()

            for log in new_logs:
                action = log.get('action_type', log.get('action', 'unknown'))
                agent_id = log.get('agent_id', '?')

                # 统计
                action_counter[action] += 1
                if agent_id not in agent_actions:
                    agent_actions[agent_id] = Counter()
                agent_actions[agent_id][action] += 1
                step_actions[action] += 1

                # 记录详情
                action_details.append({
                    'step': step_num + 1,
                    'agent_id': agent_id,
                    'action': action,
                    'content': log.get('content', '')[:100]
                })

            # 显示本步统计
            for action, count in step_actions.most_common():
                print(f"  - {action}: {count} 次")

            # 显示具体行为
            print(f"\n📝 具体行为:")
            for log in new_logs[:10]:  # 最多显示10条
                agent_id = log.get('agent_id', '?')
                action = log.get('action_type', log.get('action', 'unknown'))
                content = log.get('content', '')
                if content:
                    content = content[:60] + '...' if len(content) > 60 else content
                    print(f"  Agent {agent_id} | {action:15s} | {content}")
                else:
                    print(f"  Agent {agent_id} | {action:15s} |")

    # 总结报告
    print(f"\n{'=' * 60}")
    print("📈 行为模式总结")
    print('=' * 60)

    print("\n1️⃣  整体动作统计:")
    for action, count in action_counter.most_common():
        percentage = (count / action_counter.total()) * 100
        print(f"  - {action:20s}: {count:3d} 次 ({percentage:5.1f}%)")

    print("\n2️⃣  每个 Agent 的行为:")
    for agent_id in sorted(agent_actions.keys()):
        print(f"\n  Agent {agent_id}:")
        for action, count in agent_actions[agent_id].most_common():
            print(f"    - {action:20s}: {count:2d} 次")

    print("\n3️⃣  行为多样性分析:")
    unique_actions = len(action_counter)
    print(f"  - 使用的动作类型数: {unique_actions}")
    print(f"  - 预期动作类型: 3 (CREATE_POST, LIKE_POST, REFRESH)")

    if unique_actions == 1:
        only_action = list(action_counter.keys())[0]
        print(f"  ⚠️  警告: Agents 只使用了 {only_action} 动作！")
        print(f"  原因可能是:")
        print(f"    - LLM 倾向于选择这个动作")
        print(f"    - 其他动作的条件不满足")
        print(f"    - System prompt 鼓励这种行为")

    # 关闭引擎
    await engine.close()

    # 清理
    if os.path.exists("./behavior_analysis.db"):
        os.remove("./behavior_analysis.db")

    print("\n✅ 分析完成")


if __name__ == "__main__":
    asyncio.run(analyze_agent_behavior())
