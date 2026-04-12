"""
依次执行：topics_classify → users_format_convert → relations_generate。
供 Node 或命令行一键跑完本地 ``datasets/data`` 流水线。

用法（在 ``oasis-dashboard`` 目录）::

    python -m oasis_dashboard.datasets.social_local_pipeline
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _dashboard_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    root = _dashboard_root()
    py = sys.executable
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    modules = (
        "oasis_dashboard.datasets.topics_classify",
        "oasis_dashboard.datasets.users_format_convert",
        "oasis_dashboard.datasets.relations_generate",
    )
    for mod in modules:
        print(f"[social_local_pipeline] running: {mod}", flush=True)
        proc = subprocess.run(
            [py, "-m", mod],
            cwd=str(root),
            env=env,
        )
        if proc.returncode != 0:
            print(f"[social_local_pipeline] failed: {mod} exit={proc.returncode}", file=sys.stderr, flush=True)
            return proc.returncode
    print("[social_local_pipeline] all steps ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
