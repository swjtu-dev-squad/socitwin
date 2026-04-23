"""AI PR Review - Automated code review using LLM."""

import json
import os
import sys
from pathlib import Path

import httpx

API_URL = os.environ.get("GITHUB_API_URL", "")
REPO = os.environ.get("REPOSITORY", "")
PR_NUMBER = int(os.environ.get("PR_NUMBER", "0"))
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REVIEW_LEVEL = os.environ.get("REVIEW_LEVEL", "standard")
MAX_DIFF_LINES = int(os.environ.get("MAX_DIFF_LINES", "4000"))

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek").lower()

# Store last LLM response for debugging
last_llm_response: str = ""

PROVIDERS = {
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 8192,  # Claude 最大 8192
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "max_tokens": 4096,  # GPT-4o 最大 4096
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "max_tokens": 8192,  # DeepSeek 最大 8192
    },
    "deepseek-v3": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v3",
        "max_tokens": 8192,
    },
}


def _gh_client() -> httpx.Client:
    return httpx.Client(
        base_url=API_URL,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=60,  # 增加到 60 秒，避免获取大 diff 时超时
    )


GH = _gh_client()


# ── GitHub helpers ─────────────────────────────────────────────

def get_pr_diff() -> str:
    r = GH.get(f"/repos/{REPO}/pulls/{PR_NUMBER}", headers={"Accept": "application/vnd.github.v3.diff"})
    r.raise_for_status()
    return r.text


def get_changed_files() -> list[dict]:
    r = GH.get(f"/repos/{REPO}/pulls/{PR_NUMBER}/files")
    r.raise_for_status()
    return r.json()


def get_file_content(path: str, ref: str) -> str | None:
    r = GH.get(f"/repos/{REPO}/contents/{path}", params={"ref": ref})
    if r.status_code != 200:
        return None
    import base64
    return base64.b64decode(r.json()["content"]).decode("utf-8", errors="replace")


def post_review(body: str, comments: list[dict], file_patches: dict[str, str]):
    """Post review with inline comments. Falls back to issue comment with code snippets."""
    payload = {
        "body": body,
        "event": "COMMENT",
        "comments": comments,
    }
    r = GH.post(f"/repos/{REPO}/pulls/{PR_NUMBER}/reviews", json=payload)
    if r.status_code in (200, 201):
        print(f"Review posted ({len(comments)} inline comments)")
    else:
        print(f"Failed to post review: HTTP {r.status_code}", file=sys.stderr)
        # Fallback: post as a single PR comment with code snippets
        fallback = body
        if comments:
            fallback += "\n\n---\n### 行内评论\n\n"
            for c in comments:
                path = c['path']
                line = c.get('line', '?')
                comment_body = c['body']
                fallback += f"**`{path}:{line}`**\n\n{comment_body}\n\n"
                # Try to include code snippet if available
                if path in file_patches and line != '?':
                    code_line = _extract_line_from_patch(file_patches[path], line)
                    if code_line:
                        fallback += f"```diff\n{code_line}\n```\n\n"
        GH.post(
            f"/repos/{REPO}/issues/{PR_NUMBER}/comments",
            json={"body": fallback},
        )
        print("Posted as fallback issue comment.")


def _extract_line_from_patch(patch: str, target_line: int) -> str | None:
    """Extract a specific line from unified diff patch."""
    if not patch:
        return None
    current_line = 0
    for line in patch.splitlines():
        if line.startswith('@@'):
            # Parse line number: @@ -start,count +start,count @@
            parts = line.split()
            if len(parts) >= 3:
                hunk = parts[2]  # e.g., +123,45
                if hunk.startswith('+'):
                    hunk = hunk[1:]
                    if ',' in hunk:
                        current_line = int(hunk.split(',')[0])
                    else:
                        current_line = int(hunk)
                else:
                    current_line = int(hunk[1:]) if hunk.startswith('+') else 0
        elif line.startswith('+') and not line.startswith('+++'):
            current_line += 1
            if current_line == target_line:
                return line
        elif line.startswith(' ') or line.startswith('-'):
            current_line += 1
    return None


# ── LLM helpers ────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是 socitwin 项目的高级代码审查员 — 这是一个社交媒体模拟平台
后端采用 Python/FastAPI (async, Pydantic, SQLite, CAMEL-AI/OASIS 用于 LLM 集成)
前端采用 React/TypeScript (Vite, Tailwind, D3.js, Zustand, Socket.io)。

审查以下 PR diff。请返回一个 JSON 对象，格式如下：

{
  "summary": "1-3 句话的总体评价",
  "comments": [
    {
      "path": "relative/file/path.py",
      "line": 42,
      "side": "RIGHT",
      "body": "markdown 格式的评论内容"
    }
  ]
}

