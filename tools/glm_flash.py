"""GLM-5.3-Flash cheap-task runner: delegates simple chores to the flash model.

Credential handling (hard rules):
- API key is read at runtime from the local ZCode config (~/.zcode/v2/config.json);
  it is never printed, never written to any file, never appears in error output.
- Only the final model response text is printed.

Usage:
  backend/.venv/Scripts/python.exe tools/glm_flash.py "把下面的清单压缩成三行：..." 
  echo "<long text>" | backend/.venv/Scripts/python.exe tools/glm_flash.py "翻译成英文"
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

CONFIG = Path(r"C:\Users\Administrator\.zcode\v2\config.json")
MODEL = "GLM-5.3-Flash"


def load_credentials() -> tuple[str, str]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    provider = cfg["provider"]["builtin:bigmodel-coding-plan"]
    return provider["options"]["apiKey"], provider["options"]["baseURL"]


def ask(prompt: str, max_tokens: int = 2000) -> str:
    api_key, base_url = load_credentials()
    body = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # never include request headers/body in errors (credential safety)
        raise SystemExit(f"GLM flash HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}")
    parts = payload.get("content") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
    return "\n".join(t for t in texts if t)


def main() -> int:
    instruction = sys.argv[1] if len(sys.argv) > 1 else "Reply with the single word: OK"
    stdin_text = ""
    if not sys.stdin.isatty():
        try:
            stdin_text = sys.stdin.read()
        except Exception:
            stdin_text = ""
    prompt = instruction if not stdin_text else f"{instruction}\n\n---\n{stdin_text}"
    print(ask(prompt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
