"""
批量调用大模型生成「模拟用户」文档，供 persona 图谱构建使用。

与 OASIS 共用 OASIS_MODEL_* 环境变量；由后端进程内调用。
已在 Settings 声明的项（如 OASIS_MODEL_PLATFORM）可通过 get_settings() 从 .env 读取；其余依赖 os.environ 或 shell export。
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Tuple, Union

from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from app.services.persona.llm.camel_llm_build import build_shared_model
from app.services.persona.llm.camel_runtime_spec import ModelRuntimeSpec

logger = logging.getLogger(__name__)

_config_dotenv_loaded = False


def _ensure_persona_llm_env() -> None:
    global _config_dotenv_loaded
    if _config_dotenv_loaded:
        return
    import importlib

    importlib.import_module("app.core.config")
    _config_dotenv_loaded = True


def _datasets_data_dir() -> Path:
    override = os.environ.get("OASIS_DATASETS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    backend_root = Path(__file__).resolve().parents[4]
    return (backend_root / "data" / "datasets" / "persona_llm_debug").resolve()


def _write_json_to_datasets_data(filename: str, payload: Any) -> None:
    try:
        out_dir = _datasets_data_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("LLM 结果已写入 %s", path)
    except OSError as exc:
        logger.warning("无法写入 %s: %s", filename, exc)


def _clean_llm_api_key(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower().replace("-", "_")
    placeholders = {
        "not_provided",
        "none",
        "null",
        "undefined",
        "changeme",
        "placeholder",
        "test",
        "your_openai_api_key_here",
        "your_deepseek_api_key_here",
    }
    if low in placeholders:
        return None
    if "your_openai_api_key" in low or "your_deepseek_api_key" in low:
        return None
    return s


def _settings_str(field: str) -> str | None:
    try:
        from app.core.config import get_settings

        return _clean_llm_api_key(getattr(get_settings(), field, None))
    except Exception:
        return None


def _resolve_llm_api_key(platform: str) -> str | None:
    pl = platform.lower()
    direct = _clean_llm_api_key(os.environ.get("OASIS_MODEL_API_KEY"))
    if direct:
        return direct
    if pl == "openai":
        return _clean_llm_api_key(os.environ.get("OPENAI_API_KEY")) or _settings_str("OPENAI_API_KEY")
    if pl == "deepseek":
        return _clean_llm_api_key(os.environ.get("DEEPSEEK_API_KEY")) or _settings_str("DEEPSEEK_API_KEY")
    if pl == "openrouter":
        return _clean_llm_api_key(os.environ.get("OPENROUTER_API_KEY"))
    return None


def _platform_requires_cloud_api_key(platform: str) -> bool:
    return platform.lower() in ("openai", "deepseek", "openrouter")


def _default_model_type_for_platform(platform: str) -> str:
    pl = platform.lower()
    if pl == "deepseek":
        return "deepseek-chat"
    if pl == "openai":
        return "gpt-4o-mini"
    if pl == "openrouter":
        return "deepseek/deepseek-chat"
    if pl == "vllm":
        return "Qwen/Qwen2.5-7B-Instruct"
    return "qwen3:8b"


def _env_or_settings_str(env_name: str, settings_field: str) -> str:
    ev = os.environ.get(env_name)
    if isinstance(ev, str) and ev.strip():
        return ev.strip()
    try:
        from app.core.config import get_settings

        sv = getattr(get_settings(), settings_field, None)
        if isinstance(sv, str) and sv.strip():
            return sv.strip()
    except Exception:
        pass
    return ""


def model_spec_from_env() -> Union[ModelRuntimeSpec, List[ModelRuntimeSpec]]:
    _ensure_persona_llm_env()
    platform = _env_or_settings_str("OASIS_MODEL_PLATFORM", "OASIS_MODEL_PLATFORM") or "ollama"
    raw_model_type = _env_or_settings_str("OASIS_MODEL_TYPE", "OASIS_MODEL_TYPE")
    model_type = raw_model_type or _default_model_type_for_platform(platform)
    api_key = _resolve_llm_api_key(platform)
    if _platform_requires_cloud_api_key(platform) and not api_key:
        raise ValueError(
            "未配置有效的 LLM API Key。当前 OASIS_MODEL_PLATFORM=%r：请在 backend/.env 中设置可用的 "
            "OASIS_MODEL_API_KEY，或对 OpenAI 设置 OPENAI_API_KEY、对 DeepSeek 设置 DEEPSEEK_API_KEY；"
            "不要使用占位符（如 Not_Provided、your-xxx-key-here）。若实际使用 DeepSeek，请将 "
            "OASIS_MODEL_PLATFORM 设为 deepseek 并配置 DEEPSEEK_API_KEY。"
            % (platform,)
        )
    raw_url = _env_or_settings_str("OASIS_MODEL_URL", "OASIS_MODEL_URL")
    url = raw_url or None
    urls_raw = _env_or_settings_str("OASIS_MODEL_URLS", "OASIS_MODEL_URLS")
    urls = [item.strip() for item in urls_raw.split(",") if item.strip()]
    timeout: float | None = None
    if os.environ.get("OASIS_MODEL_TIMEOUT"):
        try:
            timeout = float(os.environ.get("OASIS_MODEL_TIMEOUT", "") or "")
        except ValueError:
            timeout = None
    max_retries = int(os.environ.get("OASIS_MODEL_MAX_RETRIES", "3"))
    generation_max_tokens = int(os.environ.get("OASIS_MODEL_GENERATION_MAX_TOKENS", "1024"))
    dcw: int | None = None
    if os.environ.get("OASIS_MODEL_CONTEXT_WINDOW"):
        try:
            dcw = int(os.environ.get("OASIS_MODEL_CONTEXT_WINDOW", "") or "0")
        except ValueError:
            dcw = None
    ctl: int | None = None
    if os.environ.get("OASIS_CONTEXT_TOKEN_LIMIT"):
        try:
            ctl = int(os.environ.get("OASIS_CONTEXT_TOKEN_LIMIT", "") or "0")
        except ValueError:
            ctl = None

    temp_defaults = {"ollama": 0.4, "deepseek": 0.8, "openai": 0.7, "openrouter": 0.7, "vllm": 0.7}
    te = os.environ.get("OASIS_MODEL_TEMPERATURE")
    try:
        temperature = float(te) if te else temp_defaults.get(platform.lower(), 0.7)
    except ValueError:
        temperature = temp_defaults.get(platform.lower(), 0.7)

    model_config_dict: dict[str, Any] = {"temperature": temperature}
    if platform.lower() == "deepseek":
        model_config_dict["tool_choice"] = "auto"

    base_kwargs: dict[str, Any] = dict(
        model_platform=platform,
        model_type=model_type,
        model_config_dict=model_config_dict,
        api_key=api_key,
        timeout=float(timeout) if timeout else 120.0,
        max_retries=max_retries,
        generation_max_tokens=generation_max_tokens,
        declared_context_window=int(dcw) if dcw else None,
        context_token_limit=int(ctl) if ctl else None,
    )
    if urls:
        return [ModelRuntimeSpec(url=item, **base_kwargs) for item in urls]
    return ModelRuntimeSpec(url=url, **base_kwargs)


def _extract_response_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n".join(parts)
    tool_calls = getattr(message, "tool_calls", None) or []
    for tool_call in tool_calls:
        func = getattr(tool_call, "function", None)
        if func is None:
            continue
        arguments = getattr(func, "arguments", None)
        if isinstance(arguments, str) and arguments.strip():
            return arguments.strip()
    return ""


def _normalize_jsonish_text(text: str) -> str:
    return text.replace("\ufeff", "").replace("［", "[").replace("］", "]").strip()


def _strip_leading_reasoning_and_noise(text: str) -> str:
    t = text
    _end_think = "</" + "think" + ">"
    _end_redacted = "</" + "redacted_thinking" + ">"
    seps = (_end_think, _end_redacted)
    changed = True
    while changed:
        changed = False
        for sep in seps:
            if sep in t:
                t = t.split(sep, 1)[-1].strip()
                changed = True
    t = re.sub(r"^#+\s.*\n+", "", t).strip()
    return t


def _outer_object_bounds(s: str) -> tuple[int, int] | None:
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(s):
        c = s[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i
        i += 1
    return None


def _looks_like_user_row(d: dict[str, Any]) -> bool:
    keys = set(d.keys())
    return bool(keys & {"username", "user_name", "name", "bio", "persona", "interests", "description"})


def _list_from_wrapping_object(obj: dict[str, Any]) -> list[dict[str, Any]] | None:
    preferred = ("users", "profiles", "personas", "agents", "items", "generated_users", "user_list", "results", "data")
    for k in preferred:
        if k not in obj:
            continue
        v = obj[k]
        if k == "data" and isinstance(v, dict):
            inner = _list_from_wrapping_object(v)
            if inner:
                return inner
            continue
        if isinstance(v, list):
            dicts = [x for x in v if isinstance(x, dict)]
            if dicts:
                return dicts
    for v in obj.values():
        if isinstance(v, list):
            dicts = [x for x in v if isinstance(x, dict)]
            if dicts and len(dicts) == len(v):
                return dicts
    return None


def _try_parse_flexible_top_level(text: str) -> list[Any] | None:
    for variant in (text, _remove_trailing_commas(text)):
        try:
            v = json.loads(variant)
        except json.JSONDecodeError:
            continue
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            nested = _list_from_wrapping_object(v)
            if nested is not None:
                return nested
            if _looks_like_user_row(v):
                return [v]
    return None


def _parse_ndjson_object_sequence(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    items: list[dict[str, Any]] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        try:
            obj, consumed = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict) and _looks_like_user_row(obj):
            items.append(obj)
        elif isinstance(obj, dict):
            nested = _list_from_wrapping_object(obj)
            if nested:
                items.extend(nested)
            else:
                break
        else:
            break
        i += consumed
    return items


def _try_single_object_slice(text: str) -> list[Any] | None:
    b = _outer_object_bounds(text)
    if b is None:
        return None
    chunk = text[b[0] : b[1] + 1]
    for variant in (chunk, _remove_trailing_commas(chunk)):
        try:
            d = json.loads(variant)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            nested = _list_from_wrapping_object(d)
            if nested is not None:
                return nested
            if _looks_like_user_row(d):
                return [d]
    return None


def _outer_array_bounds(s: str) -> tuple[int, int] | None:
    start = s.find("[")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(s):
        c = s[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return start, i
        i += 1
    return None


def _remove_trailing_commas(s: str) -> str:
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r",(\s*[}\]])", r"\1", s)
    return s


def _parse_json_array_incremental(array_text: str) -> list[Any]:
    bounds = _outer_array_bounds(array_text)
    if bounds is None:
        raise ValueError("未找到 JSON 数组")
    start, end = bounds
    inner = array_text[start + 1 : end]
    decoder = json.JSONDecoder()
    items: list[Any] = []
    i = 0
    n = len(inner)
    while i < n:
        while i < n and inner[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        try:
            obj, consumed = decoder.raw_decode(inner, i)
        except json.JSONDecodeError as e:
            if items:
                tail = inner[i:].strip()
                logger.warning("增量解析在偏移 %s 中断，已保留前 %d 条: %s 尾部: %r", i, len(items), e, tail[:160])
                return items
            raise ValueError(f"增量解析在偏移 {i} 失败: {e}") from e
        items.append(obj)
        i += consumed
        while i < n and inner[i] in " \t\n\r":
            i += 1
        if i < n and inner[i] == ",":
            i += 1
    if not items:
        raise ValueError("增量解析未得到任何元素")
    tail = inner[i:].strip()
    if tail:
        logger.warning("JSON 数组解析后仍有未消费尾部（已保留 %d 条）: %r", len(items), tail[:200])
    return items


def _parse_json_array_prefix(text: str) -> list[Any] | None:
    """尽量从“可能被截断”的数组前缀中解析出若干元素。

    适用场景：模型输出很长，末尾丢失了闭合的 ] 或 ``` fence。
    策略：定位第一个 '['，然后用 JSONDecoder.raw_decode 逐个解码元素，遇到错误即停止。
    """
    s = text.strip()
    if not s:
        return None
    lb = s.find("[")
    if lb < 0:
        return None
    inner = s[lb + 1 :]
    dec = json.JSONDecoder()
    i = 0
    n = len(inner)
    items: list[Any] = []
    while i < n:
        # 跳过空白、逗号
        while i < n and inner[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        # 若提前遇到 ']' 说明完整结束
        if inner[i] == "]":
            break
        try:
            obj, consumed = dec.raw_decode(inner[i:])
        except json.JSONDecodeError:
            break
        items.append(obj)
        i += consumed
    return items or None


def _json_array_candidates(text: str) -> list[str]:
    stripped = text.strip()
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"```(?:json)?\s*", stripped, re.IGNORECASE):
        seg = stripped[m.end() :]
        fence = seg.find("```")
        if fence >= 0:
            seg = seg[:fence]
        b = _outer_array_bounds(seg)
        if b:
            a, e = b
            chunk = seg[a : e + 1]
            if chunk not in seen:
                seen.add(chunk)
                found.append(chunk)
    b = _outer_array_bounds(stripped)
    if b:
        a, e = b
        chunk = stripped[a : e + 1]
        if chunk not in seen:
            seen.add(chunk)
            found.append(chunk)
    # 没有找到闭合的 []：尝试保留 fence 段落的前缀（用于“截断数组”解析）
    for m in re.finditer(r"```(?:json)?\s*", stripped, re.IGNORECASE):
        seg = stripped[m.end() :]
        fence = seg.find("```")
        if fence >= 0:
            seg = seg[:fence]
        if "[" in seg:
            prefix = seg[seg.find("[") :].strip()
            if prefix and prefix not in seen:
                seen.add(prefix)
                found.append(prefix)
            break
    if "[" in stripped:
        prefix = stripped[stripped.find("[") :].strip()
        if prefix and prefix not in seen:
            seen.add(prefix)
            found.append(prefix)
    return found