## 审查严重级别

每条评论必须以以下标记之一开头：
- 🔴 **Critical** — 安全漏洞、数据丢失、崩溃、注入攻击、硬编码密钥
- ⚠️ **Warning** — 逻辑错误、资源泄漏、缺失校验、竞态条件
- 💡 **Suggestion** — 命名规范、可读性、可测试性、文档建议、小改进
- ✅ **Looks Good** — 值得肯定的良好实践

## 项目专项检查

后端 (Python/FastAPI)：
- 路由函数必须有异常处理
- 数据库操作必须使用参数化查询 / ORM
- LLM API 调用必须有超时和重试机制
- Pydantic schema 必须校验输入
- 异步函数不能混用阻塞 I/O

前端 (React/TypeScript)：
- API 调用需要错误边界处理
- 注意内存泄漏（未清理的监听器、定时器）
- 不能硬编码密钥或用 console.log 输出敏感数据
- 正确的 TypeScript 类型（避免使用 `any`）

通用：
- 新增代码应包含测试
- 配置文件（.env, lock 文件）不应无故修改
- PR 应关联相关 issue

## 规则
- 简洁明了。每条评论最多 6 行。
- 只评论 diff 中出现的行。使用 RIGHT 侧行号。
- 跳过生成文件、lock 文件和第三方代码。
- 如果 diff 很干净，返回空的 comments 数组和正面评价的 summary。

## ⚠️ 输出格式要求（严格遵守）
- **只输出纯 JSON 对象**，不要有任何其他文字、解释或代码围栏标记
- 不要用 ```json 或 ``` 包裹
- 不要输出 "以下是审查结果" 等前缀
- 直接以 { 开始，以 } 结束
- 即使是推理型模型，也不要在输出中包含推理过程
- **确保输出完整的 JSON，不要因长度限制而截断**
- 如果评论内容太长，减少评论数量或缩短每条评论，但必须输出完整可解析的 JSON

正确示例：
{"summary": "...", "comments": []}
"""


def build_prompt(diff: str, extra_context: str) -> str:
    level_hint = "严格模式 — 标记所有问题，包括小问题。" if REVIEW_LEVEL == "strict" else "标准模式 — 重点关注显著问题，忽略吹毛求疵。"
    return f"""\
审查强度: {REVIEW_LEVEL}。{level_hint}

## PR Diff
```diff
{diff}
```

{extra_context}
"""


def chunk_diff(diff: str, max_lines: int = MAX_DIFF_LINES) -> list[str]:
    lines = diff.splitlines()
    if len(lines) <= max_lines:
        return [diff]
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunks.append("\n".join(lines[i : i + max_lines]))
    return chunks


def _parse_llm_json(text: str) -> dict:
    """Extract JSON from LLM response, with robust handling of various formats.

    Handles:
    - Standard code fences: ```json ... ```
    - DeepSeek Reasoner: <reasoning>...</reasoning> tags
    - Mixed content: text before/after JSON
    - Multiple code blocks (extracts the first valid JSON)
    - Truncated JSON (attempts to fix)
    """
    text = text.strip()

    # 1. Remove DeepSeek Reasoner's <reasoning> tags
    if "<reasoning>" in text:
        # Keep content after </reasoning>
        parts = text.split("</reasoning>", 1)
        text = parts[1] if len(parts) > 1 else text

    # 2. Extract content from code fences
    if "```" in text:
        # Find all code blocks and try to parse each
        lines = text.split("\n")
        in_code_block = False
        code_blocks = []
        current_block = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                if not in_code_block and current_block:
                    code_blocks.append("\n".join(current_block))
                    current_block = []
                continue
            if in_code_block:
                current_block.append(line)

        # Try each code block until we find valid JSON
        for block in code_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # 3. Fallback: simple fence removal (original logic)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]

    # 4. Try direct parsing
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # 5. Attempt to fix truncated JSON
        try:
            return _fix_truncated_json(text)
        except Exception:
            # 6. Last resort: try to find JSON object boundaries
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    extracted = text[start_idx:end_idx + 1]
                    return _fix_truncated_json(extracted)
                except Exception:
                    pass
            raise


def _fix_unescaped_quotes(text: str) -> str:
    """Fix unescaped quotes inside JSON string values.

    Uses a state machine to track whether we're inside a string value.
    Quotes inside string values that aren't escaped will be escaped.
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        if not in_string:
            # Not in a string, looking for string start
            if char == '"':
                in_string = True
                result.append(char)
            elif char == '\\':
                # Might be escaping something outside string (unusual but possible)
                result.append(char)
                escape_next = True
            else:
                result.append(char)
        else:
            # Inside a string
            if escape_next:
                # Previous char was backslash, this char is escaped
                result.append(char)
                escape_next = False
            elif char == '\\':
                # This is an escape character
                result.append(char)
                escape_next = True
            elif char == '"':
                # End of string or unescaped quote inside string
                # Look ahead to determine
                # Skip whitespace
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1

                if j < len(text):
                    next_non_ws = text[j]
                    # If followed by :, ,, }, ], the string ended
                    if next_non_ws in (':', ',', '}', ']'):
                        in_string = False
                        result.append(char)
                    elif next_non_ws == '"':
                        # Two quotes in a row - likely a structural pattern
                        in_string = False
                        result.append(char)
                    else:
                        # Still inside the string, escape this quote
                        result.append('\\"')
                else:
                    # End of text, string should end
                    in_string = False
                    result.append(char)
            else:
                result.append(char)

        i += 1

    return ''.join(result)


