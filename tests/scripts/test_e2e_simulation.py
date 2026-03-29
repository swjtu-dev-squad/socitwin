#!/usr/bin/env python3
"""
E2E Test Script: Simulate Frontend Operations with Intervention Support

This script mimics the frontend workflow:
1. Initialize simulation (POST /api/sim/config)
2. (Optional) Add controlled agents for intervention at specific step
3. Execute step-by-step (POST /api/sim/step)
4. Verify OASIS paper metrics:
   - Information Propagation (scale, depth, max_breadth, nrmse)
   - Group Polarization (round comparison: moreExtreme, moreProgressive, unchanged)
   - Herd Effect (Reddit hot score: herdEffectScore, hot/cold posts)
5. Display detailed results
6. Generate visualization charts

Usage:
    python test_e2e_simulation.py [agent_count] [num_steps] [base_url] [topics] [--intervention] [--intervention-step N] [--intervention-types T1,T2,T3]

Arguments:
    agent_count: Number of normal agents (default: 5)
    num_steps: Number of steps to execute (default: 5)
    base_url: Backend API base URL (default: http://localhost:3000)
    topics: Comma-separated topics (default: "AI")

Options:
    --intervention: Enable controlled agent intervention
    --intervention-step N: Add controlled agents at step N (default: 2)
    --intervention-types T1,T2,T3: Types of controlled agents (default: peace_messenger,fact_checker,moderator)

Examples:
    python test_e2e_simulation.py
    # Defaults: 5 agents, 5 steps, topic="AI", no intervention

    python test_e2e_simulation.py 10 10
    # 10 agents, 10 steps, topic="AI", no intervention

    python test_e2e_simulation.py 10 10 http://localhost:3000 "MiddleEast" --intervention
    # 10 agents, 10 steps, topic="MiddleEast", with default intervention at step 2

    python test_e2e_simulation.py 15 20 http://localhost:3000 "MiddleEast" --intervention --intervention-step 5 --intervention-types peace_messenger,fact_checker,moderator,humanitarian
    # 15 agents, 20 steps, topic="MiddleEast", with 4 controlled agents at step 5

Note: Seed posts are automatically loaded from the topic configuration file
      (prompts/topics/{topic}.json -> seed_posts field)
    Controlled agents are loaded from prompts/intervention.json
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import Dict, Any, List
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt

# 设置中文字体（可选）
try:
    matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
except:
    pass


class SimulationTester:
    """End-to-end simulation tester"""

    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.simulation_id = None
        self.steps_executed = 0
        self.intervention_enabled = False
        self.intervention_step = 2
        self.intervention_types = ["peace_messenger", "fact_checker", "moderator"]
        self.results = {
            "initialization": None,
            "intervention": None,
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
        regions: list = None,
        sampling_config: dict = None  # 🆕 Add sampling_config parameter (Issue #52)
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
            "regions": regions,
            "sampling_config": sampling_config,  # 🆕 Add sampling_config (Issue #52)
        }

        print(f"  🔍 DEBUG: Sending config to API: sampling_config = {sampling_config}")  # DEBUG

        print(f"  Configuration:")
        print(f"    • Agents: {agent_count}")
        print(f"    • Platform: {platform}")
        print(f"    • RecSys: {recsys}")
        print(f"    • Topics: {', '.join(topics)}")
        print(f"    • Regions: {', '.join(regions)}")
        if sampling_config:
            print(f"    • Sampling: {sampling_config.get('rate', 0)*100:.0f}% ({sampling_config.get('strategy', 'random')} strategy)")
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
                # Updated to use new OASIS metrics:
                # - propagation: scale, depth, max_breadth, round, nrmse
                # - round_comparison: moreExtreme, moreProgressive, unchanged
                # - herd_effect: herdEffectScore, hotPostsCount, coldPostsCount, behaviorDifference
                metrics = {
                    "step": step_number,
                    "elapsed_time": elapsed,
                    "current_step": result.get("current_step") or result.get("currentStep"),
                    "current_round": result.get("current_round") or result.get("currentRound"),
                    "total_posts": result.get("total_posts") or result.get("totalPosts"),
                    "active_agents": result.get("active_agents") or result.get("activeAgents"),
                    "polarization": result.get("polarization"),
                    "propagation": result.get("propagation"),
                    "round_comparison": result.get("round_comparison") or result.get("roundComparison"),
                    "herd_effect": result.get("herd_effect") or result.get("herdEffect"),
                }

                # Print metrics
                print(f"     Metrics:")
                self.print_metric("Current Step", metrics["current_step"])
                self.print_metric("Current Round", metrics["current_round"])
                self.print_metric("Total Posts", metrics["total_posts"])
                self.print_metric("Active Agents", metrics["active_agents"])
                self.print_metric("Polarization", f"{metrics['polarization']*100:.2f}", "%")

                # Print propagation metrics (OASIS paper)
                if metrics["propagation"]:
                    prop = metrics["propagation"]
                    print(f"     📊 Information Propagation:")
                    self.print_metric("  Scale (unique users)", prop.get("scale"))
                    self.print_metric("  Depth (max levels)", prop.get("depth"))
                    self.print_metric("  Max Breadth", prop.get("max_breadth"))
                    if prop.get("nrmse") is not None:
                        self.print_metric("  NRMSE", f"{prop.get('nrmse'):.4f}")

                # Print round comparison (OASIS paper)
                if metrics["round_comparison"]:
                    rc = metrics["round_comparison"]
                    print(f"     🔄 Group Polarization (Round Comparison):")
                    self.print_metric("  More Extreme/Conservative", f"{rc.get('moreExtreme', 0)*100:.1f}", "%")
                    self.print_metric("  More Progressive", f"{rc.get('moreProgressive', 0)*100:.1f}", "%")
                    self.print_metric("  Unchanged", f"{rc.get('unchanged', 0)*100:.1f}", "%")
                    if rc.get("llmEvaluation"):
                        print(f"     LLM Evaluation: {rc['llmEvaluation'][:100]}...")

                # Print herd effect metrics (OASIS paper - Reddit Hot Score)
                if metrics["herd_effect"]:
                    he = metrics["herd_effect"]
                    print(f"     🐑 Herd Effect (Reddit Hot Score):")
                    self.print_metric("  Herd Effect Score", f"{he.get('herdEffectScore', 0)*100:.1f}", "%")
                    self.print_metric("  Hot Posts", he.get("hotPostsCount"))
                    self.print_metric("  Cold Posts", he.get("coldPostsCount"))
                    self.print_metric("  Behavior Difference", f"{he.get('behaviorDifference', 0)*100:.1f}", "%")

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
        self.print_section("Verifying OASIS Metrics")

        if not self.results["metrics"]:
            print("  ❌ No metrics collected")
            return False

        all_valid = True

        # Check polarization
        polarizations = [m.get("polarization") for m in self.results["metrics"] if m.get("polarization") is not None]
        if polarizations:
            print(f"  ✅ Polarization: {len(polarizations)} measurements")
            print(f"     Range: {min(polarizations):.4f} - {max(polarizations):.4f}")

            # Verify polarization is in valid range
            invalid_pol = [p for p in polarizations if p < 0 or p > 1]
            if invalid_pol:
                print(f"  ❌ Invalid polarization values detected: {invalid_pol}")
                all_valid = False
        else:
            print(f"  ⚠️  Polarization: No measurements")
            all_valid = False

        # Check propagation metrics (OASIS paper)
        propagations = [m.get("propagation") for m in self.results["metrics"] if m.get("propagation")]
        if propagations:
            print(f"  ✅ Information Propagation: {len(propagations)} measurements")

            scales = [p.get("scale") for p in propagations if p.get("scale") is not None]
            if scales:
                print(f"     Scale (unique users): {min(scales)} - {max(scales)}")

            depths = [p.get("depth") for p in propagations if p.get("depth") is not None]
            if depths:
                print(f"     Depth (max levels): {min(depths)} - {max(depths)}")

            max_breadths = [p.get("max_breadth") for p in propagations if p.get("max_breadth") is not None]
            if max_breadths:
                print(f"     Max Breadth: {min(max_breadths)} - {max(max_breadths)}")
        else:
            print(f"  ⚠️  Information Propagation: No measurements")
            all_valid = False

        # Check round comparison metrics (OASIS paper)
        round_comparisons = [m.get("round_comparison") for m in self.results["metrics"] if m.get("round_comparison")]
        if round_comparisons:
            print(f"  ✅ Group Polarization (Round Comparison): {len(round_comparisons)} measurements")

            # Verify proportions sum to 1
            for i, rc in enumerate(round_comparisons):
                total = rc.get("moreExtreme", 0) + rc.get("moreProgressive", 0) + rc.get("unchanged", 0)
                if abs(total - 1.0) > 0.01:
                    print(f"  ⚠️  Round {i+1} comparison proportions don't sum to 1: {total:.3f}")
        else:
            print(f"  ⚠️  Group Polarization (Round Comparison): No measurements (may be Round 0)")

        # Check herd effect metrics (OASIS paper - Reddit Hot Score)
        herd_effects = [m.get("herd_effect") for m in self.results["metrics"] if m.get("herd_effect")]
        if herd_effects:
            print(f"  ✅ Herd Effect (Reddit Hot Score): {len(herd_effects)} measurements")

            scores = [he.get("herdEffectScore") for he in herd_effects if he.get("herdEffectScore") is not None]
            if scores:
                print(f"     Herd Effect Score: {min(scores):.4f} - {max(scores):.4f}")

                # Verify score is in valid range
                invalid_scores = [s for s in scores if s < 0 or s > 1]
                if invalid_scores:
                    print(f"  ❌ Invalid herd effect scores detected: {invalid_scores}")
                    all_valid = False

            hot_counts = [he.get("hotPostsCount") for he in herd_effects if he.get("hotPostsCount") is not None]
            cold_counts = [he.get("coldPostsCount") for he in herd_effects if he.get("coldPostsCount") is not None]

            if hot_counts and cold_counts:
                print(f"     Hot Posts: {min(hot_counts)} - {max(hot_counts)}")
                print(f"     Cold Posts: {min(cold_counts)} - {max(cold_counts)}")
        else:
            print(f"  ⚠️  Herd Effect (Reddit Hot Score): No measurements")
            all_valid = False

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
            print(f"    Step | Round | Posts | Polarization | Propagation | Herd Effect")
            print(f"    -----|-------|-------|--------------|-------------|-------------")
            for m in self.results["metrics"]:
                step = m.get("step", "-")
                round_num = m.get("current_round") if m.get("current_round") is not None else "-"
                posts = m.get("total_posts", "-")
                pol = f"{m.get('polarization', 0)*100:.1f}%" if m.get("polarization") is not None else "-"

                # Propagation summary
                prop = m.get("propagation")
                if prop:
                    prop_summary = f"S:{prop.get('scale', 0)} D:{prop.get('depth', 0)}"
                else:
                    prop_summary = "-"

                # Herd effect summary
                he = m.get("herd_effect")
                if he:
                    he_summary = f"{he.get('herdEffectScore', 0)*100:.0f}%"
                else:
                    he_summary = "-"

                # Safe formatting with None handling
                step_str = f"{step:5}" if step != "-" else "    -"
                round_str = f"{round_num:5}" if round_num != "-" else "    -"
                posts_str = f"{posts:5}" if posts != "-" else "    -"

                print(f"    {step_str} | {round_str} | {posts_str} | {pol:12} | {prop_summary:11} | {he_summary:11}")

    def generate_charts(self, output_dir: str = "test-results"):
        """Generate visualization charts for the three OASIS metrics"""
        if not self.results["metrics"]:
            print("  ⚠️  No metrics to visualize")
            return

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        # 准备数据
        steps = [m.get("step") for m in self.results["metrics"]]

        # 1. Information Propagation Chart
        self._plot_propagation(steps, output_dir, timestamp)

        # 2. Group Polarization Chart
        self._plot_polarization(steps, output_dir, timestamp)

        # 3. Herd Effect Chart
        self._plot_herd_effect(steps, output_dir, timestamp)

        print(f"\n  📊 Charts saved to: {output_dir}/")

    def _plot_propagation(self, steps: List[int], output_dir: str, timestamp: str):
        """Plot Information Propagation metrics"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))
        fig.suptitle('Information Propagation Metrics Over Steps', fontsize=16, fontweight='bold')

        # Scale (unique users)
        scales = []
        for m in self.results["metrics"]:
            prop = m.get("propagation")
            scales.append(prop.get("scale") if prop else 0)

        ax1.plot(steps, scales, marker='o', linewidth=2, markersize=6, color='#2E86AB')
        ax1.set_xlabel('Step', fontsize=12)
        ax1.set_ylabel('Scale (Unique Users)', fontsize=12)
        ax1.set_title('Propagation Scale - Number of Unique Users', fontsize=14)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(bottom=0)

        # Depth (max levels)
        depths = []
        for m in self.results["metrics"]:
            prop = m.get("propagation")
            depths.append(prop.get("depth") if prop else 0)

        ax2.plot(steps, depths, marker='s', linewidth=2, markersize=6, color='#A23B72')
        ax2.set_xlabel('Step', fontsize=12)
        ax2.set_ylabel('Depth (Max Levels)', fontsize=12)
        ax2.set_title('Propagation Depth - Maximum Tree Depth', fontsize=14)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(bottom=0)
        ax2.set_yticks(sorted(set(depths)))

        # Max Breadth
        breadths = []
        for m in self.results["metrics"]:
            prop = m.get("propagation")
            breadths.append(prop.get("max_breadth") if prop else 0)

        ax3.plot(steps, breadths, marker='^', linewidth=2, markersize=6, color='#F18F01')
        ax3.set_xlabel('Step', fontsize=12)
        ax3.set_ylabel('Max Breadth', fontsize=12)
        ax3.set_title('Propagation Breadth - Maximum Nodes at Any Level', fontsize=14)
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(bottom=0)
        ax3.set_yticks(sorted(set(breadths)))

        plt.tight_layout()
        filepath = f"{output_dir}/propagation_{timestamp}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✅ Propagation chart: {filepath}")

    def _plot_polarization(self, steps: List[int], output_dir: str, timestamp: str):
        """Plot Group Polarization metrics"""
        fig, ax = plt.subplots(figsize=(12, 6))

        # Polarization score
        polarizations = []
        for m in self.results["metrics"]:
            pol = m.get("polarization")
            polarizations.append(pol * 100 if pol is not None else 0)

        ax.plot(steps, polarizations, marker='o', linewidth=2.5, markersize=7,
                color='#E63946', label='Polarization Score')

        # 添加趋势线
        if len(polarizations) > 1:
            z = np.polyfit(steps, polarizations, 2)
            p = np.poly1d(z)
            steps_smooth = np.linspace(min(steps), max(steps), 100)
            ax.plot(steps_smooth, p(steps_smooth), '--', linewidth=2, color='#E63946', alpha=0.5,
                   label='Trend (2nd order polynomial)')

        ax.set_xlabel('Step', fontsize=14)
        ax.set_ylabel('Polarization Score (%)', fontsize=14)
        ax.set_title('Group Polarization Over Time', fontsize=16, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)

        # 添加数据点标注
        for i, (step, pol) in enumerate(zip(steps, polarizations)):
            if i % max(1, len(steps) // 5) == 0:  # 只标注部分点，避免拥挤
                ax.annotate(f'{pol:.1f}%', xy=(step, pol), xytext=(5, 5),
                           textcoords='offset points', fontsize=9, alpha=0.7)

        plt.tight_layout()
        filepath = f"{output_dir}/polarization_{timestamp}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✅ Polarization chart: {filepath}")

    def _plot_herd_effect(self, steps: List[int], output_dir: str, timestamp: str):
        """Plot Herd Effect metrics"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))
        fig.suptitle('Herd Effect Metrics (Reddit Hot Score Algorithm)', fontsize=16, fontweight='bold')

        # Herd Effect Score
        scores = []
        for m in self.results["metrics"]:
            he = m.get("herd_effect")
            # ✅ 兼容两种命名方式：snake_case 和 camelCase
            score = None
            if he:
                score = he.get("herd_effect_score") or he.get("herdEffectScore")
            scores.append((score or 0) * 100)

        ax1.plot(steps, scores, marker='o', linewidth=2, markersize=6, color='#06A77D')
        ax1.set_xlabel('Step', fontsize=12)
        ax1.set_ylabel('Herd Effect Score (%)', fontsize=12)
        ax1.set_title('Herd Effect Score - Strength of Herd Behavior', fontsize=14)
        ax1.grid(True, alpha=0.3)

        # ✅ 自适应坐标范围（如果有数据，留 10% 顶部空间）
        max_score = max(scores) if scores else 0
        if max_score > 0:
            ax1.set_ylim(0, max(max_score * 1.1, 10))  # 至少显示到 10%，或 max*1.1
            ax1.axhline(y=max_score / 2, color='r', linestyle='--', alpha=0.3, label='50% threshold')
            ax1.legend()
        else:
            ax1.set_ylim(0, 100)  # 默认范围

        # Hot vs Cold Posts
        hot_counts = []
        cold_counts = []
        for m in self.results["metrics"]:
            he = m.get("herd_effect")
            # ✅ 兼容两种命名方式
            if he:
                hot_counts.append(he.get("hot_posts_count") or he.get("hotPostsCount") or 0)
                cold_counts.append(he.get("cold_posts_count") or he.get("coldPostsCount") or 0)
            else:
                hot_counts.append(0)
                cold_counts.append(0)

        ax2.plot(steps, hot_counts, marker='^', linewidth=2, markersize=6, color='#FF6B35', label='Hot Posts')
        ax2.plot(steps, cold_counts, marker='s', linewidth=2, markersize=6, color='#4D908E', label='Cold Posts')
        ax2.set_xlabel('Step', fontsize=12)
        ax2.set_ylabel('Post Count', fontsize=12)
        ax2.set_title('Hot vs Cold Posts Classification', fontsize=14)
        ax2.legend(loc='best', fontsize=11)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(bottom=0)

        # Behavior Difference
        differences = []
        for m in self.results["metrics"]:
            he = m.get("herd_effect")
            # ✅ 兼容两种命名方式
            diff = None
            if he:
                diff = he.get("behavior_difference") or he.get("behaviorDifference")
            differences.append((diff or 0) * 100)

        ax3.plot(steps, differences, marker='D', linewidth=2, markersize=6, color='#F77F00')
        ax3.fill_between(steps, differences, alpha=0.3, color='#F77F00')
        ax3.set_xlabel('Step', fontsize=12)
        ax3.set_ylabel('Behavior Difference (%)', fontsize=12)
        ax3.set_title('Engagement Difference Between Hot and Cold Posts', fontsize=14)
        ax3.grid(True, alpha=0.3)

        # ✅ 自适应坐标范围
        max_diff = max(differences) if differences else 0
        if max_diff > 0:
            ax3.set_ylim(0, max(max_diff * 1.2, 1))  # 留 20% 顶部空间
        else:
            ax3.set_ylim(0, 100)  # 默认范围

        plt.tight_layout()
        filepath = f"{output_dir}/herd_effect_{timestamp}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✅ Herd Effect chart: {filepath}")

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

    def add_controlled_agents_intervention(self) -> bool:
        """Add controlled agents for intervention"""
        self.print_section("Adding Controlled Agents (Intervention)")

        try:
            response = requests.post(
                f"{self.base_url}/api/sim/intervention/batch",
                json={
                    "intervention_types": self.intervention_types,
                    "initial_step": True
                },
                timeout=60
            )
            response.raise_for_status()
            response_data = response.json()

            # Handle JSON-RPC format
            if "result" in response_data:
                result = response_data["result"]
            elif "status" in response_data:
                result = response_data
            else:
                result = response_data

            if result.get("status") == "ok":
                print(f"  ✅ Intervention successful")
                print(f"    • Created: {result.get('total', 0)} controlled agents")

                for agent_info in result.get("created_agents", []):
                    print(f"      - Agent {agent_info['agent_id']}: {agent_info['user_name']} ({agent_info['type']})")

                self.results["intervention"] = {
                    "success": True,
                    "step": self.steps_executed,
                    "intervention_types": self.intervention_types,
                    "created_agents": result.get("created_agents", [])
                }
                return True
            else:
                error_msg = result.get("message", "Unknown error")
                print(f"  ❌ Intervention failed: {error_msg}")
                self.results["errors"].append({
                    "stage": "intervention",
                    "error": error_msg
                })
                return False

        except Exception as e:
            print(f"  ❌ Intervention request failed: {e}")
            self.results["errors"].append({
                "stage": "intervention",
                "error": str(e)
            })
            return False

    def run_full_test(
        self,
        agent_count: int = 5,
        num_steps: int = 5,
        platform: str = "reddit",
        topics: list = None,
        sampling_config: dict = None  # 🆕 Add sampling_config parameter (Issue #52)
    ):
        """Run complete end-to-end test"""
        print("\n" + "🚀" * 30)
        print("  OASIS Dashboard E2E Test")
        print("  Simulating Frontend Workflow")

        if self.intervention_enabled:
            print(f"  🎭 Intervention: ENABLED (step {self.intervention_step}, types: {', '.join(self.intervention_types)})")

        print("🚀" * 30)

        # Reset
        if not self.reset_simulation():
            return False

        # Initialize
        init_result = self.initialize_simulation(
            agent_count=agent_count,
            platform=platform,
            topics=topics,
            sampling_config=sampling_config  # 🆕 Pass sampling_config (Issue #52)
        )

        if not init_result:
            return False

        # Execute steps
        self.print_section(f"Executing {num_steps} Steps")

        for step in range(1, num_steps + 1):
            # 检查是否需要添加干预
            if self.intervention_enabled and step == self.intervention_step:
                print(f"\n  🎯 Triggering intervention at step {step}...")
                if not self.add_controlled_agents_intervention():
                    print(f"\n  ⚠️  Intervention failed, but continuing test...")

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

        # Generate visualization charts
        self.print_section("Generating Visualization Charts")
        self.generate_charts()

        # Save results
        self.save_results()

        return metrics_valid and len(self.results["errors"]) == 0


def main():
    """Main entry point"""
    import sys
    import os
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="OASIS Dashboard E2E Test with Intervention Support",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("agent_count", type=int, nargs="?", default=5,
                       help="Number of normal agents (default: 5)")
    parser.add_argument("num_steps", type=int, nargs="?", default=5,
                       help="Number of steps to execute (default: 5)")
    parser.add_argument("base_url", nargs="?", default="http://localhost:3000",
                       help="Backend API base URL (default: http://localhost:3000)")
    parser.add_argument("topics", nargs="?", default="AI",
                       help="Comma-separated topics (default: AI)")

    # Intervention arguments
    parser.add_argument("--intervention", action="store_true",
                       help="Enable controlled agent intervention")
    parser.add_argument("--intervention-step", type=int, default=2, metavar="N",
                       help="Add controlled agents at step N (default: 2)")
    parser.add_argument("--intervention-types", default="peace_messenger,fact_checker,moderator",
                       metavar="T1,T2,T3",
                       help="Types of controlled agents (comma-separated, default: peace_messenger,fact_checker,moderator)")

    # 🆕 Agent sampling arguments (Issue #52)
    parser.add_argument("--sampling-rate", type=float, default=None, metavar="RATE",
                       help="Agent sampling rate (0.0-1.0, e.g., 0.1 for 10%%. Default: disabled)")
    parser.add_argument("--sampling-strategy", default="random", metavar="STRATEGY",
                       choices=["random", "weighted", "stratified"],
                       help="Sampling strategy: random, weighted, or stratified (default: random)")
    parser.add_argument("--sampling-min-active", type=int, default=5, metavar="N",
                       help="Minimum active agents when sampling (default: 5)")
    parser.add_argument("--sampling-seed", type=int, default=42, metavar="SEED",
                       help="Random seed for sampling reproducibility (default: 42)")

    args = parser.parse_args()

    # Parse topics
    topics = [t.strip() for t in args.topics.split(",")]

    # Setup tester
    tester = SimulationTester(base_url=args.base_url)
    tester.intervention_enabled = args.intervention
    tester.intervention_step = args.intervention_step
    tester.intervention_types = args.intervention_types.split(",")

    # 🆕 Build sampling config if rate is specified (Issue #52)
    sampling_config = None
    print(f"  🔍 DEBUG: args.sampling_rate = {args.sampling_rate}")  # DEBUG
    if args.sampling_rate is not None:
        sampling_config = {
            "enabled": True,
            "rate": args.sampling_rate,
            "strategy": args.sampling_strategy,
            "min_active": args.sampling_min_active,
            "seed": args.sampling_seed,
        }
        print(f"  🎯 Sampling enabled: {args.sampling_rate*100:.0f}% rate, {args.sampling_strategy} strategy")
        print(f"  🔍 DEBUG: sampling_config = {sampling_config}")  # DEBUG
    else:
        print(f"  🔍 DEBUG: sampling_rate is None, sampling disabled")  # DEBUG

    try:
        success = tester.run_full_test(
            agent_count=args.agent_count,
            num_steps=args.num_steps,
            platform="reddit",
            topics=topics,
            sampling_config=sampling_config  # 🆕 Pass sampling config (Issue #52)
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
