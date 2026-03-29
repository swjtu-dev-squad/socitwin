#!/usr/bin/env python3
"""E2E test for sampling mechanism (Issue #52)"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.scripts.test_e2e_simulation import SimulationTester


def test_e2e_with_sampling():
    """Test full simulation with sampling enabled"""

    tester = SimulationTester(base_url="http://localhost:3000")

    # Reset
    print("🔄 Resetting simulation...")
    if not tester.reset_simulation():
        print("❌ Reset failed")
        return False

    # Initialize with sampling
    sampling_config = {
        "enabled": True,
        "rate": 0.2,  # Only 20% of agents
        "strategy": "random",
        "min_active": 5,
    }

    print("🚀 Initializing simulation with 100 agents, 20% sampling...")
    result = tester.initialize_simulation(
        agent_count=100,
        topics=["AI"],
        sampling_config=sampling_config
    )

    if not result:
        print("❌ Initialization failed")
        return False

    print("✅ Initialization successful")

    # Run 5 steps
    for step_num in range(1, 6):
        print(f"⏳ Executing step {step_num}...")
        result = tester.execute_step(step_num)
        if not result:
            print(f"❌ Step {step_num} failed")
            return False

        print(f"✅ Step {step_num} completed")

    print("✅ E2E test with sampling passed")
    return True


def test_e2e_without_sampling():
    """Test full simulation without sampling (baseline)"""

    tester = SimulationTester(base_url="http://localhost:3000")

    # Reset
    print("🔄 Resetting simulation...")
    if not tester.reset_simulation():
        print("❌ Reset failed")
        return False

    # Initialize without sampling
    print("🚀 Initializing simulation with 20 agents, no sampling...")
    result = tester.initialize_simulation(
        agent_count=20,
        topics=["AI"],
        sampling_config=None  # No sampling
    )

    if not result:
        print("❌ Initialization failed")
        return False

    print("✅ Initialization successful")

    # Run 3 steps
    for step_num in range(1, 4):
        print(f"⏳ Executing step {step_num}...")
        result = tester.execute_step(step_num)
        if not result:
            print(f"❌ Step {step_num} failed")
            return False

        print(f"✅ Step {step_num} completed")

    print("✅ E2E test without sampling passed")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("E2E Sampling Test Suite")
    print("=" * 60)

    # Test without sampling first (baseline)
    print("\n📋 Test 1: E2E without sampling (baseline)")
    print("-" * 60)
    success_baseline = test_e2e_without_sampling()

    # Test with sampling
    print("\n📋 Test 2: E2E with 20% sampling")
    print("-" * 60)
    success_sampling = test_e2e_with_sampling()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    print(f"Baseline (no sampling): {'✅ PASSED' if success_baseline else '❌ FAILED'}")
    print(f"Sampling (20%): {'✅ PASSED' if success_sampling else '❌ FAILED'}")
    print("=" * 60)

    if success_baseline and success_sampling:
        print("\n✅ All E2E tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some E2E tests failed")
        sys.exit(1)
