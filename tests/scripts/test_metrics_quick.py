#!/usr/bin/env python3
"""
Quick Metrics Test - Verify velocity and HHI are working

Usage:
    python test_metrics_quick.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:3000"

print("=" * 60)
print("  Quick Metrics Test")
print("=" * 60)

# Step 1: Reset
print("\n[1/4] Resetting simulation...")
try:
    r = requests.post(f"{BASE_URL}/api/sim/reset", json={}, timeout=10)
    r.raise_for_status()
    print("  ✅ Reset OK")
except Exception as e:
    print(f"  ❌ Reset failed: {e}")
    exit(1)

time.sleep(1)

# Step 2: Initialize
print("\n[2/4] Initializing simulation (3 agents, AI topic)...")
try:
    config = {
        "agentCount": 3,
        "platform": "reddit",
        "recsys": "hot-score",
        "topics": ["AI"],
        "regions": ["General"]
    }
    r = requests.post(f"{BASE_URL}/api/sim/config", json=config, timeout=60)
    r.raise_for_status()
    response_data = r.json()

    # Handle different response formats
    if "result" in response_data and isinstance(response_data["result"], dict):
        result = response_data["result"]
    elif "status" in response_data or "running" in response_data:
        result = response_data
        if result.get("running"):
            result["status"] = "ok"
    else:
        result = response_data

    if result.get("status") == "ok":
        print(f"  ✅ Init OK: {result.get('agent_count')} agents")
    else:
        print(f"  ❌ Init failed: {result.get('message')}")
        exit(1)
except Exception as e:
    print(f"  ❌ Init failed: {e}")
    exit(1)

print("  ⏳ Waiting 3 seconds for agents to settle...")
time.sleep(3)

# Step 3: Execute steps and collect metrics
print("\n[3/4] Executing 3 steps...")
metrics_list = []

for i in range(1, 4):
    print(f"\n  Step {i}...")
    try:
        start = time.time()
        r = requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=120)
        elapsed = time.time() - start
        r.raise_for_status()
        response_data = r.json()

        # Handle different response formats
        if "result" in response_data and isinstance(response_data["result"], dict):
            result = response_data["result"]
        elif "running" in response_data or "currentStep" in response_data:
            result = response_data
            if result.get("running"):
                result["status"] = "ok"
        else:
            result = response_data

        # Check for success
        if result.get("status") == "ok" or result.get("running"):
            step_num = result.get("current_step") or result.get("currentStep", i)
            posts = result.get("total_posts") or result.get("totalPosts", 0)
            pol = result.get("polarization", 0)
            vel = result.get("velocity") or result.get("velocity", 0)
            hhi = result.get("herd_hhi") or result.get("herdHhi")

            print(f"    ✅ OK ({elapsed:.2f}s)")
            print(f"       Posts: {posts}, Polarization: {pol*100:.1f}%")

            if vel is not None:
                print(f"       ✅ Velocity: {vel:.4f} posts/s")
            else:
                print(f"       ⚠️  Velocity: None")

            if hhi is not None:
                print(f"       ✅ HHI: {hhi*100:.1f}%")

                # Show action distribution if available
                hhi_details = result.get("herd_hhi_details", {})
                if "action_distribution" in hhi_details:
                    print(f"       Actions: {list(hhi_details['action_distribution'].keys())}")
            else:
                print(f"       ⚠️  HHI: None")

            metrics_list.append({
                "step": step_num,
                "velocity": vel,
                "herd_hhi": hhi,
                "polarization": pol
            })
        else:
            print(f"    ❌ Failed: {result.get('message')}")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    time.sleep(0.5)

# Step 4: Verify
print("\n[4/4] Verification...")

velocity_values = [m["velocity"] for m in metrics_list if m["velocity"] is not None]
hhi_values = [m["herd_hhi"] for m in metrics_list if m["herd_hhi"] is not None]

print(f"\n  Results:")
print(f"    Total steps: {len(metrics_list)}")
print(f"    Velocity measurements: {len(velocity_values)}")
print(f"    HHI measurements: {len(hhi_values)}")

if velocity_values:
    print(f"    ✅ Velocity is working!")
    print(f"       Average: {sum(velocity_values)/len(velocity_values):.4f} posts/s")
else:
    print(f"    ❌ Velocity not working")

if hhi_values:
    print(f"    ✅ HHI is working!")
    print(f"       Average: {sum(hhi_values)/len(hhi_values):.4f}")

    # Check HHI is in valid range
    if all(0 <= h <= 1 for h in hhi_values):
        print(f"       ✅ All HHI values in valid range [0, 1]")
    else:
        print(f"       ❌ Some HHI values out of range!")
else:
    print(f"    ❌ HHI not working")

# Final verdict
if velocity_values and hhi_values:
    print(f"\n{'='*60}")
    print(f"  ✅ ALL TESTS PASSED!")
    print(f"{'='*60}")
    exit(0)
else:
    print(f"\n{'='*60}")
    print(f"  ❌ SOME TESTS FAILED")
    print(f"{'='*60}")
    exit(1)
