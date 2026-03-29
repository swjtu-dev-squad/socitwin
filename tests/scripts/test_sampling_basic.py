#!/usr/bin/env python3
"""Basic sampling functionality test for Issue #52"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


def test_sampling_disabled_default():
    """Test that sampling is disabled by default"""
    # Clear any existing environment variables
    for key in list(os.environ.keys()):
        if key.startswith("OASIS_SAMPLING_"):
            del os.environ[key]

    engine = RealOASISEngineV3()
    assert engine.sampling_config == {"enabled": False}
    print("✅ Sampling disabled by default")


def test_sampling_enabled_via_env():
    """Test enabling sampling via environment variables"""
    os.environ["OASIS_SAMPLING_ENABLED"] = "true"
    os.environ["OASIS_SAMPLING_RATE"] = "0.2"
    os.environ["OASIS_SAMPLING_STRATEGY"] = "random"
    os.environ["OASIS_SAMPLING_MIN_ACTIVE"] = "10"
    os.environ["OASIS_SAMPLING_SEED"] = "123"

    engine = RealOASISEngineV3()
    config = engine.sampling_config

    assert config["enabled"] == True
    assert config["rate"] == 0.2
    assert config["strategy"] == "random"
    assert config["min_active"] == 10
    assert config["seed"] == 123
    print("✅ Sampling enabled via environment variables")

    # Cleanup
    del os.environ["OASIS_SAMPLING_ENABLED"]
    del os.environ["OASIS_SAMPLING_RATE"]
    del os.environ["OASIS_SAMPLING_STRATEGY"]
    del os.environ["OASIS_SAMPLING_MIN_ACTIVE"]
    del os.environ["OASIS_SAMPLING_SEED"]


def test_sample_agents_method():
    """Test the _sample_agents method"""
    import random

    # Clear environment variables to start fresh
    for key in list(os.environ.keys()):
        if key.startswith("OASIS_SAMPLING_"):
            del os.environ[key]

    engine = RealOASISEngineV3()
    engine.sampling_config = {
        "enabled": True,
        "rate": 0.5,
        "strategy": "random",
        "min_active": 5,
        "seed": 42,
    }
    engine.current_step = 0

    # Create mock agent list
    mock_agents = [(i, f"agent_{i}") for i in range(100)]

    # Test sampling
    sampled = engine._sample_agents(mock_agents)

    # Should sample 50 agents (50% of 100)
    assert len(sampled) == 50, f"Expected 50 agents, got {len(sampled)}"
    print(f"✅ Sampled {len(sampled)}/100 agents (50%)")

    # Test min_active constraint
    engine.sampling_config["rate"] = 0.01  # 1% of 100 = 1 agent
    engine.sampling_config["min_active"] = 10  # But min is 10
    sampled = engine._sample_agents(mock_agents)
    assert len(sampled) == 10, f"Expected 10 agents with min_active constraint, got {len(sampled)}"
    print(f"✅ Respected min_active constraint: {len(sampled)} agents")

    # Test reproducibility with same seed
    engine.current_step = 0
    sampled1 = engine._sample_agents(mock_agents)
    engine.current_step = 0
    sampled2 = engine._sample_agents(mock_agents)

    # Extract agent IDs for comparison
    ids1 = sorted([agent_id for agent_id, _ in sampled1])
    ids2 = sorted([agent_id for agent_id, _ in sampled2])

    assert ids1 == ids2, "Sampling should be reproducible with same seed"
    print("✅ Sampling is reproducible with same seed")


def test_sampling_different_steps():
    """Test that different steps produce different samples"""
    import random

    # Clear environment variables
    for key in list(os.environ.keys()):
        if key.startswith("OASIS_SAMPLING_"):
            del os.environ[key]

    engine = RealOASISEngineV3()
    engine.sampling_config = {
        "enabled": True,
        "rate": 0.2,
        "strategy": "random",
        "min_active": 5,
        "seed": 42,
    }

    mock_agents = [(i, f"agent_{i}") for i in range(100)]

    # Sample at different steps
    engine.current_step = 0
    sampled_step0 = engine._sample_agents(mock_agents)

    engine.current_step = 1
    sampled_step1 = engine._sample_agents(mock_agents)

    # Extract agent IDs
    ids0 = sorted([agent_id for agent_id, _ in sampled_step0])
    ids1 = sorted([agent_id for agent_id, _ in sampled_step1])

    # Different steps should produce different samples (seed + step offset)
    assert ids0 != ids1, "Different steps should produce different samples"
    print("✅ Different steps produce different samples")


if __name__ == "__main__":
    test_sampling_disabled_default()
    test_sampling_enabled_via_env()
    test_sample_agents_method()
    test_sampling_different_steps()
    print("\n✅ All unit tests passed!")