def _parse_json_array(text: str) -> list[Any]:
    text = _normalize_jsonish_text(text)
    text = _strip_leading_reasoning_and_noise(text)
    if not text:
        raise ValueError("模型输出为空，无法解析")
    flex = _try_parse_flexible_top_level(text)
    if flex is not None:
        return flex
    candidates = _json_array_candidates(text)
    last_err: Exception | None = None
    if not candidates:
        nd = _parse_ndjson_object_sequence(text)
        if nd:
            return nd
        single = _try_single_object_slice(text)
        if single is not None:
            return single
        prefix = _parse_json_array_prefix(text)
        if prefix is not None:
            # 方案一：要求“数据完整”，因此一旦判定截断就直接失败，让上层重试补齐。
            raise ValueError(f"模型输出疑似截断：仅从数组前缀解析到 {len(prefix)} 条元素。")
        preview = text[:480] + ("..." if len(text) > 480 else "")
        raise ValueError("无法在模型输出中定位 JSON 数组（未找到合法的 [] 或用户对象）。" f" 输出开头: {preview!r}")
    for raw in candidates:
        for variant in (raw, _remove_trailing_commas(raw)):
            try:
                arr = json.loads(variant)
                if isinstance(arr, list):
                    return arr
                last_err = ValueError("解析结果不是 JSON 数组")
            except json.JSONDecodeError as e:
                last_err = e
                try:
                    return _parse_json_array_incremental(variant)
                except ValueError as e2:
                    last_err = e2
        prefix = _parse_json_array_prefix(raw)
        if prefix is not None:
            raise ValueError(f"模型输出疑似截断：仅从数组前缀解析到 {len(prefix)} 条元素。")
    nd = _parse_ndjson_object_sequence(text)
    if nd:
        return nd
    single = _try_single_object_slice(text)
    if single is not None:
        return single
    snippet = candidates[0][:500] + ("..." if len(candidates[0]) > 500 else "")
    msg = "无法在模型输出中解析 JSON 数组"
    if last_err is not None:
        msg = f"{msg}: {last_err}"
    raise ValueError(f"{msg} 片段: {snippet!r}") from last_err


