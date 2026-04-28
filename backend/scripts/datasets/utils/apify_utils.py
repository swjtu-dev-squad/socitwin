"""
Shared Apify utilities.

Provides secure key loading and HTTP-based Apify actor invocation
used by both the Facebook and Instagram fetcher scripts.
"""

import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_PLACEHOLDER = "your-apify-api-key-here"


def get_apify_key() -> str:
    """Return the Apify API token.

    Resolution order:
      1. ``APIFY_KEY`` environment variable
      2. First ``APIFY_KEY=`` line found in the *backend* ``.env`` file
         (resolved relative to this file so the script works regardless
         of the caller's working directory).

    Raises ``RuntimeError`` if no key is found.
    """
    key = os.getenv("APIFY_KEY", "").strip()
    if key and key != _PLACEHOLDER:
        return key

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        # Warn if the file is world-readable (permissions looser than 0o600).
        mode = env_path.stat().st_mode
        if mode & stat.S_IRWXO:
            import sys

            print(
                f"[WARN] {env_path} is world-readable (mode {oct(mode & 0o777)}). "
                "Consider running: chmod 600 <path>",
                file=sys.stderr,
            )
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("APIFY_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != _PLACEHOLDER:
                    return key

    raise RuntimeError(
        "APIFY_KEY not found. Set the APIFY_KEY environment variable or "
        "add APIFY_KEY=<your-key> to backend/.env"
    )


def run_apify_actor(
    token: str,
    actor: str,
    payload: dict[str, Any],
    timeout: int = 35,
) -> list[dict[str, Any]]:
    """Call an Apify Actor synchronously and return the dataset items.

    The API token is sent via the ``Authorization: Bearer`` header instead of
    a query parameter to avoid leaking it into server access logs.
    """
    actor_id = actor.replace("/", "~")
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?clean=true"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            return parsed if isinstance(parsed, list) else []
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Apify error: HTTP {exc.code}") from exc
