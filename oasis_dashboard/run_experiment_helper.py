#!/usr/bin/env python3
"""Helper script for running experiments from server.ts via execSync."""
import sys
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oasis_dashboard.experiment_runner import ExperimentConfig, run_experiment
from oasis_dashboard.compare_analyzer import generate_compare_charts, generate_compare_report_md


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--dataset-id', required=True)
    parser.add_argument('--dataset-path', required=True)
    parser.add_argument('--recommenders', required=True)  # JSON array string
    parser.add_argument('--platform', default='REDDIT')
    parser.add_argument('--steps', type=int, default=15)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--agent-count', type=int, default=10)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()

    recommenders = json.loads(args.recommenders)
    config = ExperimentConfig(
        name=args.name,
        dataset_id=args.dataset_id,
        platform=args.platform,
        recommenders=recommenders,
        steps=args.steps,
        seed=args.seed,
        agent_count=args.agent_count,
    )

    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)

    result = run_experiment(config, dataset_path, output_dir=output_dir)
    result_json = output_dir / 'result.json'

    # Generate compare charts and report
    try:
        generate_compare_charts(result_json, output_dir)
    except Exception:
        pass
    try:
        rpt = generate_compare_report_md(result_json)
        (output_dir / 'compare.md').write_text(rpt, encoding='utf-8')
    except Exception:
        pass

    with open(result_json) as f:
        data = json.load(f)
    print(json.dumps(data))


if __name__ == '__main__':
    main()