def _compact_user(u: dict[str, Any]) -> dict[str, Any]:
    keys = ("username", "user_name", "name", "realname", "bio", "description", "persona", "interests", "country", "gender", "age", "mbti", "twitter_user_id", "user_type")
    out: dict[str, Any] = {}
    for k in keys:
        if k in u and u[k] is not None:
            out[k] = u[k]
    return out


def _normalize_synthetic_topic_titles(titles: list[str] | None) -> list[str] | None:
    if not titles:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for t in titles:
        s = str(t).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out or None


def _enforce_interests_only_synthetic_titles(row: dict[str, Any], allowed: list[str]) -> None:
    if not allowed:
        return
    allowed_set = set(allowed)
    raw = row.get("interests")
    picked: list[str] = []
    if isinstance(raw, list):
        for x in raw:
            s = str(x).strip()
            if s in allowed_set:
                picked.append(s)
    seen: set[str] = set()
    deduped: list[str] = []
    for s in picked:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    deduped = deduped[:3]
    if len(deduped) < 1:
        pick_n = random.randint(1, min(3, len(allowed)))
        deduped = random.sample(allowed, pick_n)
    row["interests"] = deduped


def _build_prompt(
    *,
    seed_profiles: list[dict[str, Any]],
    batch_size: int,
    batch_index: int,
    recsys_type: str,
    kol_target: int | None = None,
    normal_target: int | None = None,
    global_context: str | None = None,
    allowed_synthetic_topic_titles: list[str] | None = None,
) -> str:
    seeds_json = json.dumps(seed_profiles, ensure_ascii=False, indent=2)
    ratio_hint = ""
    if isinstance(kol_target, int) and isinstance(normal_target, int):
        ratio_hint = f'\n- user_type: 字符串，只能为 "kol" 或 "normal"；本次希望生成 kol={kol_target}、normal={normal_target}（允许±1 的浮动，但总体比例需接近）。'
    ctx_block = ""
    if global_context and str(global_context).strip():
        ctx_block = "\n\n【仿真话题与观测背景（须结合以下语义生成用户兴趣与表达风格，勿照抄原文）】\n" + str(global_context).strip()[:12000]
    titles_block = ""
    interests_spec = "- interests: 字符串数组，3~8 个兴趣标签（可与种子风格相近，但勿照抄种子原文）"
    if allowed_synthetic_topic_titles:
        titles_json = json.dumps(allowed_synthetic_topic_titles, ensure_ascii=False, indent=2)
        titles_block = "\n\n【合法话题标题】（仅允许将下列字符串作为 interests 数组的元素；必须与其中某一项逐字完全相同）\n" f"{titles_json}\n"
        interests_spec = "- interests: 字符串数组，长度必须为 1～3，且每项必须来自上方【合法话题标题】。"
    return f"""你是社交媒体用户画像建模专家。下面是一批真实采样用户（JSON），平台类型约为: {recsys_type}。
{ctx_block}
{titles_block}

请根据这些用户在兴趣分布、表达风格、人口属性上的统计特征，**新造** {batch_size} 个**虚构**用户画像，用于社会仿真。要求：
- 与种子用户在整体分布上相似，但 username / bio / 具体兴趣组合要有明显差异，避免抄袭原文；
- 每个用户一条 JSON 对象，字段尽量齐全，便于后续入库；
- 仅输出一个 JSON 数组，不要 Markdown、不要解释文字；
- bio / persona 等字符串里若出现英文双引号，必须写成 \\"；键名必须用双引号；不要尾随逗号。
{ratio_hint}

每条对象建议使用如下字段（缺失可 null，数组可为空）：
- username
- name
- bio
- persona
{interests_spec}
- country, gender, age, mbti
- user_type: "kol" 或 "normal"

本批次编号: {batch_index}（不要在输出中包含此编号）。

【种子用户示例】
{seeds_json}
"""


