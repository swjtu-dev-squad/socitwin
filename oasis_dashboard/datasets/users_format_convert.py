"""
将 ``datasets/data/users_get.json`` 转为与 ``users_model.json`` 相同的顶层结构，
并依据 ``datasets/data/topics.json`` 中话题所属分类写入 ``topic_type``。

- ``agent_id``：从 0 起递增
- ``topic_type``：按用户 ``profile.other_info.topics`` 中各标题在 ``topics.json`` 的
  ``Politics`` / ``Economics`` / ``Society`` 映射；多类时取众数，平票则按用户 topics
  列表中**先出现**的分类为准；若均无法匹配则 ``Society``
- 保留 ``source``、``ingest_status``；去除 ``dataset_id``（及 ``twitter_user_id``，与 model 对齐）
- ``profile.other_info`` 仅保留与 model 一致字段：``topics``、``gender``、``age``、``mbti``、``country``

输出：``datasets/data/users.json``

用法::

    python -m oasis_dashboard.datasets.users_format_convert
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def load_title_to_category(topics_path: Path) -> dict[str, str]:
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


def _resolve_topic_type(
    user_topics: list[Any],
    title_to_cat: dict[str, str],
) -> str:
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
    for oc in order_cats:
        if oc in candidates:
            return oc
    return candidates[0]


def _other_info_for_model(oi: dict[str, Any]) -> dict[str, Any]:
    topics = oi.get("topics")
    if not isinstance(topics, list):
        topics = []
    topics_out = [str(x).strip() for x in topics if x is not None and str(x).strip()]
    return {
        "topics": topics_out,
        "gender": oi.get("gender"),
        "age": oi.get("age"),
        "mbti": oi.get("mbti"),
        "country": oi.get("country"),
    }


def convert_user(
    row: dict[str, Any],
    *,
    agent_id: int,
    title_to_cat: dict[str, str],
) -> dict[str, Any]:
    profile = row.get("profile")
    oi: dict[str, Any] = {}
    if isinstance(profile, dict):
        inner = profile.get("other_info")
        if isinstance(inner, dict):
            oi = inner
    topics_list = oi.get("topics") if isinstance(oi.get("topics"), list) else []
    topic_type = _resolve_topic_type(topics_list, title_to_cat)
    user_type = str(oi.get("user_type") or row.get("user_type") or "normal").strip().lower()
    if user_type not in ("kol", "normal"):
        user_type = "normal"
    recsys = str(row.get("recsys_type") or "twitter").strip() or "twitter"
    out: dict[str, Any] = {
        "agent_id": agent_id,
        "user_name": str(row.get("user_name") or "").strip(),
        "name": str(row.get("name") or "").strip(),
        "description": str(row.get("description") or "").strip(),
        "profile": {"other_info": _other_info_for_model(oi)},
        "recsys_type": recsys,
        "user_type": user_type,
        "topic_type": topic_type,
    }
    if "source" in row:
        out["source"] = row.get("source")
    if "ingest_status" in row:
        out["ingest_status"] = row.get("ingest_status")
    return out


def convert_users_get_to_model_document(
    users_get: list[dict[str, Any]],
    title_to_cat: dict[str, str],
    *,
    recsys_type: str | None = None,
) -> dict[str, Any]:
    rt = (recsys_type or "").strip() or None
    data_out: list[dict[str, Any]] = []
    agent_id = 0
    for row in users_get:
        if not isinstance(row, dict):
            continue
        doc = convert_user(row, agent_id=agent_id, title_to_cat=title_to_cat)
        agent_id += 1
        if rt is None and doc.get("recsys_type"):
            rt = str(doc["recsys_type"])
        data_out.append(doc)
    if not rt:
        rt = "twitter"
    return {
        "recsys_type": rt,
        "type": "users",
        "stats": {"count": len(data_out)},
        "data": data_out,
    }


def main() -> int:
    base = _data_dir()
    get_path = base / "users_get.json"
    topics_path = base / "topics.json"
    out_path = base / "users.json"
    if not get_path.is_file():
        print(f"未找到 {get_path}", file=sys.stderr)
        return 1
    if not topics_path.is_file():
        print(f"未找到 {topics_path}（需要话题分类结果以写入 topic_type）", file=sys.stderr)
        return 1
    raw = json.loads(get_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("users_get.json 顶层应为数组", file=sys.stderr)
        return 1
    users_get = [x for x in raw if isinstance(x, dict)]
    title_to_cat = load_title_to_category(topics_path)
    doc = convert_users_get_to_model_document(users_get, title_to_cat)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {out_path.resolve()} ，共 {doc['stats']['count']} 条用户")
    return 0


if __name__ == "__main__":
    sys.exit(main())
