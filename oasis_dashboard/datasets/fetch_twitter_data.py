#!/usr/bin/env python3
"""
Twitter realtime fetch CLI wrapper.

Purpose:
The Node backend calls a Python script via `spawn(python ... scriptPath --json ...)`.
We keep the original implementation at the repository root
(`fetch_twitter_data.py`) and forward execution from this standardized location:
`oasis_dashboard/datasets/fetch_twitter_data.py`.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    # This file: oasis_dashboard/datasets/fetch_twitter_data.py
    # Target:   ./fetch_twitter_data.py (repo root)
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "fetch_twitter_data.py"

    if not target.is_file():
        raise FileNotFoundError(f"Cannot find target script: {target}")

    # Run the target script as if it were executed directly (so __name__ == "__main__").
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()

