"""
stdin: JSON
  seed_users: list[dict]
  target_count: int
  dataset_id: str
  recsys_type: str
  batch_size?: int
  seed_sample?: int
  max_retries?: int

stdout: JSON
  status: "ok" | "error"
  users?: list (raw.users 形态)
  meta?: dict
  error?: str
  type?: str
"""

from __future__ import annotations

import json
import logging
import sys
import warnings

# 须在 import camel/requests 之前注册，避免 urllib3 版本告警淹没 stderr
warnings.filterwarnings("ignore", category=Warning, module="requests")

from dotenv import load_dotenv

from oasis_dashboard.persona_llm_batch import generate_llm_persona_users


def _parse_ratio(s: str) -> tuple[int, int]:
    raw = (s or "").strip()
    if not raw:
        return (1, 8)
    if ":" not in raw:
        raise ValueError("kol_normal_ratio 需形如 '1:8'")
    a, b = raw.split(":", 1)
    x = int(a.strip())
    y = int(b.strip())
    if x < 0 or y < 0 or (x == 0 and y == 0):
        raise ValueError("kol_normal_ratio 必须为非负整数，且不能同时为 0")
    return (x, y)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    load_dotenv()
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(
            json.dumps(
                {"status": "error", "error": f"stdin JSON 无效: {e}", "type": "llm_persona_worker"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
        sys.exit(1)

    try:
        seed_users = payload.get("seed_users") or []
        target_count = int(payload.get("target_count", 0))
        dataset_id = str(payload.get("dataset_id") or "").strip()
        recsys_type = str(payload.get("recsys_type") or "unknown").strip()
        batch_size = int(payload.get("batch_size") or 8)
        seed_sample = int(payload.get("seed_sample") or 12)
        max_retries = int(payload.get("max_retries") or 3)
        kol_normal_ratio = str(payload.get("kol_normal_ratio") or "1:8").strip()
        kol_ratio = _parse_ratio(kol_normal_ratio)

        if not isinstance(seed_users, list) or not seed_users:
            raise ValueError("seed_users 必须为非空数组")
        if target_count < 1:
            raise ValueError("target_count 须 >= 1")
        if not dataset_id:
            raise ValueError("dataset_id 不能为空")

        users, meta = generate_llm_persona_users(
            seed_users,
            target_count=target_count,
            dataset_id=dataset_id,
            recsys_type=recsys_type,
            batch_size=max(2, min(32, batch_size)),
            seed_sample=max(3, min(40, seed_sample)),
            max_retries=max(1, min(10, max_retries)),
            kol_normal_ratio=kol_ratio,
        )
        # 单行 JSON + flush，便于 Node 解析（避免与依赖库 stdout 混排时整段 parse 失败）
        print(
            json.dumps(
                {"status": "ok", "users": users, "meta": meta},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
    except Exception as e:
        print(
            json.dumps(
                {"status": "error", "error": str(e), "type": "llm_persona_worker"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
