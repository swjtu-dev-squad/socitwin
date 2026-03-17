#!/usr/bin/env python3
"""
E2E Test Script: Simulate Frontend Operations

This script mimics the frontend workflow:
1. Initialize simulation (POST /api/sim/config)
2. Execute step-by-step (POST /api/sim/step)
3. Verify metrics (velocity, herd_hhi, polarization)
4. Display detailed results

Usage:
    python test_e2e_simulation.py
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any


class SimulationTester:
    """End-to-end simulation tester"""

    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.simulation_id = None
        self.steps_executed = 0
        self.results = {
            "initialization": None,
            "steps": [],
            "metrics": [],
            "errors": []
        }

    def print_section(self, title: str):
        """Print section header"""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)

    def print_metric(self, name: str, value: Any, unit: str = ""):
        """Print metric value"""
        unit_str = f" {unit}" if unit else ""
        print(f"  • {name}: {value}{unit_str}")

    def reset_simulation(self) -> bool:
        """Reset simulation to clean state"""
        self.print_section("Resetting Simulation")

        try:
            response = requests.post(
                f"{self.base_url}/api/sim/reset",
                json={},
                timeout=10
            )
            response.raise_for_status()
            print("  ✅ Simulation reset successful")
            time.sleep(1)
            return True
        except Exception as e:
            print(f"  ❌ Reset failed: {e}")
            return False

    def initialize_simulation(
        self,
        agent_count: int = 5,
        platform: str = "reddit",
        recsys: str = "hot-score",
        topics: list = None,
        regions: list = None
    ) -> Dict:
        """Initialize simulation with configuration"""
        self.print_section("Initializing Simulation")

        if topics is None:
            topics = ["AI"]
        if regions is None:
            regions = ["General"]

        config = {
            "agentCount": agent_count,
            "platform": platform,
            "recsys": recsys,
            "topics": topics,
            "regions": regions
        }

        print(f"  Configuration:")
        print(f"    • Agents: {agent_count}")
        print(f"    • Platform: {platform}")
        print(f"    • RecSys: {recsys}")
        print(f"    • Topics: {', '.join(topics)}")
        print(f"    • Regions: {', '.join(regions)}")
        print(f"  ⏳ Initializing...")

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/sim/config",
                json=config,
                timeout=60
            )
            elapsed = time.time() - start_time

            response.raise_for_status()
            response_data = response.json()

            # Handle different response formats:
            # - /api/sim/step returns direct JSON: {"running": true, ...}
            # - /api/sim/config returns JSON-RPC: {"result": {"status": "ok", ...}}
            if "result" in response_data and isinstance(response_data["result"], dict):
                result = response_data["result"]
            elif "status" in response_data:
                # Direct format (from /api/sim/step)
                result = response_data
                # Convert to match expected format
                if result.get("running"):
                    result["status"] = "ok"
            else:
                result = response_data

            # Check for both "ok" status and "running" flag
            if result.get("status") == "ok" or result.get("running"):
                print(f"  ✅ Initialization successful ({elapsed:.2f}s)")
                self.print_metric("Agent Count", result.get("agent_count"))
                self.print_metric("Platform", result.get("platform"))
                self.print_metric("Topics", ", ".join(result.get("topics", [])))

                self.results["initialization"] = {
                    "success": True,
                    "elapsed_time": elapsed,
                    "response": result
                }

                # Wait for initialization to complete
                print(f"  ⏳ Waiting for agents to settle...")
                time.sleep(3)

                return result
            else:
                error_msg = result.get("message", "Unknown error")
                print(f"  ❌ Initialization failed: {error_msg}")
                self.results["errors"].append({
                    "stage": "initialization",
                    "error": error_msg
                })
                return None

        except Exception as e:
            print(f"  ❌ Request failed: {e}")
            self.results["errors"].append({
                "stage": "initialization",
                "error": str(e)
            })
            return None

    def execute_step(self, step_number: int) -> Dict:
        """Execute a single simulation step"""
        print(f"\n  📍 Step {step_number}")
        print(f"  ⏳ Executing...")

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/sim/step",
                json={},
                timeout=600  # 10 minutes timeout
            )
            elapsed = time.time() - start_time

            response.raise_for_status()
            response_data = response.json()

            # Handle different response formats:
            # - /api/sim/step returns direct JSON: {"running": true, ...}
            # - /api/sim/config returns JSON-RPC: {"result": {"status": "ok", ...}}
            if "result" in response_data and isinstance(response_data["result"], dict):
                result = response_data["result"]
            elif "status" in response_data:
                # Direct format (from /api/sim/step)
                result = response_data
                # Convert to match expected format
                if result.get("running"):
                    result["status"] = "ok"
            else:
                result = response_data

            # Check for both "ok" status and "running" flag
            if result.get("status") == "ok" or result.get("running"):
                print(f"  ✅ Step {step_number} completed ({elapsed:.2f}s)")

                # Extract metrics with field name mapping
                # /api/sim/step uses camelCase: currentStep, totalPosts, etc.
                metrics = {
                    "step": step_number,
                    "elapsed_time": elapsed,
                    "current_step": result.get("current_step") or result.get("currentStep"),
                    "total_posts": result.get("total_posts") or result.get("totalPosts"),
                    "active_agents": result.get("active_agents") or result.get("activeAgents"),
                    "polarization": result.get("polarization"),
                    "velocity": result.get("velocity") or result.get("velocity"),
                    "herd_hhi": result.get("herd_hhi") or result.get("herdHhi"),
                }

                # Print metrics
                print(f"     Metrics:")
                self.print_metric("Current Step", metrics["current_step"])
                self.print_metric("Total Posts", metrics["total_posts"])
                self.print_metric("Active Agents", metrics["active_agents"])
                self.print_metric("Polarization", f"{metrics['polarization']*100:.2f}", "%")

                if metrics["velocity"] is not None:
                    self.print_metric("Velocity", f"{metrics['velocity']:.4f}", "posts/s")

                if metrics["herd_hhi"] is not None:
                    self.print_metric("Herd HHI", f"{metrics['herd_hhi']*100:.2f}", "%")

                # Check detailed metrics
                if "velocity_details" in result:
                    vel_details = result["velocity_details"]
                    if "delta_posts" in vel_details:
                        self.print_metric("  Delta Posts", vel_details["delta_posts"])
                    if "step_duration" in vel_details:
                        self.print_metric("  Step Duration", f"{vel_details['step_duration']:.2f}", "s")

                if "herd_hhi_details" in result:
                    hhi_details = result["herd_hhi_details"]
                    if not hhi_details.get("degraded"):
                        if "total_actions" in hhi_details:
                            self.print_metric("  Total Actions", hhi_details["total_actions"])
                        if "n_action_types" in hhi_details:
                            self.print_metric("  Action Types", hhi_details["n_action_types"])
                        if "action_distribution" in hhi_details:
                            print(f"     Action Distribution:")
                            for action, ratio in hhi_details["action_distribution"].items():
                                print(f"       - {action}: {ratio*100:.1f}%")
                    else:
                        print(f"     ⚠️  HHI degraded (using fallback)")

                self.results["steps"].append(metrics)
                self.results["metrics"].append(metrics)
                self.steps_executed += 1

                return result
            else:
                error_msg = result.get("message", "Unknown error")
                print(f"  ❌ Step failed: {error_msg}")
                self.results["errors"].append({
                    "stage": f"step_{step_number}",
                    "error": error_msg
                })
                return None

        except Exception as e:
            print(f"  ❌ Request failed: {e}")
            self.results["errors"].append({
                "stage": f"step_{step_number}",
                "error": str(e)
            })
            return None

    def get_status(self) -> Dict:
        """Get current simulation status"""
        try:
            response = requests.get(
                f"{self.base_url}/api/sim/status",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  ⚠️  Failed to get status: {e}")
            return None

    def verify_metrics(self) -> bool:
        """Verify that metrics are present and valid"""
        self.print_section("Verifying Metrics")

        if not self.results["metrics"]:
            print("  ❌ No metrics collected")
            return False

        all_valid = True

        # Check velocity
        velocities = [m.get("velocity") for m in self.results["metrics"] if m.get("velocity") is not None]
        if velocities:
            print(f"  ✅ Velocity: {len(velocities)} measurements")
            print(f"     Range: {min(velocities):.4f} - {max(velocities):.4f} posts/s")
            print(f"     Average: {sum(velocities)/len(velocities):.4f} posts/s")
        else:
            print(f"  ⚠️  Velocity: No measurements")
            all_valid = False

        # Check HHI
        hhies = [m.get("herd_hhi") for m in self.results["metrics"] if m.get("herd_hhi") is not None]
        if hhies:
            print(f"  ✅ Herd HHI: {len(hhies)} measurements")
            print(f"     Range: {min(hhies):.4f} - {max(hhies):.4f}")
            print(f"     Average: {sum(hhies)/len(hhies):.4f}")

            # Verify HHI is in valid range
            invalid_hhi = [h for h in hhies if h < 0 or h > 1]
            if invalid_hhi:
                print(f"  ❌ Invalid HHI values detected: {invalid_hhi}")
                all_valid = False
        else:
            print(f"  ⚠️  Herd HHI: No measurements")
            all_valid = False

        # Check polarization
        polarizations = [m.get("polarization") for m in self.results["metrics"] if m.get("polarization") is not None]
        if polarizations:
            print(f"  ✅ Polarization: {len(polarizations)} measurements")
            print(f"     Range: {min(polarizations):.4f} - {max(polarizations):.4f}")
        else:
            print(f"  ⚠️  Polarization: No measurements")

        return all_valid

    def print_summary(self):
        """Print test summary"""
        self.print_section("Test Summary")

        print(f"  Initialization: {'✅ Success' if self.results['initialization'] else '❌ Failed'}")
        print(f"  Steps Executed: {self.steps_executed}")
        print(f"  Metrics Collected: {len(self.results['metrics'])}")
        print(f"  Errors: {len(self.results['errors'])}")

        if self.results["errors"]:
            print(f"\n  Errors encountered:")
            for error in self.results["errors"]:
                print(f"    • [{error['stage']}] {error['error']}")

        if self.results["metrics"]:
            print(f"\n  Metrics Trend:")
            print(f"    Step | Posts | Polarization | Velocity | HHI")
            print(f"    -----|-------|--------------|----------|-----")
            for m in self.results["metrics"]:
                step = m.get("step", "-")
                posts = m.get("total_posts", "-")
                pol = f"{m.get('polarization', 0)*100:.1f}%" if m.get("polarization") is not None else "-"
                vel = f"{m.get('velocity', 0):.3f}" if m.get("velocity") is not None else "-"
                hhi = f"{m.get('herd_hhi', 0)*100:.1f}%" if m.get("herd_hhi") is not None else "-"
                print(f"    {step:5} | {posts:5} | {pol:12} | {vel:8} | {hhi}")

    def save_results(self, filename: str = None):
        """Save test results to JSON file"""
        import os
        # Ensure test-results directory exists
        os.makedirs("test-results", exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"test-results/e2e_{timestamp}.json"

        try:
            with open(filename, "w") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"\n  💾 Results saved to: {filename}")
            print(f"  📁 Test results directory: test-results/")
        except Exception as e:
            print(f"  ⚠️  Failed to save results: {e}")

    def run_full_test(
        self,
        agent_count: int = 5,
        num_steps: int = 5,
        platform: str = "reddit",
        topics: list = None
    ):
        """Run complete end-to-end test"""
        print("\n" + "🚀" * 30)
        print("  OASIS Dashboard E2E Test")
        print("  Simulating Frontend Workflow")
        print("🚀" * 30)

        # Reset
        if not self.reset_simulation():
            return False

        # Initialize
        init_result = self.initialize_simulation(
            agent_count=agent_count,
            platform=platform,
            topics=topics
        )

        if not init_result:
            return False

        # Execute steps
        self.print_section(f"Executing {num_steps} Steps")

        for step in range(1, num_steps + 1):
            result = self.execute_step(step)

            if not result:
                print(f"\n  ⚠️  Stopping test due to step failure")
                break

            # Small delay between steps
            if step < num_steps:
                time.sleep(0.5)

        # Verify metrics
        metrics_valid = self.verify_metrics()

        # Print summary
        self.print_summary()

        # Save results
        self.save_results()

        return metrics_valid and len(self.results["errors"]) == 0


def main():
    """Main entry point"""
    import sys

    # Parse command line arguments
    agent_count = 5
    num_steps = 5
    base_url = "http://localhost:3000"

    if len(sys.argv) > 1:
        agent_count = int(sys.argv[1])
    if len(sys.argv) > 2:
        num_steps = int(sys.argv[2])
    if len(sys.argv) > 3:
        base_url = sys.argv[3]

    # Run test
    tester = SimulationTester(base_url=base_url)

    try:
        success = tester.run_full_test(
            agent_count=agent_count,
            num_steps=num_steps,
            platform="reddit",
            topics=["AI"]
        )

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n  ⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n  ❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
