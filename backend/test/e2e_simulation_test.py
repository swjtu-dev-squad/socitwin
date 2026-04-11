#!/usr/bin/env python3
"""
End-to-End Simulation Test Script

This script runs a complete simulation test with configurable parameters,
executes multiple steps, and generates a detailed JSON report.

Usage:
    python e2e_simulation_test.py --agent-count 5 --max-steps 10 --topic climate_change_debate
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PLATFORM = "twitter"
DEFAULT_AGENT_COUNT = 5
DEFAULT_MAX_STEPS = 10
DEFAULT_MODEL_PLATFORM = "DEEPSEEK"
DEFAULT_MODEL_TYPE = "DEEPSEEK_CHAT"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOPIC = "climate_change_debate"
DEFAULT_TIMEOUT = 120  # seconds


# ============================================================================
# Colors for terminal output
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# ============================================================================
# API Client
# ============================================================================

class SimulationAPIClient:
    """Client for interacting with the simulation API"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        return self._request("GET", "/health")

    def configure_simulation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure the simulation"""
        return self._request("POST", "/api/sim/config", json=config)

    def get_simulation_status(self) -> Dict[str, Any]:
        """Get current simulation status"""
        return self._request("GET", "/api/sim/status")

    def list_topics(self) -> Dict[str, Any]:
        """List available topics"""
        return self._request("GET", "/api/topics")

    def activate_topic(self, topic_id: str) -> Dict[str, Any]:
        """Activate a topic"""
        return self._request("POST", f"/api/topics/{topic_id}/activate")

    def execute_step(self, step_type: str = "auto") -> Dict[str, Any]:
        """Execute a simulation step"""
        return self._request("POST", "/api/sim/step", json={"step_type": step_type})

    def pause_simulation(self) -> Dict[str, Any]:
        """Pause the simulation"""
        return self._request("POST", "/api/sim/pause")

    def resume_simulation(self) -> Dict[str, Any]:
        """Resume the simulation"""
        return self._request("POST", "/api/sim/resume")

    def reset_simulation(self) -> Dict[str, Any]:
        """Reset the simulation"""
        return self._request("POST", "/api/sim/reset")


# ============================================================================
# Test Runner
# ============================================================================

class SimulationTestRunner:
    """Run end-to-end simulation tests"""

    def __init__(self, client: SimulationAPIClient, verbose: bool = True):
        self.client = client
        self.verbose = verbose
        self.results = {
            "test_config": {},
            "steps": [],
            "summary": {}
        }

    def _print(self, message: str, color: str = Colors.ENDC):
        """Print colored message if verbose"""
        if self.verbose:
            print(f"{color}{message}{Colors.ENDC}")

    def _print_step(self, step_num: int, total_steps: int, message: str):
        """Print step progress"""
        if self.verbose:
            print(f"[{step_num}/{total_steps}] {message}")

    def run_test(
        self,
        platform: str,
        agent_count: int,
        max_steps: int,
        topic_id: str,
        model_platform: str,
        model_type: str,
        temperature: float,
    ) -> Dict[str, Any]:
        """Run the complete test"""

        # Store test configuration
        self.results["test_config"] = {
            "platform": platform,
            "agent_count": agent_count,
            "max_steps": max_steps,
            "topic_id": topic_id,
            "model_platform": model_platform,
            "model_type": model_type,
            "temperature": temperature,
            "test_start_time": datetime.now().isoformat(),
        }

        try:
            # Step 1: Health check
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 0: Health Check", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            health = self.client.health_check()
            self._print(f"✓ API Status: {health.get('status')}", Colors.OKGREEN)
            self._print(f"✓ Project: {health.get('project')}", Colors.OKGREEN)
            self._print(f"✓ OASIS Enabled: {health.get('oasis_enabled')}", Colors.OKGREEN)

            # Step 2: Configure simulation
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 1: Configure Simulation", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            config_result = self.client.configure_simulation({
                "platform": platform,
                "agent_count": agent_count,
                "max_steps": max_steps,
                "llm_config": {
                    "model_platform": model_platform,
                    "model_type": model_type,
                    "temperature": temperature,
                    "max_tokens": 1000,
                }
            })

            if not config_result.get("success"):
                raise Exception(f"Failed to configure simulation: {config_result.get('message')}")

            self._print(f"✓ Simulation configured successfully", Colors.OKGREEN)
            self._print(f"  - Simulation ID: {config_result.get('simulation_id')}", Colors.OKCYAN)
            self._print(f"  - Agents created: {config_result.get('agents_created')}", Colors.OKCYAN)
            self._print(f"  - Platform: {platform}", Colors.OKCYAN)

            # Step 3: Activate topic
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 2: Activate Topic", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            self._print(f"Activating topic: {topic_id}", Colors.OKCYAN)

            topic_result = self.client.activate_topic(topic_id)

            if not topic_result.get("success"):
                raise Exception(f"Failed to activate topic: {topic_result.get('message')}")

            self._print(f"✓ Topic activated successfully", Colors.OKGREEN)
            self._print(f"  - Topic: {topic_result.get('topic_id')}", Colors.OKCYAN)
            self._print(f"  - Initial post created: {topic_result.get('initial_post_created')}", Colors.OKCYAN)
            self._print(f"  - Agents refreshed: {topic_result.get('agents_refreshed')}", Colors.OKCYAN)
            self._print(f"  - Execution time: {topic_result.get('execution_time', 0):.2f}s", Colors.OKCYAN)

            # Step 4: Execute simulation steps
            self._print("\n" + "="*60, Colors.HEADER)
            self._print(f"Step 3: Execute {max_steps} Simulation Steps", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            for step_num in range(1, max_steps + 1):
                step_result = self._execute_single_step(step_num, max_steps)
                self.results["steps"].append(step_result)

            # Step 5: Collect final status
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 4: Collect Final Status", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            final_status = self.client.get_simulation_status()

            self._print(f"✓ Simulation completed", Colors.OKGREEN)
            self._print(f"  - Final state: {final_status.get('state')}", Colors.OKCYAN)
            self._print(f"  - Total posts: {final_status.get('total_posts')}", Colors.OKCYAN)
            self._print(f"  - Total interactions: {final_status.get('total_interactions')}", Colors.OKCYAN)
            self._print(f"  - Active agents: {final_status.get('active_agents')}", Colors.OKCYAN)

            # Generate summary
            self.results["summary"] = self._generate_summary(final_status)
            self.results["test_config"]["test_end_time"] = datetime.now().isoformat()

            return self.results

        except Exception as e:
            self._print(f"\n✗ Test failed: {str(e)}", Colors.FAIL)
            self.results["error"] = str(e)
            self.results["test_config"]["test_end_time"] = datetime.now().isoformat()
            raise

    def _execute_single_step(self, step_num: int, total_steps: int) -> Dict[str, Any]:
        """Execute a single simulation step and collect metrics"""

        start_time = time.time()

        # Get status before step
        status_before = self.client.get_simulation_status()

        # Execute step
        step_result = self.client.execute_step("auto")

        execution_time = time.time() - start_time

        # Get status after step
        status_after = self.client.get_simulation_status()

        # Collect step information
        step_info = {
            "step_number": step_num,
            "timestamp": datetime.now().isoformat(),
            "execution_time": execution_time,
            "success": step_result.get("success", False),
            "message": step_result.get("message", ""),
            "step_executed": step_result.get("step_executed", 0),
            "actions_taken": step_result.get("actions_taken", 0),
            "metrics": {
                "before": {
                    "total_posts": status_before.get("total_posts", 0),
                    "total_interactions": status_before.get("total_interactions", 0),
                    "current_step": status_before.get("current_step", 0),
                },
                "after": {
                    "total_posts": status_after.get("total_posts", 0),
                    "total_interactions": status_after.get("total_interactions", 0),
                    "current_step": status_after.get("current_step", 0),
                },
                "delta": {
                    "posts_added": status_after.get("total_posts", 0) - status_before.get("total_posts", 0),
                    "interactions_added": status_after.get("total_interactions", 0) - status_before.get("total_interactions", 0),
                }
            },
            "state": status_after.get("state", "unknown"),
        }

        # Print progress
        if step_result.get("success"):
            self._print_step(
                step_num, total_steps,
                f"Step executed - Posts: +{step_info['metrics']['delta']['posts_added']}, "
                f"Interactions: +{step_info['metrics']['delta']['interactions_added']}, "
                f"Time: {execution_time:.2f}s"
            )
        else:
            self._print_step(step_num, total_steps, f"Step failed: {step_result.get('message')}")

        return step_info

    def _generate_summary(self, final_status: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test summary statistics"""

        total_execution_time = sum(
            step["execution_time"] for step in self.results["steps"]
        )

        total_posts_added = sum(
            step["metrics"]["delta"]["posts_added"] for step in self.results["steps"]
        )

        total_interactions_added = sum(
            step["metrics"]["delta"]["interactions_added"] for step in self.results["steps"]
        )

        successful_steps = sum(
            1 for step in self.results["steps"] if step["success"]
        )

        return {
            "total_steps_executed": len(self.results["steps"]),
            "successful_steps": successful_steps,
            "failed_steps": len(self.results["steps"]) - successful_steps,
            "total_execution_time": total_execution_time,
            "average_step_time": total_execution_time / len(self.results["steps"]) if self.results["steps"] else 0,
            "total_posts_added": total_posts_added,
            "total_interactions_added": total_interactions_added,
            "final_state": final_status.get("state"),
            "final_total_posts": final_status.get("total_posts"),
            "final_total_interactions": final_status.get("total_interactions"),
            "agent_count": final_status.get("agent_count"),
        }


