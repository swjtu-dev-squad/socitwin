#!/usr/bin/env python3
"""
End-to-End Simulation Test Script

This script runs a complete simulation test with configurable parameters,
executes multiple steps, and generates a detailed JSON report.

Usage:
    python backend/tests/e2e/e2e_simulation_test.py --agent-count 5 --max-steps 10 --topic climate_change_debate
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Load .env file from backend directory
from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(BACKEND_ROOT / "test-results" / ".matplotlib"),
)
import matplotlib
import requests

matplotlib.use('Agg')  # Non-interactive backend for server environments
import matplotlib.pyplot as plt

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PLATFORM = "twitter"
DEFAULT_AGENT_COUNT = 5
DEFAULT_MAX_STEPS = 10
# 从环境变量读取模型配置（.env 文件）
DEFAULT_MODEL_PLATFORM = os.getenv("OASIS_MODEL_PLATFORM", "openai")
DEFAULT_MODEL_TYPE = os.getenv("OASIS_MODEL_TYPE", "qwen-35b")
DEFAULT_TEMPERATURE = float(os.getenv("OASIS_MODEL_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("OASIS_MODEL_GENERATION_MAX_TOKENS", "1024"))
DEFAULT_MEMORY_MODE = os.getenv("OASIS_MEMORY_MODE", "action_v1")
DEFAULT_TOPIC = os.getenv("E2E_TEST_TOPIC", "2042552568010936455")  # 从环境变量读取，或使用默认值
DEFAULT_TIMEOUT = 120  # seconds
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "test-results" / "e2e"


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
# Configuration File Loaders
# ============================================================================

def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    加载YAML/JSON配置文件

    Args:
        file_path: 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式不支持或解析失败
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix in ['.yaml', '.yml']:
            if not YAML_AVAILABLE:
                raise ImportError("PyYAML is required to load .yaml files. Install with: pip install pyyaml")
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Failed to parse YAML file: {e}")
        elif path.suffix == '.json':
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON file: {e}")
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}. Supported: .yaml, .yml, .json")


def validate_controlled_agents_config(config: Dict[str, Any]) -> None:
    """
    验证受控agents配置文件格式

    Args:
        config: 配置字典

    Raises:
        ValueError: 配置格式无效
    """
    if "agents" not in config:
        raise ValueError("Missing required field: 'agents'")

    agents = config["agents"]
    if not isinstance(agents, list) or len(agents) == 0:
        raise ValueError("'agents' must be a non-empty list")

    for i, agent in enumerate(agents):
        required_fields = ["user_name", "name", "description"]
        for field in required_fields:
            if field not in agent:
                raise ValueError(f"Agent {i}: missing required field: '{field}'")

        # 验证 behavior_strategy (如果提供)
        if "behavior_strategy" in agent:
            valid_strategies = ["llm_autonomous", "probabilistic", "rule_based", "scheduled", "mixed"]
            if agent["behavior_strategy"] not in valid_strategies:
                raise ValueError(
                    f"Agent {i}: invalid behavior_strategy '{agent['behavior_strategy']}'. "
                    f"Valid options: {valid_strategies}"
                )

    # 验证极化率阈值 (如果提供)
    if "polarization_threshold" in config:
        threshold = config["polarization_threshold"]
        if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
            raise ValueError("'polarization_threshold' must be a number between 0.0 and 1.0")


def validate_behavior_config(config: Dict[str, Any]) -> None:
    """
    验证行为策略配置文件格式

    Args:
        config: 配置字典

    Raises:
        ValueError: 配置格式无效
    """
    # 检查是否使用预设配置或自定义配置
    has_preset = "preset" in config and config["preset"] is not None
    has_custom = "custom_config" in config and config["custom_config"] is not None

    if not has_preset and not has_custom:
        raise ValueError("Behavior config must contain either 'preset' or 'custom_config'")

    if has_preset:
        valid_presets = ["default", "probabilistic", "rule_based", "scheduled"]
        if config["preset"] not in valid_presets:
            raise ValueError(
                f"Invalid preset '{config['preset']}'. Valid options: {valid_presets}"
            )

    if "platform" in config:
        valid_platforms = ["twitter", "reddit"]
        if config["platform"] not in valid_platforms:
            raise ValueError(
                f"Invalid platform '{config['platform']}'. Valid options: {valid_platforms}"
            )

    if "target_agents" in config:
        target = config["target_agents"]
        if target != "controlled" and target != "all":
            # 尝试解析为逗号分隔的ID列表
            try:
                agent_ids = [int(x.strip()) for x in str(target).split(",")]
                config["target_agent_ids"] = agent_ids
            except ValueError:
                raise ValueError(
                    f"Invalid target_agents '{target}'. "
                    "Must be 'controlled', 'all', or comma-separated agent IDs"
                )


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

    def get_memory_debug_status(self) -> Dict[str, Any]:
        """Get current memory runtime debug status"""
        return self._request("GET", "/api/sim/memory")

    def list_topics(self) -> Dict[str, Any]:
        """List available topics"""
        return self._request("GET", "/api/topics")

    def activate_topic(self, topic_id: str) -> Dict[str, Any]:
        """Activate a topic"""
        return self._request("POST", f"/api/topics/{topic_id}/activate")

    def execute_step(self, step_type: str = "auto") -> Dict[str, Any]:
        """Execute a simulation step"""
        return self._request("POST", "/api/sim/step", json={"step_type": step_type})

    def get_step_result(self, task_id: str) -> Dict[str, Any]:
        """Get background step result"""
        try:
            return self._request("GET", f"/api/sim/step/{task_id}")
        except Exception as exc:
            # The task endpoint can briefly return 404 before the background
            # coroutine stores its result. Treat that race as pending.
            if "404 Client Error" in str(exc):
                return {"completed": False}
            raise

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
    # Metrics API methods
    # ============================================================================

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return self._request("GET", "/api/metrics/summary")

    def get_propagation_metrics(self) -> Dict[str, Any]:
        """Get information propagation metrics"""
        return self._request("GET", "/api/metrics/propagation")

    def get_polarization_metrics(self) -> Dict[str, Any]:
        """Get group polarization metrics"""
        return self._request("GET", "/api/metrics/polarization")

    def get_herd_effect_metrics(self) -> Dict[str, Any]:
        """Get herd effect metrics"""
        return self._request("GET", "/api/metrics/herd-effect")

    # ============================================================================
    # Controlled Agents API methods
    # ============================================================================

    def add_controlled_agents(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Add controlled agents to simulation"""
        return self._request("POST", "/api/sim/agents/controlled", json=request)

    # ============================================================================
    # Behavior Control API methods
    # ============================================================================

    def update_agent_behavior(self, agent_id: int, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update behavior configuration for a specific agent"""
        return self._request("POST", "/api/behavior/config", json={
            "agent_id": agent_id,
            "behavior_config": config
        })

    def get_agent_behavior(self, agent_id: int) -> Dict[str, Any]:
        """Get behavior configuration for a specific agent"""
        return self._request("GET", f"/api/behavior/config/{agent_id}")

    def apply_behavior_preset(self, agent_id: int, preset: str, platform: str) -> Dict[str, Any]:
        """Apply a preset behavior configuration to an agent"""
        return self._request(
            "POST",
            f"/api/behavior/config/preset/{agent_id}",
            params={"preset": preset, "platform": platform}
        )

    def get_behavior_statistics(self) -> Dict[str, Any]:
        """Get behavior control statistics"""
        return self._request("GET", "/api/behavior/stats")

    def get_behavior_status(self) -> Dict[str, Any]:
        """Get behavior controller status"""
        return self._request("GET", "/api/behavior/status")


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
        max_tokens: int,
        memory_mode: str,
        controlled_agents_file: Optional[str] = None,
        behavior_config_file: Optional[str] = None,
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
            "max_tokens": max_tokens,
            "memory_mode": memory_mode,
            "controlled_agents_file": controlled_agents_file,
            "behavior_config_file": behavior_config_file,
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
                "memory_mode": memory_mode,
                "llm_config": {
                    "model_platform": model_platform,
                    "model_type": model_type,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            })

            if not config_result.get("success"):
                raise Exception(f"Failed to configure simulation: {config_result.get('message')}")

            self._print("✓ Simulation configured successfully", Colors.OKGREEN)
            self._print(f"  - Simulation ID: {config_result.get('simulation_id')}", Colors.OKCYAN)
            self._print(f"  - Agents created: {config_result.get('agents_created')}", Colors.OKCYAN)
            self._print(f"  - Platform: {platform}", Colors.OKCYAN)

            # Step 2: Activate topic
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 2: Activate Topic", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            self._print(f"Activating topic: {topic_id}", Colors.OKCYAN)

            topic_result = self.client.activate_topic(topic_id)

            if not topic_result.get("success"):
                raise Exception(f"Failed to activate topic: {topic_result.get('message')}")

            self._print("✓ Topic activated successfully", Colors.OKGREEN)
            self._print(f"  - Topic: {topic_result.get('topic_id')}", Colors.OKCYAN)
            self._print(f"  - Initial post created: {topic_result.get('initial_post_created')}", Colors.OKCYAN)
            self._print(f"  - Agents refreshed: {topic_result.get('agents_refreshed')}", Colors.OKCYAN)
            self._print(f"  - Execution time: {topic_result.get('execution_time', 0):.2f}s", Colors.OKCYAN)

            # Step 3: Add controlled agents (if config provided)
            controlled_agents_result = self._add_controlled_agents_step(
                controlled_agents_file, platform
            )

            # Step 4: Apply behavior configurations (if config provided)
            controlled_agent_ids = controlled_agents_result.get("agent_ids", [])
            all_agent_count = agent_count + len(controlled_agent_ids)
            behavior_config_result = self._apply_behavior_configurations_step(
                behavior_config_file,
                controlled_agent_ids,
                all_agent_count,
                platform
            )

            # Step 5: Execute simulation steps
            self._print("\n" + "="*60, Colors.HEADER)
            self._print(f"Step 5: Execute {max_steps} Simulation Steps", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            for step_num in range(1, max_steps + 1):
                step_result = self._execute_single_step(step_num, max_steps)
                self.results["steps"].append(step_result)

            # Step 6: Collect final status
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 6: Collect Final Status", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            final_status = self.client.get_simulation_status()
            final_memory_debug = self._collect_memory_debug()

            self._print("✓ Simulation completed", Colors.OKGREEN)
            self._print(f"  - Final state: {final_status.get('state')}", Colors.OKCYAN)
            self._print(f"  - Total posts: {final_status.get('total_posts')}", Colors.OKCYAN)
            self._print(f"  - Total interactions: {final_status.get('total_interactions')}", Colors.OKCYAN)
            self._print(f"  - Active agents: {final_status.get('active_agents')}", Colors.OKCYAN)

            # Generate summary
            self.results["summary"] = self._generate_summary(final_status)
            if final_memory_debug:
                self.results["summary"]["final_memory_debug"] = final_memory_debug

            # Add controlled agents and behavior config results to summary
            self.results["summary"]["controlled_agents_result"] = controlled_agents_result
            self.results["summary"]["behavior_config_result"] = behavior_config_result

            # Step 7: Collect behavior statistics (if controlled agents were added)
            if controlled_agents_result.get("success"):
                self._print("\n" + "="*60, Colors.HEADER)
                self._print("Step 7: Collect Behavior Statistics", Colors.HEADER)
                self._print("="*60, Colors.HEADER)

                behavior_stats = self._collect_behavior_statistics()
                if behavior_stats:
                    self.results["summary"]["behavior_statistics"] = behavior_stats

                    # Print behavior statistics
                    if behavior_stats.get("statistics"):
                        stats = behavior_stats["statistics"]
                        strategy_stats = stats.get("strategy_statistics", {})
                        self._print("✓ Behavior Statistics:", Colors.OKGREEN)
                        self._print(f"  - Agents configured: {stats.get('agent_config_count', 0)}", Colors.OKCYAN)

                        for strategy, data in strategy_stats.items():
                            if data.get("count", 0) > 0:
                                self._print(f"  - {strategy}: {data.get('count', 0)} agents ({data.get('percentage', 0):.1f}%)", Colors.OKCYAN)

                    if behavior_stats.get("controller_status"):
                        status = behavior_stats["controller_status"]
                        engines = status.get("engines", {})
                        self._print("✓ Engine Status:", Colors.OKGREEN)
                        self._print(f"  - Probabilistic: {'available' if engines.get('probabilistic') else 'unavailable'}", Colors.OKCYAN)
                        self._print(f"  - Rule Engine: {'available' if engines.get('rule') else 'unavailable'}", Colors.OKCYAN)
                        self._print(f"  - Scheduling: {'available' if engines.get('scheduling') else 'unavailable'}", Colors.OKCYAN)
                else:
                    self._print("⚠ Could not collect behavior statistics", Colors.WARNING)

            # Step 8: Collect final OASIS metrics
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 8: Collect Final OASIS Metrics", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            final_metrics = self._collect_oasis_metrics()
            if final_metrics:
                self.results["summary"]["final_oasis_metrics"] = final_metrics

                # Print final metrics
                if final_metrics.get("propagation"):
                    prop = final_metrics["propagation"]
                    self._print("✓ Propagation Metrics:", Colors.OKGREEN)
                    self._print(f"  - Scale (users): {prop.get('scale', 0)}", Colors.OKCYAN)
                    self._print(f"  - Depth (levels): {prop.get('depth', 0)}", Colors.OKCYAN)
                    self._print(f"  - Max breadth: {prop.get('max_breadth', 0)}", Colors.OKCYAN)

                if final_metrics.get("herd_effect"):
                    herd = final_metrics["herd_effect"]
                    self._print("✓ Herd Effect Metrics:", Colors.OKGREEN)
                    self._print(f"  - Conformity index: {herd.get('conformity_index', 0):.3f}", Colors.OKCYAN)
                    self._print(f"  - Average post score: {herd.get('average_post_score', 0):.3f}", Colors.OKCYAN)
                    self._print(f"  - Disagree score: {herd.get('disagree_score', 0):.3f}", Colors.OKCYAN)

                if final_metrics.get("polarization"):
                    pol = final_metrics["polarization"]
                    self._print("✓ Polarization Metrics:", Colors.OKGREEN)
                    self._print(f"  - Average magnitude: {pol.get('average_magnitude', 0):.3f}", Colors.OKCYAN)
                    self._print(f"  - Average direction: {pol.get('average_direction', 'N/A')}", Colors.OKCYAN)
                    self._print(f"  - Agents evaluated: {pol.get('total_agents_evaluated', 0)}", Colors.OKCYAN)
            else:
                self._print("⚠ Could not collect final OASIS metrics", Colors.WARNING)

            # Validate metrics
            self._print("\n" + "="*60, Colors.HEADER)
            self._print("Step 9: Validate Metrics", Colors.HEADER)
            self._print("="*60, Colors.HEADER)

            validation_results = self._validate_metrics(final_metrics)
            self.results["summary"]["metrics_validation"] = validation_results
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

        # Execute step. Large agent counts are executed asynchronously by the
        # backend, so wait for the task before treating this step as complete.
        step_result = self.client.execute_step("auto")
        step_result = self._wait_for_step_completion(step_result)

        execution_time = time.time() - start_time

        # Get status after step
        status_after = self.client.get_simulation_status()

        # Get OASIS metrics after step
        oasis_metrics = self._collect_oasis_metrics()
        memory_debug = self._collect_memory_debug()

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
                },
                "oasis_metrics": oasis_metrics,
                "memory_debug": memory_debug,
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

            # Print OASIS metrics summary
            if oasis_metrics and oasis_metrics.get("propagation"):
                prop = oasis_metrics["propagation"]
                self._print(
                    f"  └─ Propagation: scale={prop.get('scale', 0)}, "
                    f"depth={prop.get('depth', 0)}, "
                    f"max_breadth={prop.get('max_breadth', 0)}",
                    Colors.OKCYAN
                )

            if oasis_metrics and oasis_metrics.get("herd_effect"):
                herd = oasis_metrics["herd_effect"]
                self._print(
                    f"  └─ Herd Effect: conformity={herd.get('conformity_index', 0):.2f}, "
                    f"avg_score={herd.get('average_post_score', 0):.2f}",
                    Colors.OKCYAN
                )

            if oasis_metrics and oasis_metrics.get("polarization"):
                pol = oasis_metrics["polarization"]
                self._print(
                    f"  └─ Polarization: magnitude={pol.get('average_magnitude', 0):.2f}, "
                    f"direction={pol.get('average_direction', 'N/A')}",
                    Colors.OKCYAN
                )

            if memory_debug:
                self._print(
                    "  └─ Memory: "
                    f"mode={memory_debug.get('memory_mode')}, "
                    f"recent_total={memory_debug.get('total_recent_retained')}, "
                    f"compressed_total={memory_debug.get('total_compressed_retained')}, "
                    f"recall_injected={memory_debug.get('total_recall_injected')}, "
                    f"max_prompt_tokens={memory_debug.get('max_prompt_tokens')}",
                    Colors.OKCYAN,
                )
        else:
            self._print_step(step_num, total_steps, f"Step failed: {step_result.get('message')}")

        return step_info

    def _wait_for_step_completion(self, step_result: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for a background step task and return the real StepResult."""
        task_id = step_result.get("task_id")
        if not task_id:
            return step_result

        poll_interval = 2.0
        deadline = time.time() + self.client.timeout
        self._print(f"  └─ Background step started: {task_id}", Colors.OKCYAN)

        while time.time() < deadline:
            task_payload = self.client.get_step_result(task_id)
            if task_payload.get("completed"):
                if task_payload.get("error"):
                    return {
                        "success": False,
                        "message": task_payload.get("error", "Background step failed"),
                        "task_id": task_id,
                        "step_executed": 0,
                        "actions_taken": 0,
                    }
                result = task_payload.get("result") or {}
                if isinstance(result, dict):
                    return result
                return {
                    "success": False,
                    "message": f"Unexpected background result: {result!r}",
                    "task_id": task_id,
                    "step_executed": 0,
                    "actions_taken": 0,
                }
            time.sleep(poll_interval)

        return {
            "success": False,
            "message": f"Timed out waiting for background step: {task_id}",
            "task_id": task_id,
            "step_executed": 0,
            "actions_taken": 0,
        }

    def _collect_oasis_metrics(self) -> Dict[str, Any]:
        """Collect all three OASIS metrics after a step"""
        try:
            # Get metrics summary (contains all three metrics)
            summary = self.client.get_metrics_summary()

            return {
                "propagation": summary.get("propagation"),
                "polarization": summary.get("polarization"),
                "herd_effect": summary.get("herd_effect"),
                "current_step": summary.get("current_step"),
                "timestamp": summary.get("timestamp"),
            }

        except Exception as e:
            # If metrics API fails, return None and continue
            self._print(f"  ⚠ Failed to collect OASIS metrics: {str(e)}", Colors.WARNING)
            return None

    def _collect_memory_debug(self) -> Dict[str, Any]:
        """Collect compact memory debug data after a step."""
        try:
            debug = self.client.get_memory_debug_status()
            agents = debug.get("agents", []) or []
            recent_total = sum(
                agent.get("recent_retained_step_count", 0) for agent in agents
            )
            compressed_total = sum(
                agent.get("compressed_retained_step_count", 0) for agent in agents
            )
            injected_total = sum(agent.get("last_injected_count", 0) for agent in agents)
            max_prompt_tokens = max(
                [agent.get("last_prompt_tokens", 0) for agent in agents] or [0]
            )
            max_observation_tokens = max(
                [agent.get("last_observation_prompt_tokens", 0) for agent in agents] or [0]
            )
            return {
                "memory_mode": debug.get("memory_mode"),
                "agent_count": debug.get("agent_count"),
                "context_token_limit": debug.get("context_token_limit"),
                "generation_max_tokens": debug.get("generation_max_tokens"),
                "total_recent_retained": recent_total,
                "total_compressed_retained": compressed_total,
                "total_recall_injected": injected_total,
                "max_prompt_tokens": max_prompt_tokens,
                "max_observation_tokens": max_observation_tokens,
            }
        except Exception as e:
            self._print(f"  ⚠ Failed to collect memory debug: {str(e)}", Colors.WARNING)
            return None

    # ============================================================================
    # Controlled Agents and Behavior Control Steps
    # ============================================================================

    def _add_controlled_agents_step(
        self,
        config_file: Optional[str],
        platform: str
    ) -> Dict[str, Any]:
        """
        步骤: 添加受控agents

        Args:
            config_file: 受控agents配置文件路径
            platform: 平台类型

        Returns:
            添加结果字典
        """
        if not config_file:
            return {"skipped": True, "reason": "No config file provided"}

        result = {
            "success": False,
            "added_count": 0,
            "agent_ids": [],
            "agents_results": [],
            "initial_polarization": None,
        }

        try:
            # 加载并验证配置
            self._print(f"\nLoading controlled agents config: {config_file}", Colors.OKCYAN)
            config = load_yaml_config(config_file)
            validate_controlled_agents_config(config)

            self._print(f"✓ Config loaded: {len(config['agents'])} agent(s) defined", Colors.OKGREEN)

            # 构建API请求
            request_data = {
                "agents": config["agents"],
                "check_polarization": config.get("check_polarization", False),
                "polarization_threshold": config.get("polarization_threshold", 0.6),
            }

            # 调用API添加受控agents
            self._print("Adding controlled agents...", Colors.OKCYAN)
            api_result = self.client.add_controlled_agents(request_data)

            result["success"] = api_result.get("success", False)
            result["added_count"] = api_result.get("added_count", 0)
            result["agent_ids"] = api_result.get("added_agent_ids", [])
            result["agents_results"] = api_result.get("results", [])
            result["initial_polarization"] = api_result.get("current_polarization")

            if result["success"]:
                self._print(f"✓ Successfully added {result['added_count']} controlled agent(s)", Colors.OKGREEN)
                self._print(f"  - Agent IDs: {result['agent_ids']}", Colors.OKCYAN)
                if result["initial_polarization"] is not None:
                    self._print(f"  - Current polarization: {result['initial_polarization']:.3f}", Colors.OKCYAN)
            else:
                self._print(f"✗ Failed to add controlled agents: {api_result.get('message')}", Colors.FAIL)

        except FileNotFoundError as e:
            self._print(f"✗ Config file not found: {e}", Colors.FAIL)
            result["error"] = str(e)
        except ValueError as e:
            self._print(f"✗ Invalid config: {e}", Colors.FAIL)
            result["error"] = str(e)
        except Exception as e:
            self._print(f"✗ Failed to add controlled agents: {e}", Colors.FAIL)
            result["error"] = str(e)

        return result

    def _apply_behavior_configurations_step(
        self,
        config_file: Optional[str],
        controlled_agent_ids: List[int],
        all_agent_count: int,
        platform: str
    ) -> Dict[str, Any]:
        """
        步骤: 应用行为策略配置

        Args:
            config_file: 行为配置文件路径
            controlled_agent_ids: 受控agent ID列表
            all_agent_count: 所有agent数量
            platform: 平台类型

        Returns:
            应用结果字典
        """
        if not config_file or not controlled_agent_ids:
            return {"skipped": True, "reason": "No config file or no controlled agents"}

        result = {
            "success": False,
            "applied_count": 0,
            "target_agents": [],
            "results": [],
        }

        try:
            # 加载并验证配置
            self._print(f"\nLoading behavior config: {config_file}", Colors.OKCYAN)
            config = load_yaml_config(config_file)
            validate_behavior_config(config)

            preset = config.get("preset")
            behavior_platform = config.get("platform", platform)
            target_agents = config.get("target_agents", "controlled")

            # 确定目标agents
            if target_agents == "controlled":
                target_agent_ids = controlled_agent_ids
            elif target_agents == "all":
                target_agent_ids = list(range(all_agent_count))
            elif "target_agent_ids" in config:
                target_agent_ids = config["target_agent_ids"]
            else:
                target_agent_ids = controlled_agent_ids

            result["target_agents"] = target_agent_ids

            if not target_agent_ids:
                self._print("⚠ No target agents to apply behavior config", Colors.WARNING)
                return {"skipped": True, "reason": "No target agents"}

            self._print(f"✓ Config loaded: preset={preset}, platform={behavior_platform}", Colors.OKGREEN)
            self._print(f"  - Target agents: {len(target_agent_ids)} agent(s)", Colors.OKCYAN)

            # 应用配置
            if preset:
                self._print(f"Applying preset '{preset}' to agents...", Colors.OKCYAN)

                applied_results = []
                for agent_id in target_agent_ids:
                    try:
                        api_result = self.client.apply_behavior_preset(
                            agent_id, preset, behavior_platform
                        )
                        applied_results.append({
                            "agent_id": agent_id,
                            "success": api_result.get("success", False),
                            "message": api_result.get("message", ""),
                        })
                        if api_result.get("success"):
                            result["applied_count"] += 1
                    except Exception as e:
                        applied_results.append({
                            "agent_id": agent_id,
                            "success": False,
                            "message": str(e),
                        })

                result["results"] = applied_results
                result["success"] = result["applied_count"] > 0

                if result["success"]:
                    self._print(f"✓ Successfully applied behavior config to {result['applied_count']} agent(s)", Colors.OKGREEN)
                else:
                    self._print("⚠ Failed to apply behavior config to any agent", Colors.WARNING)

        except FileNotFoundError as e:
            self._print(f"✗ Config file not found: {e}", Colors.FAIL)
            result["error"] = str(e)
        except ValueError as e:
            self._print(f"✗ Invalid config: {e}", Colors.FAIL)
            result["error"] = str(e)
        except Exception as e:
            self._print(f"✗ Failed to apply behavior config: {e}", Colors.FAIL)
            result["error"] = str(e)

        return result

    def _collect_behavior_statistics(self) -> Optional[Dict[str, Any]]:
        """
        收集行为控制统计信息

        Returns:
            行为统计信息字典
        """
        try:
            status = self.client.get_behavior_status()
            stats = self.client.get_behavior_statistics()

            return {
                "controller_status": status,
                "statistics": stats,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self._print(f"  ⚠ Failed to collect behavior statistics: {str(e)}", Colors.WARNING)
            return None

    def _validate_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证三大指标的合理性

        Args:
            metrics: 指标数据字典

        Returns:
            验证结果字典
        """
        validation = {
            "propagation": {"valid": False, "checks": []},
            "polarization": {"valid": False, "checks": []},
            "herd_effect": {"valid": False, "checks": []},
        }

        if not metrics:
            self._print("⚠ No metrics to validate", Colors.WARNING)
            return validation

        # 验证传播指标
        if metrics.get("propagation"):
            prop = metrics["propagation"]
            checks = []

            # 检查1: 规模 >= 0
            if prop.get("scale", -1) >= 0:
                checks.append({"check": "scale >= 0", "passed": True, "value": prop.get("scale")})
            else:
                checks.append({"check": "scale >= 0", "passed": False, "value": prop.get("scale")})

            # 检查2: 深度 >= 0
            if prop.get("depth", -1) >= 0:
                checks.append({"check": "depth >= 0", "passed": True, "value": prop.get("depth")})
            else:
                checks.append({"check": "depth >= 0", "passed": False, "value": prop.get("depth")})

            # 检查3: 最大宽度 >= 0
            if prop.get("max_breadth", -1) >= 0:
                checks.append({"check": "max_breadth >= 0", "passed": True, "value": prop.get("max_breadth")})
            else:
                checks.append({"check": "max_breadth >= 0", "passed": False, "value": prop.get("max_breadth")})

            # 检查4: 如果有帖子，规模应该 > 0
            if prop.get("scale", 0) > 0 and prop.get("post_id"):
                checks.append({"check": "has_propagation", "passed": True, "value": f"scale={prop.get('scale')}"})
            else:
                checks.append({"check": "has_propagation", "passed": False, "value": "no propagation detected"})

            validation["propagation"]["checks"] = checks
            validation["propagation"]["valid"] = all(c["passed"] for c in checks)

            self._print(f"{'✓' if validation['propagation']['valid'] else '⚠'} Propagation: {len([c for c in checks if c['passed']])}/{len(checks)} checks passed",
                        Colors.OKGREEN if validation['propagation']['valid'] else Colors.WARNING)

        # 验证羊群效应
        if metrics.get("herd_effect"):
            herd = metrics["herd_effect"]
            checks = []

            # 检查1: 一致性指数在 [0, 1] 范围内
            if 0 <= herd.get("conformity_index", -1) <= 1:
                checks.append({"check": "0 <= conformity_index <= 1", "passed": True, "value": herd.get("conformity_index")})
            else:
                checks.append({"check": "0 <= conformity_index <= 1", "passed": False, "value": herd.get("conformity_index")})

            # 检查2: 分歧得分 >= 0
            if herd.get("disagree_score", -1) >= 0:
                checks.append({"check": "disagree_score >= 0", "passed": True, "value": herd.get("disagree_score")})
            else:
                checks.append({"check": "disagree_score >= 0", "passed": False, "value": herd.get("disagree_score")})

            # 检查3: 有热门帖子数据
            hot_posts = herd.get("hot_posts", [])
            if isinstance(hot_posts, list):
                checks.append({"check": "has_hot_posts", "passed": True, "value": f"{len(hot_posts)} posts"})
            else:
                checks.append({"check": "has_hot_posts", "passed": False, "value": "invalid data type"})

            validation["herd_effect"]["checks"] = checks
            validation["herd_effect"]["valid"] = all(c["passed"] for c in checks)

            self._print(f"{'✓' if validation['herd_effect']['valid'] else '⚠'} Herd Effect: {len([c for c in checks if c['passed']])}/{len(checks)} checks passed",
                        Colors.OKGREEN if validation['herd_effect']['valid'] else Colors.WARNING)

        # 验证极化率
        if metrics.get("polarization"):
            pol = metrics["polarization"]
            checks = []

            # 检查1: 幅度在 [0, 1] 范围内
            if 0 <= pol.get("average_magnitude", -1) <= 1:
                checks.append({"check": "0 <= magnitude <= 1", "passed": True, "value": pol.get("average_magnitude")})
            else:
                checks.append({"check": "0 <= magnitude <= 1", "passed": False, "value": pol.get("average_magnitude")})

            # 检查2: 有有效的方向
            valid_directions = ["EXTREME_CONSERVATIVE", "MODERATE_CONSERVATIVE", "NEUTRAL", "MODERATE_PROGRESSIVE", "EXTREME_PROGRESSIVE"]
            if pol.get("average_direction") in valid_directions:
                checks.append({"check": "valid_direction", "passed": True, "value": pol.get("average_direction")})
            else:
                checks.append({"check": "valid_direction", "passed": False, "value": pol.get("average_direction")})

            # 检查3: 评估了至少1个agent
            if pol.get("total_agents_evaluated", 0) > 0:
                checks.append({"check": "agents_evaluated > 0", "passed": True, "value": pol.get("total_agents_evaluated")})
            else:
                checks.append({"check": "agents_evaluated > 0", "passed": False, "value": "no agents evaluated"})

            validation["polarization"]["checks"] = checks
            validation["polarization"]["valid"] = all(c["passed"] for c in checks)

            self._print(f"{'✓' if validation['polarization']['valid'] else '⚠'} Polarization: {len([c for c in checks if c['passed']])}/{len(checks)} checks passed",
                        Colors.OKGREEN if validation['polarization']['valid'] else Colors.WARNING)

        return validation

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
    """Export test results to JSON file and generate metrics charts"""

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, results: Dict[str, Any]) -> str:
        """Export results to JSON file and generate charts"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create timestamped subdirectory
        test_output_dir = self.output_dir / timestamp
        test_output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON file
        json_filename = f"test-result-{timestamp}.json"
        json_filepath = test_output_dir / json_filename

        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Generate metrics charts
        self._generate_metrics_charts(results, test_output_dir, timestamp)

        # Return the directory path instead of file path
        return str(test_output_dir)

    def _generate_metrics_charts(
        self,
        results: Dict[str, Any],
        output_dir: Path,
        timestamp: str
    ) -> List[str]:
        """
        Generate charts for all three OASIS metrics

        Args:
            results: Test results dictionary
            output_dir: Directory to save charts
            timestamp: Timestamp for filenames

        Returns:
            List of generated chart file paths
        """
        steps = results.get('steps', [])

        if not steps:
            print("Warning: No step data available for chart generation")
            return []

        # Extract step numbers and metrics data
        step_numbers = []
        propagation_scales = []
        propagation_depths = []
        propagation_breadths = []

        polarization_magnitudes = []
        polarization_agents_evaluated = []

        herd_conformity = []
        herd_avg_score = []
        herd_disagree = []

        for step in steps:
            if not step.get('success'):
                continue

            step_num = step.get('step_number')
            metrics = step.get('metrics', {}).get('oasis_metrics', {})

            step_numbers.append(step_num)

            # Propagation metrics
            prop = metrics.get('propagation', {})
            propagation_scales.append(prop.get('scale', 0))
            propagation_depths.append(prop.get('depth', 0))
            propagation_breadths.append(prop.get('max_breadth', 0))

            # Polarization metrics
            pol = metrics.get('polarization', {})
            polarization_magnitudes.append(pol.get('average_magnitude', 0))
            polarization_agents_evaluated.append(pol.get('total_agents_evaluated', 0))

            # Herd effect metrics
            herd = metrics.get('herd_effect', {})
            herd_conformity.append(herd.get('conformity_index', 0))
            herd_avg_score.append(herd.get('average_post_score', 0))
            herd_disagree.append(herd.get('disagree_score', 0))

        if not step_numbers:
            print("Warning: No successful steps with metrics data")
            return []

        chart_files = []

        # Generate three charts
        chart_files.append(self._plot_propagation_metrics(
            step_numbers, propagation_scales, propagation_depths, propagation_breadths,
            output_dir, timestamp
        ))

        chart_files.append(self._plot_polarization_metrics(
            step_numbers, polarization_magnitudes, polarization_agents_evaluated,
            output_dir, timestamp
        ))

        chart_files.append(self._plot_herd_effect_metrics(
            step_numbers, herd_conformity, herd_avg_score, herd_disagree,
            output_dir, timestamp
        ))

        return chart_files

    def _plot_propagation_metrics(
        self,
        steps: List[int],
        scales: List[int],
        depths: List[int],
        breadths: List[int],
        output_dir: Path,
        timestamp: str
    ) -> str:
        """Plot information propagation metrics over time"""
        fig, axes = plt.subplots(3, 1, figsize=(10, 12))
        fig.suptitle('Information Propagation Metrics Over Time', fontsize=16, fontweight='bold')

        # Scale (number of users)
        axes[0].plot(steps, scales, marker='o', linewidth=2, markersize=6, color='#2E86AB')
        axes[0].fill_between(steps, scales, alpha=0.3, color='#2E86AB')
        axes[0].set_ylabel('Scale (Users)', fontsize=12, fontweight='bold')
        axes[0].set_title('Propagation Scale - Total Users Reached', fontsize=11)
        axes[0].grid(True, alpha=0.3, linestyle='--')
        axes[0].set_xlabel('Simulation Step', fontsize=11)

        # Depth (number of levels)
        axes[1].plot(steps, depths, marker='s', linewidth=2, markersize=6, color='#A23B72')
        axes[1].fill_between(steps, depths, alpha=0.3, color='#A23B72')
        axes[1].set_ylabel('Depth (Levels)', fontsize=12, fontweight='bold')
        axes[1].set_title('Propagation Depth - Maximum Cascading Levels', fontsize=11)
        axes[1].grid(True, alpha=0.3, linestyle='--')
        axes[1].set_xlabel('Simulation Step', fontsize=11)

        # Max Breadth (users per level)
        axes[2].plot(steps, breadths, marker='^', linewidth=2, markersize=6, color='#F18F01')
        axes[2].fill_between(steps, breadths, alpha=0.3, color='#F18F01')
        axes[2].set_ylabel('Max Breadth (Users)', fontsize=12, fontweight='bold')
        axes[2].set_title('Maximum Breadth - Largest Single-Level Spread', fontsize=11)
        axes[2].grid(True, alpha=0.3, linestyle='--')
        axes[2].set_xlabel('Simulation Step', fontsize=11)

        plt.tight_layout()

        filename = f"propagation-metrics-{timestamp}.png"
        filepath = output_dir / filename
        plt.savefig(filepath, dpi=80, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def _plot_polarization_metrics(
        self,
        steps: List[int],
        magnitudes: List[float],
        agents_evaluated: List[int],
        output_dir: Path,
        timestamp: str
    ) -> str:
        """Plot group polarization metrics over time"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
        fig.suptitle('Group Polarization Metrics Over Time', fontsize=16, fontweight='bold')

        # Magnitude (0.0 - 1.0)
        color1 = '#C73E1D'
        ax1.plot(steps, magnitudes, marker='o', linewidth=2.5, markersize=7, color=color1)
        ax1.fill_between(steps, magnitudes, alpha=0.3, color=color1)
        ax1.set_ylabel('Magnitude', fontsize=12, fontweight='bold')
        ax1.set_title('Polarization Magnitude - Average Opinion Shift Intensity', fontsize=11)
        ax1.set_ylim(0, 1.0)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.axhline(y=0.5, color='gray', linestyle=':', linewidth=1.5, alpha=0.7, label='Moderate')
        ax1.legend(loc='upper right')
        ax1.set_xlabel('Simulation Step', fontsize=11)

        # Add interpretation text
        if magnitudes:
            latest_mag = magnitudes[-1]
            interpretation = "Neutral" if latest_mag < 0.3 else ("Moderate" if latest_mag < 0.7 else "Extreme")
            ax1.text(0.02, 0.98, f'Latest: {latest_mag:.3f} ({interpretation})',
                    transform=ax1.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # Agents evaluated
        color2 = '#6B4C9A'
        ax2.bar(steps, agents_evaluated, color=color2, alpha=0.7, edgecolor='black', linewidth=1.2)
        ax2.set_ylabel('Agents Count', fontsize=12, fontweight='bold')
        ax2.set_title('Number of Agents Evaluated for Polarization', fontsize=11)
        ax2.set_xlabel('Simulation Step', fontsize=11)
        ax2.grid(True, alpha=0.3, linestyle='--', axis='y')

        # Add count labels on bars
        for i, (step, count) in enumerate(zip(steps, agents_evaluated)):
            if count > 0:
                ax2.text(step, count + 0.1, str(count), ha='center', va='bottom', fontsize=9, fontweight='bold')

        plt.tight_layout()

        filename = f"polarization-metrics-{timestamp}.png"
        filepath = output_dir / filename
        plt.savefig(filepath, dpi=80, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def _plot_herd_effect_metrics(
        self,
        steps: List[int],
        conformity: List[float],
        avg_score: List[float],
        disagree_score: List[float],
        output_dir: Path,
        timestamp: str
    ) -> str:
        """Plot herd effect metrics over time"""
        fig, axes = plt.subplots(3, 1, figsize=(10, 12))
        fig.suptitle('Herd Effect Metrics Over Time', fontsize=16, fontweight='bold')

        # Conformity Index (Gini coefficient, 0-1)
        axes[0].plot(steps, conformity, marker='o', linewidth=2.5, markersize=7, color='#E63946')
        axes[0].fill_between(steps, conformity, alpha=0.3, color='#E63946')
        axes[0].set_ylabel('Conformity Index', fontsize=12, fontweight='bold')
        axes[0].set_title('Conformity Index - Engagement Inequality (Gini Coefficient)', fontsize=11)
        axes[0].set_ylim(0, 1.0)
        axes[0].grid(True, alpha=0.3, linestyle='--')

        # Add interpretation zones
        axes[0].axhspan(0, 0.3, alpha=0.2, color='green', label='Low Conformity')
        axes[0].axhspan(0.3, 0.7, alpha=0.2, color='yellow', label='Moderate')
        axes[0].axhspan(0.7, 1.0, alpha=0.2, color='red', label='High Conformity')
        axes[0].legend(loc='upper right', fontsize=9)
        axes[0].set_xlabel('Simulation Step', fontsize=11)

        # Add interpretation text
        if conformity:
            latest_conf = conformity[-1]
            level = "Low" if latest_conf < 0.3 else ("Moderate" if latest_conf < 0.7 else "High")
            axes[0].text(0.02, 0.98, f'Latest: {latest_conf:.3f} ({level})',
                        transform=axes[0].transAxes, fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # Average Post Score (likes - dislikes)
        axes[1].plot(steps, avg_score, marker='s', linewidth=2, markersize=7, color='#457B9D')
        axes[1].axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.5)
        axes[1].fill_between(steps, avg_score, alpha=0.3, color='#457B9D')
        axes[1].set_ylabel('Average Score', fontsize=12, fontweight='bold')
        axes[1].set_title('Average Post Score - Mean Net Engagement (Likes - Dislikes)', fontsize=11)
        axes[1].grid(True, alpha=0.3, linestyle='--')
        axes[1].set_xlabel('Simulation Step', fontsize=11)

        # Disagree Score (content diversity)
        axes[2].plot(steps, disagree_score, marker='^', linewidth=2.5, markersize=7, color='#1D3557')
        axes[2].fill_between(steps, disagree_score, alpha=0.3, color='#1D3557')
        axes[2].set_ylabel('Disagree Score', fontsize=12, fontweight='bold')
        axes[2].set_title('Disagree Score - Content Diversity & Viewpoint Variance', fontsize=11)
        axes[2].grid(True, alpha=0.3, linestyle='--')
        axes[2].set_xlabel('Simulation Step', fontsize=11)

        # Add interpretation text
        if disagree_score:
            latest_dis = disagree_score[-1]
            diversity = "Low" if latest_dis < 0.3 else ("Medium" if latest_dis < 0.7 else "High")
            axes[2].text(0.02, 0.98, f'Latest: {latest_dis:.3f} ({diversity} Diversity)',
                        transform=axes[2].transAxes, fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        filename = f"herd-effect-metrics-{timestamp}.png"
        filepath = output_dir / filename
        plt.savefig(filepath, dpi=80, bbox_inches='tight')
        plt.close()

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
  python backend/tests/e2e/e2e_simulation_test.py

  # Run with custom parameters
  python backend/tests/e2e/e2e_simulation_test.py --agent-count 10 --max-steps 20 --topic tech_ai_regulation

  # Run with Reddit platform
  python backend/tests/e2e/e2e_simulation_test.py --platform reddit --topic crypto_discussion

  # Run action_v1 memory route with compact tracking
  python backend/tests/e2e/e2e_simulation_test.py --memory-mode action_v1 --agent-count 3 --max-steps 3

  # Run quietly (no colored output)
  python backend/tests/e2e/e2e_simulation_test.py --no-verbose
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

    parser.add_argument(
        "--memory-mode",
        type=str,
        default=DEFAULT_MEMORY_MODE,
        choices=["upstream", "action_v1"],
        help=f"Memory route to use (default: {DEFAULT_MEMORY_MODE})"
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

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"LLM generation max tokens (default: {DEFAULT_MAX_TOKENS})"
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
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for test results (default: {DEFAULT_OUTPUT_DIR})"
    )

    parser.add_argument(
        "--no-verbose",
        action="store_true",
        help="Disable verbose output"
    )

    # Controlled agents and behavior control options
    parser.add_argument(
        "--controlled-agents-file",
        type=str,
        default=None,
        help="Path to YAML/JSON file defining controlled agents (optional)"
    )

    parser.add_argument(
        "--behavior-config-file",
        type=str,
        default=None,
        help="Path to YAML/JSON file for behavior configuration (optional)"
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
    print(f"  Memory Mode: {args.memory_mode}")
    print(f"  Model: {args.model_platform}/{args.model_type}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Max Tokens: {args.max_tokens}")
    print(f"  Base URL: {args.base_url}")
    print(f"  Output Dir: {args.output_dir}")
    if args.controlled_agents_file:
        print(f"  Controlled Agents: {args.controlled_agents_file}")
    if args.behavior_config_file:
        print(f"  Behavior Config: {args.behavior_config_file}")

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
            max_tokens=args.max_tokens,
            memory_mode=args.memory_mode,
            controlled_agents_file=args.controlled_agents_file,
            behavior_config_file=args.behavior_config_file,
        )

        # Export results
        exporter = ResultExporter(output_dir=args.output_dir)
        result_dir = exporter.export(results)

        # List generated files
        result_path = Path(result_dir)
        files = sorted(result_path.glob("*"))
        json_files = [f for f in files if f.suffix == '.json']
        image_files = [f for f in files if f.suffix == '.png']

        # Print success message
        print("\n" + Colors.OKGREEN + "="*60)
        print("✓ Test Completed Successfully!")
        print("="*60 + Colors.ENDC)
        print(f"\n📁 Results directory: {result_dir}")
        print(f"\nGenerated files ({len(files)} total):")

        if json_files:
            print(f"\n  📄 Data Files ({len(json_files)}):")
            for f in json_files:
                print(f"    - {f.name}")

        if image_files:
            print(f"\n  📊 Charts ({len(image_files)}):")
            for f in image_files:
                print(f"    - {f.name}")

        # Print summary
        summary = results["summary"]
        print("\nTest Summary:")
        print(f"  Steps executed: {summary['total_steps_executed']}")
        print(f"  Successful: {summary['successful_steps']}")
        print(f"  Failed: {summary['failed_steps']}")
        print(f"  Total time: {summary['total_execution_time']:.2f}s")
        print(f"  Avg step time: {summary['average_step_time']:.2f}s")
        print(f"  Posts created: {summary['total_posts_added']}")
        print(f"  Interactions: {summary['total_interactions_added']}")

        # Print OASIS metrics summary
        if summary.get("final_oasis_metrics"):
            metrics = summary["final_oasis_metrics"]
            print("\nFinal OASIS Metrics:")

            if metrics.get("propagation"):
                prop = metrics["propagation"]
                print("  Information Propagation:")
                print(f"    - Scale: {prop.get('scale', 0)} users")
                print(f"    - Depth: {prop.get('depth', 0)} levels")
                print(f"    - Max breadth: {prop.get('max_breadth', 0)} users")

            if metrics.get("herd_effect"):
                herd = metrics["herd_effect"]
                print("  Herd Effect:")
                print(f"    - Conformity index: {herd.get('conformity_index', 0):.3f}")
                print(f"    - Average post score: {herd.get('average_post_score', 0):.3f}")
                print(f"    - Disagree score: {herd.get('disagree_score', 0):.3f}")

            if metrics.get("polarization"):
                pol = metrics["polarization"]
                print("  Group Polarization:")
                print(f"    - Average magnitude: {pol.get('average_magnitude', 0):.3f}")
                print(f"    - Average direction: {pol.get('average_direction', 'N/A')}")
                print(f"    - Agents evaluated: {pol.get('total_agents_evaluated', 0)}")

        # Print metrics validation results
        if summary.get("metrics_validation"):
            validation = summary["metrics_validation"]
            print("\nMetrics Validation:")

            for metric_name, results in validation.items():
                if results.get("checks"):
                    passed = len([c for c in results["checks"] if c["passed"]])
                    total = len(results["checks"])
                    status = "✓" if results["valid"] else "⚠"
                    print(f"  {status} {metric_name.capitalize()}: {passed}/{total} checks passed")

                    # 显示失败的检查
                    failed_checks = [c for c in results["checks"] if not c["passed"]]
                    if failed_checks:
                        for check in failed_checks:
                            print(f"      - {check['check']}: {check['value']}")

        return 0

    except Exception as e:
        print("\n" + Colors.FAIL + "="*60)
        print("✗ Test Failed!")
        print("="*60 + Colors.ENDC)
        print(f"\nError: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