_JSON_STRICT_RETRY_SUFFIX = "\n\n【再次强调】只输出一个合法 JSON 数组，不要有其它文字。"


def run_llm_batch(
    model: Any, prompt: str, max_retries: int, *, expected_min_items: int | None = None
) -> list[dict[str, Any]]:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        content = prompt if attempt == 0 else prompt + _JSON_STRICT_RETRY_SUFFIX
        msg = BaseMessage.make_user_message(role_name="User", content=content)
        openai_msg = msg.to_openai_message(OpenAIBackendRole.USER)
        try:
            response = model.run([openai_msg])
            text = _extract_response_text(response)
            if not text:
                raise ValueError("模型返回空内容")
            arr = _parse_json_array(text)
            out = [item for item in arr if isinstance(item, dict)]
            if not out:
                raise ValueError("数组内无有效对象")
            if expected_min_items is not None and len(out) < int(expected_min_items):
                raise ValueError(
                    f"数组元素不足：期望至少 {int(expected_min_items)} 条对象，实际仅 {len(out)} 条。"
                )
            return out
        except Exception as e:
            last_err = e
            logger.warning("批次调用失败 (%s/%s): %s", attempt + 1, max_retries, e)
    raise RuntimeError(f"批次在 {max_retries} 次重试后仍失败: {last_err}")