# ============================================================================
# Result Exporter
# ============================================================================

class ResultExporter:
    """Export test results to JSON file"""

    def __init__(self, output_dir: str = "test-result"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, results: Dict[str, Any]) -> str:
        """Export results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test-result-{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        return str(filepath)


# ============================================================================
# Command Line Interface
# ============================================================================

def parse_arguments():
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(
        description="End-to-End Simulation Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default parameters
  python e2e_simulation_test.py

  # Run with custom parameters
  python e2e_simulation_test.py --agent-count 10 --max-steps 20 --topic tech_ai_regulation

  # Run with Reddit platform
  python e2e_simulation_test.py --platform reddit --topic crypto_discussion

  # Run quietly (no colored output)
  python e2e_simulation_test.py --no-verbose
        """
    )

    # Simulation parameters
    parser.add_argument(
        "--platform",
        type=str,
        default=DEFAULT_PLATFORM,
        choices=["twitter", "reddit"],
        help="Social media platform (default: twitter)"
    )

    parser.add_argument(
        "--agent-count",
        type=int,
        default=DEFAULT_AGENT_COUNT,
        help="Number of agents to create (default: 5)"
    )

    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum number of simulation steps (default: 10)"
    )

    parser.add_argument(
        "--topic",
        type=str,
        default=DEFAULT_TOPIC,
        help="Topic ID to activate (default: climate_change_debate)"
    )

    # LLM parameters
    parser.add_argument(
        "--model-platform",
        type=str,
        default=DEFAULT_MODEL_PLATFORM,
        help="LLM model platform (default: DEEPSEEK)"
    )

    parser.add_argument(
        "--model-type",
        type=str,
        default=DEFAULT_MODEL_TYPE,
        help="LLM model type (default: DEEPSEEK_CHAT)"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="LLM temperature (default: 0.7)"
    )

    # API configuration
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )

    # Output options
    parser.add_argument(
        "--output-dir",
        type=str,
        default="../test-result",
        help="Output directory for test results (default: ../test-result)"
    )

    parser.add_argument(
        "--no-verbose",
        action="store_true",
        help="Disable verbose output"
    )

    return parser.parse_args()


