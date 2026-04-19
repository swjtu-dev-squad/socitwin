from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.persona.legacy_pipeline.common import data_dir


def _load_title_to_category(topics_path: Path) -> dict[str, str]:
    raw = json.loads(topics_path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for block in raw.get("data") or []:
        if not isinstance(block, dict):
            continue
        cat = block.get("category")
        if not isinstance(cat, str) or not cat.strip():
            continue
        for t in block.get("topics") or []:
            if isinstance(t, str) and t.strip():
                out[t.strip()] = cat.strip()
    return out


def _resolve_topic_type(user_topics: list[Any], title_to_cat: dict[str, str]) -> str:
    order_cats: list[str] = []
    for t in user_topics:
        if not isinstance(t, str):
            continue
        k = t.strip()
        if k in title_to_cat:
            order_cats.append(title_to_cat[k])
    if not order_cats:
        return "Society"
    cnt = Counter(order_cats)
    max_v = max(cnt.values())
    candidates = [c for c, v in cnt.items() if v == max_v]
    if len(candidates) == 1:
        return candidates[0]
    for c in order_cats:
        if c in candidates:
            return c
    return candidates[0]


def _other_info_for_model(oi: dict[str, Any]) -> dict[str, Any]:
    topics = oi.get("topics")
    if not isinstance(topics, list):
        topics = []
    topics_out = [str(x).strip() for x in topics if x is not None and str(x).strip()]
    return {"topics": topics_out, "gender": oi.get("gender"), "age": oi.get("age"), "mbti": oi.get("mbti"), "country": oi.get("country")}


def _convert_user(row: dict[str, Any], *, agent_id: int, title_to_cat: dict[str, str]) -> dict[str, Any]:
    profile = row.get("profile")
    oi: dict[str, Any] = {}
    if isinstance(profile, dict):
        inner = profile.get("other_info")
        if isinstance(inner, dict):
            oi = inner
    raw_topics = oi.get("topics")
    topics_list: list[Any] = raw_topics if isinstance(raw_topics, list) else []
    topic_type = _resolve_topic_type(topics_list, title_to_cat)
    user_type = str(oi.get("user_type") or row.get("user_type") or "normal").strip().lower()
    if user_type not in ("kol", "normal"):
        user_type = "normal"
    out: dict[str, Any] = {
        "agent_id": agent_id,
        "user_name": str(row.get("user_name") or "").strip(),
        "name": str(row.get("name") or "").strip(),
        "description": str(row.get("description") or "").strip(),
        "profile": {"other_info": _other_info_for_model(oi)},
        "recsys_type": str(row.get("recsys_type") or "twitter").strip() or "twitter",
        "user_type": user_type,
        "topic_type": topic_type,
    }
    if "source" in row:
        out["source"] = row.get("source")
    if "ingest_status" in row:
        out["ingest_status"] = row.get("ingest_status")
    return out


def convert_users_get_to_users_json() -> dict[str, Any]:
    dd = data_dir()
    src = dd / "users_get.json"
    topics_path = dd / "topics.json"
    if not src.is_file():
        raise FileNotFoundError(f"未找到 {src}")
    if not topics_path.is_file():
        raise FileNotFoundError(f"未找到 {topics_path}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("users_get.json 顶层应为数组")
    users_get = [x for x in raw if isinstance(x, dict)]
    title_to_cat = _load_title_to_category(topics_path)
    data_out = [_convert_user(row, agent_id=idx, title_to_cat=title_to_cat) for idx, row in enumerate(users_get)]
    doc = {"recsys_type": "twitter", "type": "users", "stats": {"count": len(data_out)}, "data": data_out}
    (dd / "users.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc
