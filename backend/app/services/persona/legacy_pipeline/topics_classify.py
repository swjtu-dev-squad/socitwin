from __future__ import annotations

import json
import os
import re
from typing import Any, Final

import requests

from app.services.persona.legacy_pipeline.common import data_dir, load_backend_env

CATEGORIES: Final[tuple[str, ...]] = ("Politics", "Economics", "Society")
_DEFAULT_BASE_BY_PLATFORM: Final[dict[str, str]] = {
    "ollama": "http://127.0.0.1:11434/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def _normalize_openai_base_url(base: str) -> str:
    b = base.strip().rstrip("/")
    if b.endswith("/v1"):
        return b
    return f"{b}/v1"


def _resolve_chat_runtime() -> tuple[str, dict[str, str], dict[str, Any]]:
    platform = os.environ.get("OASIS_MODEL_PLATFORM", "deepseek").strip().lower()
    model_type = os.environ.get("OASIS_MODEL_TYPE", "").strip() or (
        "deepseek-chat" if platform == "deepseek" else "qwen3:8b"
    )
    raw_key = os.environ.get("OASIS_MODEL_API_KEY", "").strip()
    if not raw_key and platform == "deepseek":
        raw_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not raw_key and platform == "openai":
        raw_key = os.environ.get("OPENAI_API_KEY", "").strip()
    raw_url = os.environ.get("OASIS_MODEL_URL", "").strip()
    urls = [x.strip() for x in os.environ.get("OASIS_MODEL_URLS", "").split(",") if x.strip()]
    base = raw_url or (urls[0] if urls else "") or _DEFAULT_BASE_BY_PLATFORM.get(platform, "")
    if not base:
        raise ValueError(f"未设置 OASIS_MODEL_URL，且平台 {platform!r} 无默认地址")
    if platform in {"deepseek", "openai", "openrouter"} and not raw_key:
        raise ValueError(
            f"{platform} 平台缺少 API Key：请设置 OASIS_MODEL_API_KEY"
            + (" 或 DEEPSEEK_API_KEY" if platform == "deepseek" else "")
            + (" 或 OPENAI_API_KEY" if platform == "openai" else "")
        )
    base = _normalize_openai_base_url(base)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if raw_key:
        headers["Authorization"] = f"Bearer {raw_key}"
    meta = {
        "model": model_type,
        "temperature": float(os.environ.get("OASIS_MODEL_TEMPERATURE") or 0.7),
        "max_tokens": int(os.environ.get("OASIS_MODEL_GENERATION_MAX_TOKENS") or 2048),
        "timeout": float(os.environ.get("OASIS_MODEL_TIMEOUT") or 120.0),
    }
    return f"{base}/chat/completions", headers, meta


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


def _run_llm_chat(prompt: str) -> str:
    chat_url, headers, meta = _resolve_chat_runtime()
    body = {
        "model": meta["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": meta["temperature"],
        "max_tokens": meta["max_tokens"],
    }
    resp = requests.post(chat_url, headers=headers, json=body, timeout=meta["timeout"])
    resp.raise_for_status()
    text = _extract_message_content(resp.json())
    if not text:
        raise ValueError("分类模型返回空内容")
    return text


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
    return t


def _classify_once(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    slim = [
        {"title": str(it.get("title") or "").strip(), "summary": str(it.get("summary") or "").strip()[:400]}
        for it in items
        if isinstance(it, dict) and str(it.get("title") or "").strip()
    ]
    prompt = (
        "将下面话题标题分类到 Politics/Economics/Society 三类。"
        "只输出 JSON 对象，键名固定为 Politics、Economics、Society，值为标题字符串数组。\n\n"
        f"{json.dumps(slim, ensure_ascii=False, indent=2)}"
    )
    raw = _strip_json_fence(_run_llm_chat(prompt))
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("分类返回不是 JSON 对象")
    out: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    all_titles = [x["title"] for x in slim]
    title_set = set(all_titles)
    for c in CATEGORIES:
        arr = obj.get(c)
        if isinstance(arr, list):
            out[c] = [str(x).strip() for x in arr if str(x).strip() in title_set]
    placed = set(x for arr in out.values() for x in arr)
    for t in all_titles:
        if t not in placed:
            out["Society"].append(t)
    return out


def classify_topics_to_topics_json(batch_size: int = 24, max_retries: int = 3) -> dict[str, Any]:
    load_backend_env()
    dd = data_dir()
    dd.mkdir(parents=True, exist_ok=True)
    src = dd / "topics_get.json"
    if not src.is_file():
        raise FileNotFoundError(f"未找到 {src}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("topics_get.json 顶层应为数组")
    items = [x for x in raw if isinstance(x, dict)]
    merged: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    bs = max(4, min(64, int(batch_size)))
    for i in range(0, len(items), bs):
        chunk = items[i : i + bs]
        last_err: Exception | None = None
        part: dict[str, list[str]] | None = None
        for _ in range(max(1, min(10, max_retries))):
            try:
                part = _classify_once(chunk)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
        if part is None:
            raise RuntimeError(f"话题分类失败: {last_err}")
        for c in CATEGORIES:
            merged[c].extend(part[c])
    doc = {
        "recsys_type": "twitter",
        "type": "topics",
        "stats": {"count": len(CATEGORIES)},
        "data": [{"recsys_type": "twitter", "category": c, "topics": merged[c]} for c in CATEGORIES],
    }
    (dd / "topics.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc
