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
        "model": "deepseek-chat",
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
            fallback += "\n\n---\n### Inline Comments\n"
            for c in comments:
                fallback += f"\n**`{c['path']}:{c.get('line', '?')}`** — {c['body']}\n"
        GH.post(
            f"/repos/{REPO}/issues/{PR_NUMBER}/comments",
            json={"body": fallback},
        )
        print("Posted as fallback issue comment.")


# ── LLM helpers ────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior code reviewer for the socitwin project — a social media simulation platform
with a Python/FastAPI backend (async, Pydantic, SQLite, CAMEL-AI/OASIS for LLM integration)
and a React/TypeScript frontend (Vite, Tailwind, D3.js, Zustand, Socket.io).

Review the PR diff below. Respond with a JSON object having exactly these keys:

{
  "summary": "1-3 sentence overall assessment",
  "comments": [
    {
      "path": "relative/file/path.py",
      "line": 42,
      "side": "RIGHT",
      "body": "markdown comment body"
    }
  ]
}

## Review severity levels

Each comment must start with one of these markers:
- 🔴 **Critical** — Security holes, data loss, crashes, injection, hardcoded secrets
- ⚠️ **Warning** — Logic errors, resource leaks, missing validation, race conditions
- 💡 **Suggestion** — Naming, readability, testability, documentation, minor improvements
- ✅ **Looks Good** — Notable good patterns worth highlighting

## Project-specific checks

Backend (Python/FastAPI):
- Route functions must have error handling
- Database operations must use parameterized queries / ORM
- LLM API calls must have timeout + retry
- Pydantic schemas must validate input
- Async functions must not mix blocking I/O

Frontend (React/TypeScript):
- API calls need error boundary handling
- Watch for memory leaks (unsubscribed listeners, dangling intervals)
- No hardcoded secrets or console.log with sensitive data
- Proper TypeScript typing (avoid `any`)

General:
- New code should include tests
- Config files (.env, lock files) should not be changed without reason
- PR should reference related issues

## Rules
- Be concise. Each comment: max 6 lines.
- Only comment on lines present in the diff. Use RIGHT side line numbers.
- Skip generated files, lock files, and vendored code.
- If the diff is clean, return an empty comments array and a positive summary.
- Output ONLY the JSON object, nothing else.
"""


def build_prompt(diff: str, extra_context: str) -> str:
    level_hint = "Be thorough and strict — flag even minor issues." if REVIEW_LEVEL == "strict" else "Focus on significant issues. Skip nitpicks."
    return f"""\
Review level: {REVIEW_LEVEL}. {level_hint}

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
        return {"summary": f"⚠️ Unknown LLM_PROVIDER `{LLM_PROVIDER}`. Choose from: {', '.join(PROVIDERS)}", "comments": []}

    api_key = _get_api_key(LLM_PROVIDER)
    if not api_key:
        env_name = PROVIDERS[LLM_PROVIDER]["api_key_env"]
        return {"summary": f"⚠️ {env_name} not configured. Skipping AI review.", "comments": []}

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
    print(f"Reviewing PR #{PR_NUMBER} in {REPO} (provider: {LLM_PROVIDER}, level: {REVIEW_LEVEL})")

    diff = get_pr_diff()
    if not diff.strip():
        print("Empty diff, nothing to review.")
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
        ext_context = "## Changed files\n"
        for f in reviewable:
            ext_context += f"- `{f['filename']}` (+{f['additions']} -{f['deletions']})\n"

    print(f"Diff: {len(diff.splitlines())} lines, {len(reviewable)} reviewable files")

    chunks = chunk_diff(diff)
    all_comments: list[dict] = []
    summary_parts: list[str] = []

    for i, chunk in enumerate(chunks):
        print(f"Reviewing chunk {i + 1}/{len(chunks)}...")
        ctx = ext_context if i == 0 else ""
        prompt = build_prompt(chunk, ctx)
        try:
            result = call_llm(prompt)
        except Exception as e:
            print(f"LLM call failed for chunk {i + 1}: {e}", file=sys.stderr)
            summary_parts.append(f"⚠️ Chunk {i + 1} review failed: {e}")
            continue

        summary_parts.append(result.get("summary", ""))
        all_comments.extend(result.get("comments", []))

    if not all_comments and not summary_parts:
        print("No review output.")
        return

    # Validate comment positions against changed files
    valid_paths = {f["filename"] for f in changed}
    valid_comments = [
        c for c in all_comments
        if c.get("path", "") in valid_paths
    ]
    skipped = len(all_comments) - len(valid_comments)
    if skipped:
        print(f"Skipped {skipped} comments with invalid file paths")

    summary = "\n\n".join(s for s in summary_parts if s)
    # Prepend metadata header
    header = f"## 🤖 AI Code Review (`{LLM_PROVIDER}` · `{REVIEW_LEVEL}`)\n\n"
    body = header + summary
    if chunks:
        body += f"\n\n_Reviewed in {len(chunks)} chunk(s). {len(valid_comments)} finding(s)._"

    post_review(body, valid_comments)


if __name__ == "__main__":
    main()
