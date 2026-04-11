"""
批量调用大模型生成「模拟用户」文档，供 persona 图谱构建使用。

与 OASIS 共用 OASIS_MODEL_* 环境变量；由 Node 通过 persona_llm_worker 子进程调用，
也可被 scripts/generate_llm_personas.py 复用。
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from typing import Any, List, Tuple, Union

from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from oasis_dashboard.context import ModelRuntimeSpec, build_shared_model

logger = logging.getLogger(__name__)


def model_spec_from_env() -> Union[ModelRuntimeSpec, List[ModelRuntimeSpec]]:
    """
    与 real_oasis_engine_v3._build_model_runtime_spec 对齐：
    - OASIS_MODEL_API_KEY：云端 API 使用
    - OASIS_MODEL_URL：单端点
    - OASIS_MODEL_URLS：逗号分隔多端点 → 多个 ModelRuntimeSpec，由 ModelManager 轮询
    """
    platform = os.environ.get("OASIS_MODEL_PLATFORM", "ollama")
    model_type = os.environ.get("OASIS_MODEL_TYPE", "qwen3:8b")
    raw_key = os.environ.get("OASIS_MODEL_API_KEY", "").strip()
    api_key = raw_key or None
    raw_url = os.environ.get("OASIS_MODEL_URL", "").strip()
    url = raw_url or None
    urls = [
        item.strip()
        for item in os.environ.get("OASIS_MODEL_URLS", "").split(",")
        if item.strip()
    ]
    timeout = os.environ.get("OASIS_MODEL_TIMEOUT")
    max_retries = int(os.environ.get("OASIS_MODEL_MAX_RETRIES", "3"))
    generation_max_tokens = int(os.environ.get("OASIS_MODEL_GENERATION_MAX_TOKENS", "1024"))
    dcw = os.environ.get("OASIS_MODEL_CONTEXT_WINDOW")
    ctl = os.environ.get("OASIS_CONTEXT_TOKEN_LIMIT")

    temp_defaults = {
        "ollama": 0.4,
        "deepseek": 0.8,
        "openai": 0.7,
        "openrouter": 0.7,
        "vllm": 0.7,
    }
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
        # 默认给一个更保守的请求超时，避免请求过早报 "Request timed out."
        # 可通过 OASIS_MODEL_TIMEOUT（秒）覆盖。
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
    """去掉 BOM、全角方括号等，便于定位 JSON。"""
    return (
        text.replace("\ufeff", "")
        .replace("［", "[")
        .replace("］", "]")
        .strip()
    )


def _strip_leading_reasoning_and_noise(text: str) -> str:
    """去掉推理标签、常见说明前缀，保留其后 JSON 正文（多段标签时反复截取）。"""
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
    # 去掉开头的 Markdown 一级标题行（部分模型爱写「以下是…」）
    t = re.sub(r"^#+\s.*\n+", "", t).strip()
    return t


def _outer_object_bounds(s: str) -> tuple[int, int] | None:
    """定位最外层 JSON 对象的 {{ 与匹配的 }}，忽略字符串内的花括号。"""
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
    return bool(
        keys
        & {
            "username",
            "user_name",
            "name",
            "bio",
            "persona",
            "interests",
            "description",
        }
    )


def _list_from_wrapping_object(obj: dict[str, Any]) -> list[dict[str, Any]] | None:
    """支持 {{ \"users\": [...] }}、{{ \"data\": {{ \"list\": [...] }} }} 等常见包装。"""
    preferred = (
        "users",
        "profiles",
        "personas",
        "agents",
        "items",
        "generated_users",
        "user_list",
        "results",
        "data",
    )
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
    """顶层为数组、包装对象或单条用户对象时，直接得到列表。"""
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
    """解析连续多个顶层 {{...}}（换行分隔或紧挨），无外层数组。"""
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
    """全文无 [ 时，截取第一个与括号匹配的 {{...}} 作为单条用户。"""
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
    """定位最外层 JSON 数组的 [ 与匹配的 ]，忽略字符串内的括号。"""
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
    """去掉 JSON 结构里 }, 或 ], 前的尾随逗号（启发式，可能误伤极少数字符串内容）。"""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r",(\s*[}\]])", r"\1", s)
    return s


def _parse_json_array_incremental(array_text: str) -> list[Any]:
    """用 raw_decode 逐个解析数组元素；某条损坏时仍可能保留前几条。"""
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
                logger.warning(
                    "增量解析在偏移 %s 中断，已保留前 %d 条: %s 尾部: %r",
                    i,
                    len(items),
                    e,
                    tail[:160],
                )
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


def _json_array_candidates(text: str) -> list[str]:
    """从全文或 ```json 代码块中收集可能的数组子串（去重保序）。"""
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
        preview = text[:480] + ("..." if len(text) > 480 else "")
        logger.warning("无法从模型输出中定位 JSON 数组，原文开头: %r", preview)
        raise ValueError(
            "无法在模型输出中定位 JSON 数组（未找到合法的 [] 或用户对象）。"
            f" 输出开头: {preview!r}"
        )

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
    keys = (
        "username",
        "user_name",
        "name",
        "realname",
        "bio",
        "description",
        "persona",
        "interests",
        "country",
        "gender",
        "age",
        "mbti",
        "twitter_user_id",
        "user_type",
    )
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
    """将 interests 限制为仅包含本轮已生成的仿真话题 title（入库后写入 profile.other_info.topics）。"""
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
        ratio_hint = (
            f"\n- user_type: 字符串，只能为 \"kol\" 或 \"normal\"；本次希望生成 kol={kol_target}、normal={normal_target}（允许±1 的浮动，但总体比例需接近）。"
        )
    ctx_block = ""
    if global_context and str(global_context).strip():
        ctx_block = (
            "\n\n【仿真话题与观测背景（须结合以下语义生成用户兴趣与表达风格，勿照抄原文）】\n"
            + str(global_context).strip()[:12000]
        )
    titles_block = ""
    interests_spec = "- interests: 字符串数组，3~8 个兴趣标签（可与种子风格相近，但勿照抄种子原文）"
    if allowed_synthetic_topic_titles:
        titles_json = json.dumps(allowed_synthetic_topic_titles, ensure_ascii=False, indent=2)
        titles_block = (
            "\n\n【合法话题标题】（仅允许将下列字符串作为 interests 数组的元素；"
            "必须与其中某一项**逐字完全相同**，含空格与标点，不得翻译、缩写或自拟新话题名）\n"
            f"{titles_json}\n"
        )
        interests_spec = (
            "- interests: 字符串数组，长度必须为 **1～3**。"
            " 每一项必须是上方【合法话题标题】JSON 数组中的某一个值的**逐字完全相同**的拷贝；"
            "不得包含任何不在该列表中的字符串。"
        )
    return f"""你是社交媒体用户画像建模专家。下面是一批真实采样用户（JSON），平台类型约为: {recsys_type}。
{ctx_block}
{titles_block}

请根据这些用户在兴趣分布、表达风格、人口属性上的统计特征，**新造** {batch_size} 个**虚构**用户画像，用于社会仿真。要求：
- 与种子用户在整体分布上相似，但 username / bio / 具体兴趣组合要有明显差异，避免抄袭原文；
- 每个用户一条 JSON 对象，字段尽量齐全，便于后续入库；
- 仅输出一个 JSON 数组，不要 Markdown、不要解释文字；
- bio / persona 等字符串里若出现英文双引号，必须写成 \\"；不要用中文弯引号；键名必须用双引号；不要尾随逗号。
{ratio_hint}

每条对象建议使用如下字段（缺失可 null，数组可为空）：
- username: 字符串，小写英文/数字下划线风格，唯一
- name: 显示名
- bio: **单行**个人简介，口语化、信息密度高；**总长度不超过约 80 个字符**（中文按字计），不要分段、不要列表
- persona: **1～2 句**短句，概括性格与说话习惯；**总长度不超过约 120 个字符**，不要长篇背景故事
{interests_spec}
- country, gender, age, mbti: 与种子分布合理一致（尽量给出具体 age 整数）
- user_type: "kol" 或 "normal"

本批次编号: {batch_index}（用于你区分批次，不要在输出中包含此编号）。

【种子用户示例】
{seeds_json}
"""


_JSON_STRICT_RETRY_SUFFIX = (
    "\n\n【再次强调】只输出一个合法 JSON 数组，不要有其它文字。"
    "字符串内的英文双引号必须转义为反斜杠加双引号；不要使用尾随逗号；不要使用 Markdown 代码块。"
)


def run_llm_batch(model: Any, prompt: str, max_retries: int) -> list[dict[str, Any]]:
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
            if not isinstance(arr, list):
                raise ValueError("解析结果不是数组")
            out: list[dict[str, Any]] = []
            for item in arr:
                if isinstance(item, dict):
                    out.append(item)
            if not out:
                raise ValueError("数组内无有效对象")
            return out
        except Exception as e:
            last_err = e
            logger.warning("批次调用失败 (%s/%s): %s", attempt + 1, max_retries, e)
    hint = ""
    err_s = str(last_err)
    if "Model Not Exist" in err_s or "model_not_found" in err_s.lower():
        hint = (
            " 【模型名错误】请修改 .env 中的 OASIS_MODEL_TYPE，使其与当前 OASIS_MODEL_URL / PLATFORM 上真实存在的模型 ID 一致："
            "Ollama 用 `ollama list` 中的名称（如 qwen3:8b）；"
            "DeepSeek 官方 API 多为 deepseek-chat；"
            "OpenRouter 多为 vendor/model（如 deepseek/deepseek-chat）。"
            "若走自建 vLLM/OpenAI 兼容网关，名称需与该网关登记的 model 字段一致。"
        )
    elif "502" in err_s or "503" in err_s or "504" in err_s:
        hint = (
            " （HTTP 502/503/504 多为模型网关或服务不可用：请确认 Ollama/推理服务已启动，"
            "OASIS_MODEL_URL 与 OASIS_MODEL_PLATFORM 配置正确；若经 Nginx 反代，需调大 proxy_read_timeout。）"
        )
    elif "400" in err_s and "invalid_request" in err_s:
        hint = (
            " （HTTP 400：多为请求参数/模型名不合法，请核对 OASIS_MODEL_TYPE、OASIS_MODEL_PLATFORM 与服务商文档。）"
        )
    elif "delimiter" in err_s or "JSON" in err_s or "Expecting" in err_s:
        hint = (
            " （模型返回的 JSON 不合法：已尝试修复尾随逗号与分段解析。"
            "可尝试减小每批生成条数（如请求体 llmBatchSize）或换更守格式的模型。）"
        )
    elif "无法定位" in err_s or "未找到合法的" in err_s:
        hint = (
            " （未识别到顶层 []：已尝试整段 JSON、`users` 等包装字段、多行对象、推理结束标记后的正文。"
            "请根据报错里的「输出开头」确认模型是否只返回了说明文字；必要时换模型或关闭推理长输出。）"
        )
    raise RuntimeError(f"批次在 {max_retries} 次重试后仍失败: {last_err}{hint}")


def map_llm_row_to_raw_user(
    row: dict[str, Any],
    *,
    dataset_id: str,
    recsys_type: str,
    index: int,
) -> dict[str, Any]:
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

    tid = f"llm_{dataset_id[:32]}_{index}"
    if len(tid) > 64:
        tid = tid[:64]

    # 简介保持短小，便于列表与图谱悬停展示（超出部分在入库前截断）
    bio_short = bio[:220] if bio else ""
    persona_short = persona[:360] if persona else ""

    return {
        "dataset_id": dataset_id,
        "recsys_type": recsys_type,
        "user_name": uname[:120],
        "name": name[:200],
        "description": bio_short,
        "profile": {
            "other_info": {
                "user_profile": persona_short,
                "topics": interests,
                "user_type": user_type,
                "country": row.get("country"),
                "gender": row.get("gender"),
                "age": age_val,
                "mbti": row.get("mbti"),
            }
        },
        "twitter_user_id": tid,
        "source": "llm_generated",
        "ingest_status": "generated",
    }


def generate_synthetic_topics(
    model: Any,
    *,
    selected_topics: list[dict[str, Any]],
    topic_count: int,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """根据已选观测话题，让模型再生成若干条「仿真讨论话题」。"""
    n = max(1, min(64, int(topic_count)))
    sel = [t for t in selected_topics if isinstance(t, dict)][:80]
    sel_json = json.dumps(sel, ensure_ascii=False, indent=2)
    prompt = f"""你是社交媒体趋势分析专家。下面是平台已观测到的一批真实话题（含标题），平台偏 Twitter/X 类短内容。

请基于这些话题的**主题域与语气**，**虚构** {n} 个**新的**讨论话题，用于社会仿真；不要复制原话题标题，要有合理多样性（可含政治/科技/生活等子域，但勿输出违法或极端仇恨内容）。

只输出一个 JSON 数组，不要 Markdown。每项对象字段：
- title: 字符串，简短话题名（可含中文或英文）
- summary: 字符串，1~2 句说明该话题在讨论什么

【已观测话题】
{sel_json}
"""
    batch = run_llm_batch(model, prompt, max_retries)
    out: list[dict[str, Any]] = []
    for item in batch:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        summary = str(item.get("summary") or item.get("description") or "").strip()
        if not title:
            continue
        out.append({"title": title[:300], "summary": summary[:800]})
        if len(out) >= n:
            break
    if len(out) < min(n, 1):
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
    """
    根据种子用户调用 LLM，生成 target_count 条可写入 raw.users 形态的文档。

    synthetic_topic_titles: 若提供（通常为先前 generate_synthetic_topics 的 title 列表），
    则提示词与后处理均保证 interests / profile.other_info.topics 仅来自这些标题。
    """
    if target_count < 1:
        raise ValueError("target_count 须 >= 1")
    if not seed_users:
        raise ValueError("seed_users 不能为空")

    random.seed(int(os.environ.get("OASIS_PERSONA_GEN_SEED", "42")))
    pool = [_compact_user(u) for u in seed_users if isinstance(u, dict)]
    if not pool:
        raise ValueError("种子用户无法规范化")

    titles_norm = _normalize_synthetic_topic_titles(synthetic_topic_titles)

    spec = model_spec_from_env()
    resolved = build_shared_model(spec)
    model = resolved.model

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
        logger.info(
            "LLM persona 批次 %s: 本批 %s 条, 剩余 %s",
            batch_index,
            this_batch,
            remaining,
        )
        before_len = len(mapped)
        batch = run_llm_batch(model, prompt, max_retries)
        # 按配额筛选：优先满足剩余的 kol/normal 需求
        picked: list[dict[str, Any]] = []
        for row in batch:
            if not isinstance(row, dict):
                continue
            ut = str(row.get("user_type") or row.get("type") or row.get("role") or "").strip().lower()
            if ut not in ("kol", "normal"):
                ut = "normal"
            if ut == "kol":
                if kol_need <= 0:
                    continue
                kol_need -= 1
            else:
                if normal_need <= 0:
                    continue
                normal_need -= 1
            picked.append(row)
            if len(picked) >= this_batch:
                break
        batch = picked
        base_idx = len(mapped)
        for i, row in enumerate(batch):
            if not isinstance(row, dict):
                continue
            if titles_norm:
                _enforce_interests_only_synthetic_titles(row, titles_norm)
            mapped.append(
                map_llm_row_to_raw_user(
                    row,
                    dataset_id=dataset_id,
                    recsys_type=recsys_type,
                    index=base_idx + i,
                )
            )
        remaining = target_count - len(mapped)
        if len(batch) < this_batch:
            logger.warning("本批仅解析到 %s 条", len(batch))
        if len(mapped) == before_len:
            raise RuntimeError(
                f"LLM 本批未生成可解析用户（已 {len(mapped)}/{target_count}）。"
                "请检查模型输出或减小 batch_size / 换模型。"
            )

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