def main():
    """Main entry point"""

    args = parse_arguments()

    # Print banner
    print(Colors.HEADER + "="*60)
    print("End-to-End Simulation Test")
    print("="*60 + Colors.ENDC)

    # Display test configuration
    print("\nTest Configuration:")
    print(f"  Platform: {args.platform}")
    print(f"  Agent Count: {args.agent_count}")
    print(f"  Max Steps: {args.max_steps}")
    print(f"  Topic: {args.topic}")
    print(f"  Model: {args.model_platform}/{args.model_type}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Base URL: {args.base_url}")
    print(f"  Output Dir: {args.output_dir}")

    try:
        # Initialize client and runner
        client = SimulationAPIClient(base_url=args.base_url, timeout=args.timeout)
        runner = SimulationTestRunner(client, verbose=not args.no_verbose)

        # Run test
        results = runner.run_test(
            platform=args.platform,
            agent_count=args.agent_count,
            max_steps=args.max_steps,
            topic_id=args.topic,
            model_platform=args.model_platform,
            model_type=args.model_type,
            temperature=args.temperature,
        )

        # Export results
        exporter = ResultExporter(output_dir=args.output_dir)
        result_file = exporter.export(results)

        # Print success message
        print("\n" + Colors.OKGREEN + "="*60)
        print("✓ Test Completed Successfully!")
        print("="*60 + Colors.ENDC)
        print(f"\nResults saved to: {result_file}")

        # Print summary
        summary = results["summary"]
        print(f"\nTest Summary:")
        print(f"  Steps executed: {summary['total_steps_executed']}")
        print(f"  Successful: {summary['successful_steps']}")
        print(f"  Failed: {summary['failed_steps']}")
        print(f"  Total time: {summary['total_execution_time']:.2f}s")
        print(f"  Avg step time: {summary['average_step_time']:.2f}s")
        print(f"  Posts created: {summary['total_posts_added']}")
        print(f"  Interactions: {summary['total_interactions_added']}")

        return 0

    except Exception as e:
        print("\n" + Colors.FAIL + "="*60)
        print("✗ Test Failed!")
        print("="*60 + Colors.ENDC)
        print(f"\nError: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
