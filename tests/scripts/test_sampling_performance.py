#!/usr/bin/env python3
"""Performance comparison: with vs without sampling (Issue #52)"""

import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.scripts.test_e2e_simulation import SimulationTester


def benchmark_sampling():
    """Compare execution time with and without sampling"""

    configs = [
        {
            "name": "No Sampling (20 agents)",
            "agent_count": 20,
            "sampling_config": {"enabled": False},
            "steps": 5
        },
        {
            "name": "Sampling 50% (20 agents)",
            "agent_count": 20,
            "sampling_config": {"enabled": True, "rate": 0.5, "min_active": 5, "strategy": "random"},
            "steps": 5
        },
    ]

    results = []

    for config in configs:
        print(f"\n{'=' * 70}")
        print(f"Testing: {config['name']}")
        print('=' * 70)

        tester = SimulationTester()

        # Reset
        print("🔄 Resetting simulation...")
        if not tester.reset_simulation():
            print(f"❌ Failed to reset for {config['name']}")
            continue

        # Initialize
        print(f"🚀 Initializing {config['agent_count']} agents...")
        init_result = tester.initialize_simulation(
            agent_count=config["agent_count"],
            topics=["AI"],
            sampling_config=config["sampling_config"]
        )

        if not init_result:
            print(f"❌ Failed to initialize: {config['name']}")
            continue

        # Measure steps
        print(f"⏳ Measuring {config['steps']} steps...")
        start_time = time.time()

        for step_num in range(1, config["steps"] + 1):
            result = tester.execute_step(step_num)
            if not result:
                print(f"❌ Step {step_num} failed")
                break

        elapsed = time.time() - start_time

        results.append({
            "config": config["name"],
            "time": elapsed,
            "avg_step_time": elapsed / config["steps"],
            "steps": config["steps"],
        })

        print(f"✅ Total time: {elapsed:.2f}s")
        print(f"   Avg per step: {elapsed/config['steps']:.2f}s")

    # Print comparison
    print(f"\n{'=' * 70}")
    print("📊 Performance Comparison")
    print('=' * 70)

    if len(results) >= 2:
        baseline = results[0]
        for r in results[1:]:
            speedup = baseline["avg_step_time"] / r["avg_step_time"]
            improvement = ((baseline["avg_step_time"] - r["avg_step_time"]) / baseline["avg_step_time"]) * 100

            print(f"\n{r['config']}:")
            print(f"  Avg per step: {r['avg_step_time']:.2f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Time saved: {improvement:.1f}%")

    print(f"\n{'=' * 70}")
    print("Summary Table:")
    print('=' * 70)
    print(f"{'Configuration':<35} | {'Avg Step':<12} | {'Total':<10}")
    print('-' * 70)
    for r in results:
        print(f"{r['config']:<35} | {r['avg_step_time']:.2f}s        | {r['time']:.2f}s   ")
    print('=' * 70)

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("Agent Sampling Performance Benchmark")
    print("Issue #52 - Agent Sampling Mechanism")
    print("=" * 70)

    results = benchmark_sampling()

    print("\n✅ Performance benchmark completed!")
    sys.exit(0)
