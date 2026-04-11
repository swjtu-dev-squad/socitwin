"""
stdin: JSON
  selected_topics: list[{"topic_key": str, "topic_label": str}, ...]
  synthetic_topic_count: int
  seed_users: list[dict]
  user_target_count: int
  dataset_id: str
  recsys_type: str
  batch_size?, seed_sample?, max_retries?, kol_normal_ratio?

stdout: JSON
  status, topics, users, meta
"""

from __future__ import annotations

import json
import logging
import sys
import warnings

warnings.filterwarnings("ignore", category=Warning, module="requests")

from dotenv import load_dotenv

from oasis_dashboard.context import build_shared_model
from oasis_dashboard.persona_llm_batch import (
    generate_llm_persona_users,
    generate_synthetic_topics,
    model_spec_from_env,
)


def _parse_ratio(s: str) -> tuple[int, int]:
    raw = (s or "").strip()
    if not raw:
        return (1, 10)
    if ":" not in raw:
        raise ValueError("kol_normal_ratio 需形如 '1:10'")
    a, b = raw.split(":", 1)
    x = int(a.strip())
    y = int(b.strip())
    if x < 0 or y < 0 or (x == 0 and y == 0):
        raise ValueError("kol_normal_ratio 必须为非负整数，且不能同时为 0")
    return (x, y)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    load_dotenv()
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(
            json.dumps(
                {"status": "error", "error": f"stdin JSON 无效: {e}", "type": "topics_users_llm_worker"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
        sys.exit(1)

    try:
        selected = payload.get("selected_topics") or []
        if not isinstance(selected, list) or not selected:
            raise ValueError("selected_topics 必须为非空数组")
        syn_n = int(payload.get("synthetic_topic_count") or 0)
        if syn_n < 1:
            raise ValueError("synthetic_topic_count 须 >= 1")

        seed_users = payload.get("seed_users") or []
        if not isinstance(seed_users, list) or not seed_users:
            raise ValueError("seed_users 必须为非空数组")

        user_target_count = int(payload.get("user_target_count") or 0)
        if user_target_count < 1:
            raise ValueError("user_target_count 须 >= 1")

        dataset_id = str(payload.get("dataset_id") or "").strip()
        if not dataset_id:
            raise ValueError("dataset_id 不能为空")
        recsys_type = str(payload.get("recsys_type") or "twitter").strip()

        batch_size = int(payload.get("batch_size") or 8)
        seed_sample = int(payload.get("seed_sample") or 12)
        max_retries = int(payload.get("max_retries") or 3)
        kol_normal_ratio = str(payload.get("kol_normal_ratio") or "1:10").strip()
        kol_ratio = _parse_ratio(kol_normal_ratio)

        spec = model_spec_from_env()
        resolved = build_shared_model(spec)
        model = resolved.model

        topics = generate_synthetic_topics(
            model,
            selected_topics=selected,
            topic_count=syn_n,
            max_retries=max(1, min(10, max_retries)),
        )
        topics_text = json.dumps(topics, ensure_ascii=False, indent=2)
        topic_titles = [
            str(t.get("title") or "").strip()
            for t in topics
            if isinstance(t, dict) and str(t.get("title") or "").strip()
        ]

        users, meta = generate_llm_persona_users(
            seed_users,
            target_count=max(1, min(2000, user_target_count)),
            dataset_id=dataset_id,
            recsys_type=recsys_type,
            batch_size=max(2, min(32, batch_size)),
            seed_sample=max(3, min(40, seed_sample)),
            max_retries=max(1, min(10, max_retries)),
            kol_normal_ratio=kol_ratio,
            global_context=topics_text,
            synthetic_topic_titles=topic_titles,
        )
        meta = dict(meta or {})
        meta["synthetic_topics"] = topics
        meta["synthetic_topic_count_requested"] = syn_n
        meta["synthetic_topic_count_actual"] = len(topics)

        print(
            json.dumps(
                {"status": "ok", "topics": topics, "users": users, "meta": meta},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
    except Exception as e:
        print(
            json.dumps(
                {"status": "error", "error": str(e), "type": "topics_users_llm_worker"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