def map_llm_row_to_raw_user(row: dict[str, Any], *, dataset_id: str, recsys_type: str, index: int) -> dict[str, Any]:
    uname = str(row.get("username") or f"llm_user_{index}").strip() or f"llm_user_{index}"
    name = str(row.get("name") or uname).strip()
    bio = str(row.get("bio") or "").strip()
    persona = str(row.get("persona") or "").strip()
    user_type = str(row.get("user_type") or row.get("type") or row.get("role") or "").strip().lower()
    if user_type not in ("kol", "normal"):
        user_type = "normal"
    interests = row.get("interests")
    if not isinstance(interests, list):
        interests = []
    interests = [str(x) for x in interests if x is not None][:16]
    age_val = row.get("age")
    if isinstance(age_val, str) and age_val.isdigit():
        age_val = int(age_val)
    elif not isinstance(age_val, (int, float)):
        age_val = None
    elif isinstance(age_val, float):
        age_val = int(age_val)
    tid = f"llm_{dataset_id[:32]}_{index}"[:64]
    return {
        "dataset_id": dataset_id,
        "recsys_type": recsys_type,
        "user_name": uname[:120],
        "name": name[:200],
        "description": bio[:220] if bio else "",
        "profile": {"other_info": {"user_profile": persona[:360] if persona else "", "topics": interests, "user_type": user_type, "country": row.get("country"), "gender": row.get("gender"), "age": age_val, "mbti": row.get("mbti")}},
        "twitter_user_id": tid,
        "source": "llm_generated",
        "ingest_status": "generated",
    }


