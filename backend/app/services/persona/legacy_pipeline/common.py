from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def backend_root() -> Path:
    return Path(__file__).resolve().parents[4]


def data_dir() -> Path:
    override = os.environ.get("OASIS_DATASETS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return backend_root() / "data" / "datasets" / "data"


def load_backend_env(override: bool = True) -> None:
    env_path = backend_root() / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=override)
    else:
        load_dotenv(override=override)
