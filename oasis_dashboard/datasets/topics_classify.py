"""
读取 ``oasis_dashboard/datasets/data/topics_get.json``，使用 ``.env`` 中与 ``persona_llm_batch``
一致的 ``OASIS_MODEL_*`` 变量，通过 **OpenAI 兼容 HTTP API**（``/v1/chat/completions``）
调用所选大模型（如 ``OASIS_MODEL_PLATFORM=deepseek``），将每条话题归入
``Politics`` / ``Economics`` / ``Society``，并写出与 ``topics_model.json`` 相同结构的 JSON。

**不依赖 camel**：仅使用项目已有的 ``requests`` 与 ``python-dotenv``。

默认输出:: ``oasis_dashboard/datasets/data/topics.json``

本脚本**默认按 DeepSeek 云端**解析（``OASIS_MODEL_PLATFORM`` 未设置时视为 ``deepseek``）；
若 ``OASIS_MODEL_PLATFORM=deepseek`` 但 ``OASIS_MODEL_URL`` 仍指向本机 Ollama（含端口 ``11434``），
会自动改用 ``https://api.deepseek.com/v1``。须在 ``.env`` 中配置 ``OASIS_MODEL_API_KEY``。

用法::

    python -m oasis_dashboard.datasets.topics_classify

无论从哪个工作目录启动，都会尝试加载 ``oasis-dashboard/.env``。

可用 ``TOPICS_CLASSIFY_OUTPUT`` 覆盖输出文件名；``OASIS_DATASETS_DATA_DIR`` 可覆盖数据目录。
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Final

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

CATEGORIES: Final[tuple[str, ...]] = ("Politics", "Economics", "Society")
_CATEGORY_ALIASES: Final[dict[str, str]] = {
    "politics": "Politics",
    "economics": "Economics",
    "society": "Society",
}

_DEFAULT_BASE_BY_PLATFORM: Final[dict[str, str]] = {
    "ollama": "http://127.0.0.1:11434/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def _dashboard_root() -> Path:
    """``oasis-dashboard`` 目录（本文件在 ``oasis_dashboard/datasets/`` 下）。"""
    return Path(__file__).resolve().parents[2]


def _load_dashboard_env() -> None:
    """优先加载 ``oasis-dashboard/.env``，避免从 IDE 直接运行脚本时工作目录不对读不到配置。"""
    env_path = _dashboard_root() / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=True)
    else:
        load_dotenv()


def _looks_like_ollama_url(base: str) -> bool:
    return "11434" in base


def _datasets_data_dir() -> Path:
    """
    默认 ``…/oasis_dashboard/datasets/data``（本文件位于 ``datasets/`` 下，与 ``data`` 同级）。
    """
    override = os.environ.get("OASIS_DATASETS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path(__file__).resolve().parent / "data").resolve()


def _normalize_openai_base_url(base: str) -> str:
    b = base.strip().rstrip("/")
    if b.endswith("/v1"):
        return b
    return f"{b}/v1"


def _resolve_chat_runtime() -> tuple[str, dict[str, str], dict[str, Any]]:
    """
    根据环境变量解析 Chat Completions URL、请求头与 body 中的 model / 采样参数。
    与 ``persona_llm_batch.model_spec_from_env`` 使用同一套变量名。

    未设置 ``OASIS_MODEL_PLATFORM`` 时默认 ``deepseek``（云端）；DeepSeek 须配置 ``OASIS_MODEL_API_KEY``。
    """
    platform = os.environ.get("OASIS_MODEL_PLATFORM", "deepseek").strip().lower()
    raw_model = os.environ.get("OASIS_MODEL_TYPE", "").strip()
    if raw_model:
        model_type = raw_model
    else:
        model_type = "deepseek-chat" if platform == "deepseek" else "qwen3:8b"
    if platform == "ollama" and (
        model_type in ("deepseek-chat", "deepseek-coder") or "deepseek" in model_type.lower()
    ):
        logger.warning(
            "OASIS_MODEL_TYPE 为 DeepSeek 云端模型，但 OASIS_MODEL_PLATFORM=ollama；"
            "本脚本将按 DeepSeek 云端请求（与仅使用 DeepSeek 的设定一致）"
        )
        platform = "deepseek"
    raw_key = os.environ.get("OASIS_MODEL_API_KEY", "").strip()
    raw_url = os.environ.get("OASIS_MODEL_URL", "").strip()
    urls = [x.strip() for x in os.environ.get("OASIS_MODEL_URLS", "").split(",") if x.strip()]
    base = raw_url or (urls[0] if urls else "")
    if platform == "deepseek":
        if base and _looks_like_ollama_url(base):
            logger.warning(
                "当前为 DeepSeek 云端，但 OASIS_MODEL_URL 指向本机 Ollama（%s），已改用官方 API",
                base[:80],
            )
            base = _DEFAULT_BASE_BY_PLATFORM["deepseek"]
        elif not base:
            base = _DEFAULT_BASE_BY_PLATFORM["deepseek"]
        if not raw_key:
            raise ValueError(
                "使用 DeepSeek 云端须在 .env 中配置 OASIS_MODEL_API_KEY（"
                f"已加载: {_dashboard_root() / '.env'}）"
            )
    elif not base:
        base = _DEFAULT_BASE_BY_PLATFORM.get(platform, "")
    if not base:
        raise ValueError(
            f"未设置 OASIS_MODEL_URL，且平台 {platform!r} 无内置默认，请在 .env 中配置 OASIS_MODEL_URL"
        )
    base = _normalize_openai_base_url(base)
    chat_url = f"{base}/chat/completions"

    timeout = float(os.environ.get("OASIS_MODEL_TIMEOUT") or 120.0)
    max_tokens = int(os.environ.get("OASIS_MODEL_GENERATION_MAX_TOKENS", "2048") or 2048)

    temp_defaults = {
        "ollama": 0.4,
        "deepseek": 0.8,
        "openai": 0.7,
        "openrouter": 0.7,
        "vllm": 0.7,
    }
    te = os.environ.get("OASIS_MODEL_TEMPERATURE")
    try:
        temperature = float(te) if te else temp_defaults.get(platform, 0.7)
    except ValueError:
        temperature = temp_defaults.get(platform, 0.7)

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if raw_key:
        headers["Authorization"] = f"Bearer {raw_key}"

    if platform == "openrouter":
        ref = os.environ.get("OPENROUTER_HTTP_REFERER", "").strip()
        if ref:
            headers["HTTP-Referer"] = ref
        title = os.environ.get("OPENROUTER_X_TITLE", "OASIS topics_classify").strip()
        if title:
            headers["X-Title"] = title

    meta: dict[str, Any] = {
        "model": model_type,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
    }
    return chat_url, headers, meta


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    t = part.get("text")
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
        if parts:
            return "\n".join(parts)
    return ""


def _run_llm_chat(user_content: str) -> str:
    chat_url, headers, meta = _resolve_chat_runtime()
    body: dict[str, Any] = {
        "model": meta["model"],
        "messages": [{"role": "user", "content": user_content}],
        "temperature": meta["temperature"],
        "max_tokens": meta["max_tokens"],
    }
    resp = requests.post(chat_url, headers=headers, json=body, timeout=meta["timeout"])
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        detail = resp.text[:800] if resp.text else ""
        raise RuntimeError(f"Chat API HTTP 错误: {e} 响应: {detail}") from e
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("API 返回非 JSON 对象")
    text = _extract_message_content(data)
    if not text:
        raise ValueError("API 返回空 content")
    return text


def _canon_category(key: str) -> str | None:
    k = str(key).strip()
    if k in CATEGORIES:
        return k
    return _CATEGORY_ALIASES.get(k.lower())


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
    return t


def _parse_bucket_object(text: str) -> dict[str, list[str]]:
    """解析形如 { \"Politics\": [\"...\"], \"Economics\": [], \"Society\": [] } 的对象。"""
    raw = _strip_json_fence(text)
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("模型输出顶层应为 JSON 对象")
    out: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for key, val in obj.items():
        cat = _canon_category(str(key))
        if cat is None:
            continue
        if not isinstance(val, list):
            continue
        for x in val:
            s = str(x).strip()
            if s:
                out[cat].append(s)
    return out


def _match_title(raw: str, titles_ordered: list[str], title_set: set[str]) -> str | None:
    s = raw.strip()
    if not s:
        return None
    if s in title_set:
        return s
    matches = get_close_matches(s, titles_ordered, n=1, cutoff=0.72)
    if matches:
        return matches[0]
    return None


def _reconcile_buckets(
    buckets: dict[str, list[str]],
    titles_ordered: list[str],
) -> dict[str, list[str]]:
    """将模型返回的字符串对齐到输入 title，并保证每条话题恰好出现一次。"""
    title_set = set(titles_ordered)
    placed: dict[str, str] = {}
    result: dict[str, list[str]] = {c: [] for c in CATEGORIES}

    for cat in CATEGORIES:
        for raw in buckets.get(cat, []):
            m = _match_title(raw, titles_ordered, title_set)
            if m is None:
                logger.warning("无法匹配话题标题，跳过: %r", raw[:120])
                continue
            if m in placed:
                logger.warning("话题 %r 已被标为 %s，忽略重复归类为 %s", m, placed[m], cat)
                continue
            placed[m] = cat
            result[cat].append(m)

    for t in titles_ordered:
        if t not in placed:
            logger.warning("模型未返回分类，归入 Society: %r", t[:120])
            result["Society"].append(t)

    return result


def _build_prompt_payload(items: list[dict[str, Any]]) -> str:
    slim = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        if not title:
            continue
        summary = str(it.get("summary") or "").strip()[:400]
        slim.append({"index": i, "title": title, "summary": summary})
    return json.dumps(slim, ensure_ascii=False, indent=2)


def _build_classify_prompt(slim_json: str) -> str:
    cats = ", ".join(f'"{c}"' for c in CATEGORIES)
    return f"""你是新闻与社交媒体话题分类专家。下面 JSON 数组中每一项有一条仿真话题（title / summary）。

请仅根据 title 与 summary 的语义，将**每一条**话题归入且仅归入以下三类之一：{cats}
- Politics：政府、选举、外交、军事、政策与法律争议、地缘政治等。
- Economics：宏观经济、市场、金融、贸易、产业、就业与消费、企业商业等。
- Society：文化、教育、科技与社会生活、健康、环境民生（非纯政策博弈）、舆论与身份等；若难以区分政经，偏公共讨论可归 Society。

**必须**只输出一个 JSON 对象（不要 Markdown、不要解释），且**恰好**包含这三个键：
"Politics"、"Economics"、"Society"。每个键对应一个**字符串数组**，数组元素必须是输入中的 **title 原文**（逐字与 title 字段一致），不要翻译或改写标题。

输入话题：
{slim_json}
"""


def _classify_batch(
    items: list[dict[str, Any]],
    max_retries: int,
) -> dict[str, list[str]]:
    slim_json = _build_prompt_payload(items)
    if slim_json == "[]":
        return {c: [] for c in CATEGORIES}
    prompt = _build_classify_prompt(slim_json)
    titles_ordered = [
        str(it.get("title") or "").strip()
        for it in items
        if isinstance(it, dict) and str(it.get("title") or "").strip()
    ]
    last_err: Exception | None = None
    strict_suffix = (
        "\n\n【再次强调】只输出合法 JSON 对象，键名必须为 Politics、Economics、Society；"
        "数组元素必须是输入中的 title 原文，双引号转义，不要尾随逗号，不要 Markdown。"
    )
    for attempt in range(max_retries):
        content = prompt if attempt == 0 else prompt + strict_suffix
        try:
            text = _run_llm_chat(content)
            buckets = _parse_bucket_object(text)
            return _reconcile_buckets(buckets, titles_ordered)
        except Exception as e:
            last_err = e
            logger.warning("分类调用失败 (%s/%s): %s", attempt + 1, max_retries, e)
    raise RuntimeError(f"话题分类在 {max_retries} 次重试后仍失败: {last_err}") from last_err


def load_topics_get(data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / "topics_get.json"
    if not path.is_file():
        raise FileNotFoundError(f"未找到 {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("topics_get.json 顶层应为数组")
    return [x for x in raw if isinstance(x, dict)]


def build_topics_model_document(
    *,
    recsys_type: str,
    buckets: dict[str, list[str]],
) -> dict[str, Any]:
    data = [
        {"recsys_type": recsys_type, "category": cat, "topics": buckets[cat]}
        for cat in CATEGORIES
    ]
    return {
        "recsys_type": recsys_type,
        "type": "topics",
        "stats": {"count": len(CATEGORIES)},
        "data": data,
    }


def classify_topics_from_get_json(
    *,
    recsys_type: str | None = None,
    batch_size: int = 24,
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    读取 topics_get.json，调用 LLM 分类，返回与 topics_model.json 相同结构的 dict。
    """
    _load_dashboard_env()
    rt = (recsys_type or os.environ.get("OASIS_TOPIC_RECSYS_TYPE", "twitter")).strip() or "twitter"
    data_dir = _datasets_data_dir()
    items = load_topics_get(data_dir)
    if not items:
        raise ValueError("topics_get.json 中没有有效话题对象")

    merged: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    bs = max(4, min(64, int(batch_size)))
    for start in range(0, len(items), bs):
        chunk = items[start : start + bs]
        part = _classify_batch(chunk, max_retries=max(1, min(10, max_retries)))
        for c in CATEGORIES:
            merged[c].extend(part[c])

    return build_topics_model_document(recsys_type=rt, buckets=merged)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _load_dashboard_env()
    out_name = os.environ.get("TOPICS_CLASSIFY_OUTPUT", "topics.json").strip() or "topics.json"
    try:
        doc = classify_topics_from_get_json()
        out_dir = _datasets_data_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = Path(out_name) if os.path.isabs(out_name) else out_dir / out_name
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("已写入 %s", out_path.resolve())
    except Exception as e:
        logger.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