def generate_synthetic_topics(model: Any, *, selected_topics: list[dict[str, Any]], topic_count: int, max_retries: int = 3) -> list[dict[str, Any]]:
    # 单次模型调用最多生成 20 条；若输入要求更少，则按输入数量生成
    n = max(1, min(20, int(topic_count)))
    sel = [t for t in selected_topics if isinstance(t, dict)][:80]
    prompt = (
        "你是社交媒体趋势分析专家。请基于下面话题生成新的仿真讨论话题。"
        f" 输出 {n} 条，仅输出 JSON 数组，每项包含 title, summary。\n\n"
        f"{json.dumps(sel, ensure_ascii=False, indent=2)}"
    )
    batch = run_llm_batch(model, prompt, max_retries, expected_min_items=n)
    out: list[dict[str, Any]] = []
    for item in batch:
        title = str(item.get("title") or item.get("name") or "").strip()
        summary = str(item.get("summary") or item.get("description") or "").strip()
        if title:
            out.append({"title": title[:300], "summary": summary[:800]})
        if len(out) >= n:
            break
    if len(out) < 1:
        raise RuntimeError("未能从模型输出中解析到任何仿真话题")
    return out[:n]


def generate_llm_persona_users(
    seed_users: list[dict[str, Any]],
    *,
    target_count: int,
    dataset_id: str,
    recsys_type: str,
    batch_size: int = 8,
    seed_sample: int = 12,
    max_retries: int = 3,
    kol_normal_ratio: tuple[int, int] = (1, 8),
    global_context: str | None = None,
    synthetic_topic_titles: list[str] | None = None,
) -> Tuple[list[dict[str, Any]], dict[str, Any]]:
    if target_count < 1:
        raise ValueError("target_count 须 >= 1")
    if not seed_users:
        raise ValueError("seed_users 不能为空")
    random.seed(int(os.environ.get("OASIS_PERSONA_GEN_SEED", "42")))
    pool = [_compact_user(u) for u in seed_users if isinstance(u, dict)]
    if not pool:
        raise ValueError("种子用户无法规范化")

    titles_norm = _normalize_synthetic_topic_titles(synthetic_topic_titles)
    model = build_shared_model(model_spec_from_env()).model
    mapped: list[dict[str, Any]] = []
    batch_index = 0
    remaining = target_count
    kol_need = 0
    normal_need = target_count
    try:
        k, n = kol_normal_ratio
        total = k + n
        if total > 0 and k >= 0 and n >= 0:
            kol_need = int(round(target_count * (k / total)))
            normal_need = target_count - kol_need
    except Exception:
        kol_need = 0
        normal_need = target_count

    while remaining > 0:
        batch_index += 1
        this_batch = min(batch_size, remaining)
        sample_k = min(seed_sample, len(pool))
        seed_profiles = random.sample(pool, sample_k) if sample_k < len(pool) else list(pool)
        prompt = _build_prompt(
            seed_profiles=seed_profiles,
            batch_size=this_batch,
            batch_index=batch_index,
            recsys_type=recsys_type,
            kol_target=min(kol_need, this_batch) if kol_need > 0 else 0,
            normal_target=max(0, this_batch - min(kol_need, this_batch)),
            global_context=global_context,
            allowed_synthetic_topic_titles=titles_norm,
        )
        before_len = len(mapped)

        picked: list[dict[str, Any]] = []
        last_pick_err: Exception | None = None
        # 外层重试负责“挑选不足”等逻辑失败；内层最多 2 次（原始 prompt + 严格后缀），避免与外层叠乘成 max_retries^2。
        inner_llm_retries = min(2, max(1, int(max_retries)))
        for _pick_attempt in range(max(1, int(max_retries))):
            try:
                batch = run_llm_batch(model, prompt, inner_llm_retries, expected_min_items=this_batch)
                # 本次挑选不立刻消耗 kol_need/normal_need，只有成功凑够 this_batch 才提交扣减
                tmp_kol_need = kol_need
                tmp_normal_need = normal_need
                tmp_picked: list[dict[str, Any]] = []
                for row in batch:
                    ut = str(row.get("user_type") or row.get("type") or row.get("role") or "").strip().lower()
                    if ut not in ("kol", "normal"):
                        ut = "normal"
                    if ut == "kol":
                        if tmp_kol_need <= 0:
                            continue
                        tmp_kol_need -= 1
                    else:
                        if tmp_normal_need <= 0:
                            continue
                        tmp_normal_need -= 1
                    tmp_picked.append(row)
                    if len(tmp_picked) >= this_batch:
                        break
                if len(tmp_picked) < this_batch:
                    raise ValueError(f"本批挑选到的用户不足：{len(tmp_picked)}/{this_batch}")
                picked = tmp_picked
                kol_need = tmp_kol_need
                normal_need = tmp_normal_need
                last_pick_err = None
                break
            except Exception as e:
                last_pick_err = e
                logger.warning(
                    "本批用户生成/挑选失败，将重试 (%s/%s): %s",
                    _pick_attempt + 1,
                    max(1, int(max_retries)),
                    e,
                )

        if not picked:
            raise RuntimeError(
                f"LLM 本批在 {max(1, int(max_retries))} 次尝试后仍无法生成足量用户（目标 {this_batch}）。最后错误: {last_pick_err}"
            )
        base_idx = len(mapped)
        for i, row in enumerate(picked):
            if titles_norm:
                _enforce_interests_only_synthetic_titles(row, titles_norm)
            mapped.append(map_llm_row_to_raw_user(row, dataset_id=dataset_id, recsys_type=recsys_type, index=base_idx + i))
        remaining = target_count - len(mapped)
        if len(mapped) == before_len:
            raise RuntimeError(f"LLM 本批未生成可解析用户（已 {len(mapped)}/{target_count}）。")

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_count": target_count,
        "actual_count": len(mapped),
        "batch_size": batch_size,
        "seed_pool_size": len(pool),
        "model_platform": os.environ.get("OASIS_MODEL_PLATFORM"),
        "model_type": os.environ.get("OASIS_MODEL_TYPE"),
        "used_global_context": bool(global_context and str(global_context).strip()),
        "interests_locked_to_synthetic_topic_titles": bool(titles_norm),
        "synthetic_topic_title_count": len(titles_norm) if titles_norm else 0,
    }
    return mapped, meta
