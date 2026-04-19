#!/usr/bin/env python3
"""
手动测试 /api/sim/config 端点。

保留为轻量手工脚本，便于在本地联调时快速确认配置合同。
"""

import json
from typing import Any, Dict

import requests

BASE_URL = "http://localhost:8000"
CONFIG_ENDPOINT = f"{BASE_URL}/api/sim/config"


def create_test_config(agent_count: int = 10) -> Dict[str, Any]:
    return {
        "platform": "twitter",
        "agent_count": agent_count,
        "llm_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT",
            "temperature": 0.7,
            "max_tokens": 1000,
        },
    }


def create_reddit_config(agent_count: int = 15) -> Dict[str, Any]:
    return {
        "platform": "reddit",
        "agent_count": agent_count,
        "llm_config": {
            "model_platform": "DEEPSEEK",
            "model_type": "DEEPSEEK_CHAT",
            "temperature": 0.7,
        },
    }


def print_request(config: Dict[str, Any]) -> None:
    print("\nRequest:")
    print(f"  URL: {CONFIG_ENDPOINT}")
    print(f"  Payload: {json.dumps(config, indent=2, ensure_ascii=False)}")


def print_response(response: requests.Response) -> Dict[str, Any] | None:
    print("\nResponse:")
    print(f"  Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception:
        print(response.text)
        return None


def run_test(name: str, config: Dict[str, Any], expected_status: int) -> bool:
    print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    print_request(config)
    try:
        response = requests.post(CONFIG_ENDPOINT, json=config, timeout=30)
    except Exception as exc:
        print(f"\nRequest failed: {exc}")
        return False

    print_response(response)
    if response.status_code == expected_status:
        print("\nPASS")
        return True

    print(f"\nFAIL: expected {expected_status}, got {response.status_code}")
    return False


def main() -> None:
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        if health.status_code != 200:
            print(f"Health check failed: {health.status_code}")
            return
    except Exception:
        print("Cannot connect to backend at http://localhost:8000")
        return

    results = [
        run_test("Basic Twitter config", create_test_config(), 200),
        run_test("Basic Reddit config", create_reddit_config(), 200),
        run_test(
            "Invalid platform",
            {
                "platform": "invalid_platform",
                "agent_count": 10,
                "llm_config": {
                    "model_platform": "DEEPSEEK",
                    "model_type": "DEEPSEEK_CHAT",
                },
            },
            422,
        ),
    ]

    passed = sum(1 for result in results if result)
    print(f"\nSummary: {passed}/{len(results)} passed")


if __name__ == "__main__":
    main()