def _fix_truncated_json(text: str) -> dict:
    """Attempt to fix truncated JSON by completing incomplete structures.

    Common truncation patterns:
    - "comments": [    →    "comments": []
    - "body": "text... →  "body": "text [truncated]"
    - Missing closing braces/brackets
    - Unescaped quotes in string values
    """
    text = text.strip()

    # First, try to fix unescaped quotes in string values
    try:
        text = _fix_unescaped_quotes(text)
    except Exception:
        pass  # If fixing fails, continue with original text

    # Fix truncated comments array
    if '"comments": [' in text and not '"comments": []' in text:
        # Check if comments array is incomplete
        comments_idx = text.find('"comments": [')
        if comments_idx != -1:
            after_comments = text[comments_idx + 13:]
            # If array doesn't close properly or has incomplete object
            if not any(after_comments.strip().startswith(s) for s in (']', '}', '{')):
                # Try to close the array
                if after_comments.strip() and after_comments.strip()[0] in ('{', '['):
                    # Has content but not closed, close what we can
                    text = text[:comments_idx + 13] + '[]'
                else:
                    # Empty or incomplete, replace with empty array
                    text = text[:comments_idx + 13] + '[]'

    # Fix truncated string values (common with "...")
    # Use Unicode escape sequence for ellipsis character
    ellipsis = chr(0x2026)  # Unicode ellipsis character (…)
    if '"..."' in text or ellipsis in text or '...' in text:
        # Replace truncated strings with placeholder
        import re
        text = re.sub(r'"[^"]*\.\.\.\'"', '"[内容被截断]', text)
        # Match strings ending with Unicode ellipsis or ASCII ellipsis
        text = re.sub(r'"[^"]*[' + ellipsis + r']"', '"[内容被截断]', text)

    # Balance braces/brackets
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')

    # Add missing closing brackets/braces
    text += '}' * max(0, open_braces - close_braces)
    text += ']' * max(0, open_brackets - close_brackets)

    # Remove trailing comma before closing brackets/braces
    text = re.sub(r',\s*([}\]])', r'\1', text)

    return json.loads(text)


def _get_api_key(provider: str) -> str:
    cfg = PROVIDERS[provider]
    return os.environ.get(cfg["api_key_env"], "")


def call_llm(prompt: str) -> dict:
    if LLM_PROVIDER not in PROVIDERS:
        return {"summary": f"⚠️ 未知的 LLM_PROVIDER `{LLM_PROVIDER}`。可选: {', '.join(PROVIDERS)}", "comments": []}

    api_key = _get_api_key(LLM_PROVIDER)
    if not api_key:
        env_name = PROVIDERS[LLM_PROVIDER]["api_key_env"]
        return {"summary": f"⚠️ 未配置 {env_name}。跳过 AI 审查。", "comments": []}

    if LLM_PROVIDER == "anthropic":
        return _call_anthropic(api_key, prompt)
    return _call_openai_compatible(api_key, prompt)


def _call_anthropic(api_key: str, prompt: str) -> dict:
    global last_llm_response
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": PROVIDERS["anthropic"]["model"],
            "max_tokens": PROVIDERS["anthropic"].get("max_tokens", 8192),
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    r.raise_for_status()
    text = r.json()["content"][0]["text"]
    last_llm_response = text
    try:
        return _parse_llm_json(text)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败，原始响应:", file=sys.stderr)
        print(text[:1000] + ("..." if len(text) > 1000 else ""), file=sys.stderr)
        raise


