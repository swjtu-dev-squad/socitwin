#!/usr/bin/env python3
"""
最小化采样测试 - 快速验证采样机制是否生效
只运行2步，专注于检查采样日志
"""

import sys
import os
import time
import requests

# 配置
BASE_URL = "http://localhost:3000"
AGENT_COUNT = 20  # 小规模
STEPS = 2  # 只跑2步
SAMPLING_RATE = 0.1  # 10%采样，应该激活2个agents
SAMPLING_CONFIG = {
    "enabled": True,
    "rate": SAMPLING_RATE,
    "strategy": "random",
    "min_active": 2,
    "seed": 42,
}

print("=" * 60)
print("🔬 最小化采样测试")
print("=" * 60)
print(f"配置：")
print(f"  • Agents: {AGENT_COUNT}")
print(f"  • Steps: {STEPS}")
print(f"  • 采样率: {SAMPLING_RATE*100}%（应该激活 {int(AGENT_COUNT * SAMPLING_RATE)} 个agents）")
print()

# Step 1: 重置
print("🔄 步骤1：重置模拟")
try:
    response = requests.post(f"{BASE_URL}/api/sim/reset")
    response.raise_for_status()
    print("  ✅ 重置成功")
except Exception as e:
    print(f"  ❌ 重置失败: {e}")
    sys.exit(1)

# Step 2: 初始化（带采样配置）
print(f"\n🚀 步骤2：初始化 {AGENT_COUNT} 个agents（采样率 {SAMPLING_RATE*100}%）")
print(f"  🔍 DEBUG: 发送采样配置: {SAMPLING_CONFIG}")

try:
    start_time = time.time()
    response = requests.post(
        f"{BASE_URL}/api/sim/config",
        json={
            "agentCount": AGENT_COUNT,
            "platform": "reddit",
            "topics": ["AI"],
            "sampling_config": SAMPLING_CONFIG,
        },
        timeout=60
    )
    elapsed = time.time() - start_time
    response.raise_for_status()

    result = response.json()
    if result.get("status") == "ok":
        print(f"  ✅ 初始化成功 ({elapsed:.2f}s)")
        print(f"  🔍 DEBUG: 响应数据: {result.get('data', {})}")
    else:
        print(f"  ❌ 初始化失败: {result}")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ 初始化失败: {e}")
    sys.exit(1)

# Step 3-4: 运行2步
for step_num in range(1, STEPS + 1):
    print(f"\n⏳ 步骤{step_num + 2}：执行 Step {step_num}")

    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/sim/step",
            timeout=120
        )
        elapsed = time.time() - start_time
        response.raise_for_status()

        result = response.json()
        print(f"  ✅ Step {step_num} 完成 ({elapsed:.2f}s)")

        # 提取关键指标
        active_agents = result.get("activeAgents", "N/A")
        total_posts = result.get("totalPosts", "N/A")
        polarization = result.get("polarization", 0)

        print(f"  📊 指标:")
        print(f"     • Active agents: {active_agents}")
        print(f"     • Total posts: {total_posts}")
        print(f"     • Polarization: {polarization*100:.2f}%")

        # 判断采样是否生效
        if active_agents == AGENT_COUNT:
            print(f"  ⚠️  Warning: active_agents = {active_agents}（全部激活，采样可能未生效）")
        elif active_agents == int(AGENT_COUNT * SAMPLING_RATE):
            print(f"  ✅ 采样可能生效：active_agents = {active_agents}（符合预期）")
        else:
            print(f"  🔍 active_agents = {active_agents}（不确定是否采样生效）")

    except Exception as e:
        print(f"  ❌ Step {step_num} 失败: {e}")
        sys.exit(1)

# 总结
print("\n" + "=" * 60)
print("📊 测试总结")
print("=" * 60)
print("\n请检查服务器日志中是否包含以下关键信息：")
print()
print("✅ 采样配置接收（Python引擎）：")
print("   [OASIS Engine stderr] 🔍 DEBUG: Received sampling_config")
print("   [OASIS Engine stderr] 🎯 Sampling config: {'enabled': True, ...")
print()
print("✅ 采样应用（每个step）：")
print("   [OASIS Engine stderr] 🔍 DEBUG: Sampling enabled!")
print("   [OASIS Engine stderr] 🎯 Sampling: 2/20 agents (10.0%)")
print()
print("❌ 如果缺失上述日志，说明采样配置未传递到Python引擎")
print()
print("📋 下一步：查看服务器窗口的完整日志输出")
print("=" * 60)
