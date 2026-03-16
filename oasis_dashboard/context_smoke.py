from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def run_context_smoke(args: argparse.Namespace) -> dict[str, Any]:
    engine = RealOASISEngineV3(
        model_platform=args.model_platform,
        model_type=args.model_type,
        db_path=args.db_path,
    )
    try:
        init_result = await engine.initialize(
            agent_count=args.agent_count,
            platform=args.platform,
            recsys=args.recsys,
            topic=args.topic,
            topics=args.topics or None,
            regions=args.regions or None,
        )
        if init_result.get("status") != "ok":
            raise RuntimeError(init_result.get("message", "engine initialize failed"))

        steps: list[dict[str, Any]] = []
        for _ in range(args.steps):
            step_result = await engine.step()
            if step_result.get("status") != "ok":
                raise RuntimeError(step_result.get("message", "engine step failed"))
            steps.append(
                {
                    "step": step_result["current_step"],
                    "total_posts": step_result["total_posts"],
                    "step_time": step_result["step_time"],
                    "context_metrics": step_result["context_metrics"],
                }
            )

        return {
            "init": {
                "agent_count": init_result["agent_count"],
                "platform": init_result["platform"],
                "topics": init_result["topics"],
                "regions": init_result["regions"],
            "context_token_limit": init_result.get("context_token_limit"),
            "generation_max_tokens": init_result.get("generation_max_tokens"),
            "memory_window_size": init_result.get("memory_window_size"),
        },
        "steps": steps,
    }
    finally:
        await engine.reset()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a small OASIS context smoke test."
    )
    parser.add_argument(
        "--model-platform",
        default=os.environ.get("OASIS_MODEL_PLATFORM", "ollama"),
    )
    parser.add_argument(
        "--model-type",
        default=os.environ.get("OASIS_MODEL_TYPE", "qwen3:8b"),
    )
    parser.add_argument("--db-path", default="/tmp/oasis-context-smoke.db")
    parser.add_argument("--agent-count", type=int, default=2)
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--platform", choices=["reddit", "twitter"], default="reddit")
    parser.add_argument("--recsys", default="hot-score")
    parser.add_argument("--topic", default="general")
    parser.add_argument("--topics", nargs="*")
    parser.add_argument("--regions", nargs="*")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = asyncio.run(run_context_smoke(args))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    init = result["init"]
    print(
        "context smoke init:",
        f"agents={init['agent_count']}",
        f"platform={init['platform']}",
        f"context_limit={init['context_token_limit']}",
        f"generation_max_tokens={init['generation_max_tokens']}",
        f"memory_window_size={init['memory_window_size']}",
    )
    for step in result["steps"]:
        metrics = step["context_metrics"]
        print(
            "step",
            step["step"],
            f"posts={step['total_posts']}",
            f"time={step['step_time']:.2f}s",
            f"context_avg={metrics['avg_context_tokens']}",
            f"context_max={metrics['max_context_tokens']}",
            f"memory_avg={metrics['avg_memory_records']}",
            f"retrieve_avg_ms={metrics['avg_retrieve_ms']}",
            f"user={metrics.get('total_user_records', 0)}",
            f"assistant={metrics.get('total_assistant_records', 0)}",
            f"assistant_fn={metrics.get('total_assistant_function_call_records', 0)}",
            f"function={metrics.get('total_function_records', 0)}",
            f"tool={metrics.get('total_tool_records', 0)}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