def _call_openai_compatible(api_key: str, prompt: str) -> dict:
    global last_llm_response
    cfg = PROVIDERS[LLM_PROVIDER]
    payload = {
        "model": cfg["model"],
        "max_tokens": cfg.get("max_tokens", 8192),  # 使用各模型的最大输出限制
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    # 使用 JSON 模式强制输出有效 JSON（DeepSeek 和 OpenAI 都支持）
    if LLM_PROVIDER in ("deepseek", "deepseek-v3", "openai"):
        payload["response_format"] = {"type": "json_object"}

    r = httpx.post(
        f"{cfg['base_url']}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    last_llm_response = text
    try:
        return json.loads(text)  # JSON 模式保证输出纯 JSON，无需额外解析
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败，原始响应:", file=sys.stderr)
        print(text[:1000] + ("..." if len(text) > 1000 else ""), file=sys.stderr)
        raise


# ── Main flow ──────────────────────────────────────────────────

def main():
    print(f"正在审查 PR #{PR_NUMBER} in {REPO} (provider: {LLM_PROVIDER}, level: {REVIEW_LEVEL})")
    print("正在获取 PR diff...", flush=True)

    diff = get_pr_diff()
    if not diff.strip():
        print("Diff 为空，无需审查。")
        return

    print(f"Diff 获取成功，共 {len(diff.splitlines())} 行", flush=True)

    # Build extra context from changed files
    changed = get_changed_files()
    # Build a map of file path -> patch for code snippet extraction
    file_patches: dict[str, str] = {}
    for f in changed:
        if f.get("patch"):
            file_patches[f["filename"]] = f["patch"]
    ext_context = ""
    reviewable = [
        f for f in changed
        if not any(
            f["filename"].endswith(ext)
            for ext in (".lock", ".map", ".min.js", ".min.css")
        )
        and "node_modules" not in f["filename"]
        and "vendor" not in f["filename"]
    ]
    if reviewable:
        ext_context = "## 变更文件\n"
        for f in reviewable:
            ext_context += f"- `{f['filename']}` (+{f['additions']} -{f['deletions']})\n"

    print(f"Diff: {len(diff.splitlines())} 行, {len(reviewable)} 个可审查文件")

    chunks = chunk_diff(diff)
    all_comments: list[dict] = []
    summary_parts: list[str] = []

    for i, chunk in enumerate(chunks):
        print(f"正在审查第 {i + 1}/{len(chunks)} 块...")
        ctx = ext_context if i == 0 else ""
        prompt = build_prompt(chunk, ctx)
        try:
            result = call_llm(prompt)
        except json.JSONDecodeError as e:
            # Provide helpful debugging info
            exc_name = type(e).__name__
            print(f"第 {i + 1} 块 JSON 解析失败: {exc_name} - {e}", file=sys.stderr)

            # Show more detailed debugging info
            response_len = len(last_llm_response)
            response_start = last_llm_response[:800] if response_len > 800 else last_llm_response
            response_end = last_llm_response[-500:] if response_len > 500 else ""

            error_msg = f"""⚠️ **第 {i + 1} 块审查失败: {exc_name}**

**错误信息:** `{e}`

**响应长度:** {response_len} 字符

**响应开头:**
```
{response_start}
```

**响应结尾:**
```
{response_end}
```

**可能的原因：**
- LLM 添加了代码围栏 (\\`\\`\\`) 或额外文字
- DeepSeek Reasoner 输出了推理过程
- JSON 格式不完整或被截断
- 字符串中包含未转义的特殊字符

**建议：**
- 检查 GitHub Actions 日志查看完整响应
- 尝试使用 `deepseek-v3` 替代 `deepseek-reasoner`
- 或者手动审查此块变更
"""
            summary_parts.append(error_msg)
            continue
        except Exception as e:
            exc_name = type(e).__name__
            http_status = getattr(getattr(e, 'response', None), 'status_code', None)
            status_str = f" HTTP {http_status}" if http_status else ""
            print(f"第 {i + 1} 块 LLM 调用失败: {exc_name}{status_str}", file=sys.stderr)
            summary_parts.append(f"⚠️ 第 {i + 1} 块审查失败: {exc_name}{status_str}")
            continue

        summary_parts.append(result.get("summary", ""))
        all_comments.extend(result.get("comments", []))

    if not all_comments and not summary_parts:
        print("无审查输出。")
        return

    # Validate comment positions against changed files
    valid_paths = {f["filename"] for f in changed}
    valid_comments = [
        c for c in all_comments
        if c.get("path", "") in valid_paths
    ]
    skipped = len(all_comments) - len(valid_comments)
    if skipped:
        print(f"跳过 {skipped} 条文件路径无效的评论")

    summary = "\n\n".join(s for s in summary_parts if s)
    # Prepend metadata header
    header = f"## 🤖 AI 代码审查 (`{LLM_PROVIDER}` · `{REVIEW_LEVEL}`)\n\n"
    body = header + summary
    if chunks:
        body += f"\n\n_分 {len(chunks)} 个块审查。共 {len(valid_comments)} 条发现。_"

    post_review(body, valid_comments, file_patches)


if __name__ == "__main__":
    main()
