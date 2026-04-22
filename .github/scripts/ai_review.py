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

PROVIDERS = {
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-sonnet-4-20250514",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-reasoner",
    },
    "deepseek-v3": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v3",
    },
}


def _gh_client() -> httpx.Client:
    return httpx.Client(
        base_url=API_URL,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=30,
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


def post_review(body: str, comments: list[dict]):
    payload = {
        "body": body,
        "event": "COMMENT",
        "comments": comments,
    }
    r = GH.post(f"/repos/{REPO}/pulls/{PR_NUMBER}/reviews", json=payload)
    if r.status_code in (200, 201):
        print(f"Review posted ({len(comments)} inline comments)")
    else:
        print(f"Failed to post review: {r.status_code} {r.text}", file=sys.stderr)
        # Fallback: post as a single PR comment
        fallback = body
        if comments:
            fallback += "\n\n---\n### 行内评论\n"
            for c in comments:
                fallback += f"\n**`{c['path']}:{c.get('line', '?')}`** — {c['body']}\n"
        GH.post(
            f"/repos/{REPO}/issues/{PR_NUMBER}/comments",
            json={"body": fallback},
        )
        print("Posted as fallback issue comment.")


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
- 只输出 JSON 对象，不要输出其他内容。
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
    """Extract JSON from LLM response, stripping code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


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
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": PROVIDERS["anthropic"]["model"],
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    r.raise_for_status()
    text = r.json()["content"][0]["text"]
    return _parse_llm_json(text)


def _call_openai_compatible(api_key: str, prompt: str) -> dict:
    cfg = PROVIDERS[LLM_PROVIDER]
    r = httpx.post(
        f"{cfg['base_url']}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg["model"],
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return _parse_llm_json(text)


# ── Main flow ──────────────────────────────────────────────────

def main():
    print(f"正在审查 PR #{PR_NUMBER} in {REPO} (provider: {LLM_PROVIDER}, level: {REVIEW_LEVEL})")

    diff = get_pr_diff()
    if not diff.strip():
        print("Diff 为空，无需审查。")
        return

    # Build extra context from changed files
    changed = get_changed_files()
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
        except Exception as e:
            print(f"第 {i + 1} 块 LLM 调用失败: {e}", file=sys.stderr)
            summary_parts.append(f"⚠️ 第 {i + 1} 块审查失败: {e}")
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

    post_review(body, valid_comments)


if __name__ == "__main__":
    main()
