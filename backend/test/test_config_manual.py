#!/usr/bin/env python3
"""
手动测试 /api/sim/config 端点

这个脚本用于手动测试配置端点，使用 DeepSeek API。
运行前确保后端服务正在运行。

Usage:
    python test_config_manual.py
"""

import json
from typing import Any, Dict

import requests

# ============================================================================
# 配置
# ============================================================================

BASE_URL = "http://localhost:8000"
CONFIG_ENDPOINT = f"{BASE_URL}/api/sim/config"


# ============================================================================
# 测试配置
# ============================================================================

def create_test_config(agent_count: int = 10) -> Dict[str, Any]:
    """创建测试配置"""
    return {
        "platform": "twitter",
        "agent_count": agent_count,
        "model_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT",
            "temperature": 0.7,
            "max_tokens": 1000
        }
    }


def create_reddit_config(agent_count: int = 15) -> Dict[str, Any]:
    """创建 Reddit 测试配置"""
    return {
        "platform": "reddit",
        "agent_count": agent_count,
        "model_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT",
            "temperature": 0.7
        }
    }


# ============================================================================
# 测试函数
# ============================================================================

def print_test_header(test_name: str):
    """打印测试标题"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print('='*60)


def print_request(config: Dict[str, Any]):
    """打印请求详情"""
    print("\n📤 请求:")
    print(f"   URL: {CONFIG_ENDPOINT}")
    print(f"   配置: {json.dumps(config, indent=2, ensure_ascii=False)}")


def print_response(response: requests.Response):
    """打印响应详情"""
    print("\n📥 响应:")
    print(f"   状态码: {response.status_code}")
    try:
        data = response.json()
        print(f"   数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        return data
    except Exception:
        print(f"   内容: {response.text}")
        return None


def test_basic_config():
    """测试基本配置"""
    print_test_header("基本配置测试")

    config = create_test_config(agent_count=10)
    print_request(config)

    try:
        response = requests.post(CONFIG_ENDPOINT, json=config, timeout=30)
        data = print_response(response)

        if response.status_code == 200 and data and data.get("success"):
            print("\n✅ 测试通过")
            return True
        else:
            print("\n❌ 测试失败")
            return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_reddit_config():
    """测试 Reddit 配置"""
    print_test_header("Reddit 配置测试")

    config = create_reddit_config(agent_count=15)
    print_request(config)

    try:
        response = requests.post(CONFIG_ENDPOINT, json=config, timeout=30)
        data = print_response(response)

        if response.status_code == 200 and data and data.get("success"):
            print("\n✅ 测试通过")
            return True
        else:
            print("\n❌ 测试失败")
            return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_invalid_platform():
    """测试无效平台"""
    print_test_header("无效平台测试")

    config = {
        "platform": "invalid_platform",
        "agent_count": 10,
        "model_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT"
        }
    }
    print_request(config)

    try:
        response = requests.post(CONFIG_ENDPOINT, json=config, timeout=30)
        print_response(response)

        # 期望返回 422 验证错误
        if response.status_code == 422:
            print("\n✅ 测试通过（正确返回验证错误）")
            return True
        else:
            print(f"\n❌ 测试失败（期望 422，实际 {response.status_code}）")
            return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_default_values():
    """测试默认值"""
    print_test_header("默认值测试")

    config = {
        "platform": "twitter"
        # 缺少 agent_count 和 model_config，应该使用默认值
    }
    print_request(config)

    try:
        response = requests.post(CONFIG_ENDPOINT, json=config, timeout=30)
        data = print_response(response)

        if response.status_code == 200 and data and data.get("success"):
            # 检查是否使用了默认值
            agent_count = data.get("config", {}).get("agent_count")
            if agent_count == 5:  # 默认值应该是 5
                print("\n✅ 测试通过（正确使用默认值）")
                return True
            else:
                print(f"\n❌ 测试失败（期望默认值 5，实际 {agent_count}）")
                return False
        else:
            print("\n❌ 测试失败")
            return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_invalid_agent_count():
    """测试无效智能体数量"""
    print_test_header("无效智能体数量测试")

    config = {
        "platform": "twitter",
        "agent_count": -1,  # 无效值
        "model_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT"
        }
    }
    print_request(config)

    try:
        response = requests.post(CONFIG_ENDPOINT, json=config, timeout=30)
        print_response(response)

        if response.status_code == 422:
            print("\n✅ 测试通过（正确返回验证错误）")
            return True
        else:
            print(f"\n❌ 测试失败（期望 422，实际 {response.status_code}）")
            return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ============================================================================
# 主函数
# ============================================================================

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试 /api/sim/config 端点")
    print("="*60)

    # 检查服务器是否运行
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"\n⚠️  警告: 服务器健康检查失败（状态码 {response.status_code}）")
            print("请确保后端服务正在运行")
            return
    except Exception:
        print("\n❌ 错误: 无法连接到后端服务")
        print("请确保后端服务正在运行在 http://localhost:8000")
        return

    # 运行测试
    tests = [
        ("基本配置", test_basic_config),
        ("Reddit配置", test_reddit_config),
        ("无效平台", test_invalid_platform),
        ("默认值", test_default_values),
        ("无效智能体数量", test_invalid_agent_count),
    ]

    results = {}
    for name, test_func in tests:
        results[name] = test_func()

    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")


if __name__ == "__main__":
    main()
