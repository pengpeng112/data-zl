"""Read-only hospital OpenAI-compatible chat client.

The model may only receive desensitized governance summaries and return
analysis text. It never receives credentials, SQL to execute, or write tools.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..core.config import settings


class HospitalLlmError(RuntimeError):
    def __init__(self, error_class: str, message: str | None = None):
        super().__init__(message or error_class)
        self.error_class = error_class


@dataclass
class HospitalLlmResponse:
    text: str
    model: str
    raw: dict


def iter_stream_deltas(lines) -> list[str]:
    """Parse OpenAI-style SSE lines into content deltas."""
    chunks: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = payload.get("choices") or []
        if not choices:
            continue
        delta = (choices[0] or {}).get("delta") or {}
        content = delta.get("content")
        if content:
            chunks.append(str(content))
    return chunks


def strip_think_stream(deltas) -> list[str]:
    """Drop <think>…</think> while keeping visible answer tokens."""
    visible: list[str] = []
    buf = ""
    in_think = False
    for delta in deltas:
        buf += str(delta or "")
        while buf:
            if in_think:
                end = buf.find("</think>")
                if end < 0:
                    buf = buf[-20:]
                    break
                buf = buf[end + 8:]
                in_think = False
                continue
            start = buf.find("<think>")
            if start >= 0:
                if start:
                    visible.append(buf[:start])
                buf = buf[start + 7:]
                in_think = True
                continue
            if len(buf) > 20:
                visible.append(buf[:-20])
                buf = buf[-20:]
            break
    if buf and not in_think:
        visible.append(buf)
    return visible


def extract_assistant_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = str(message.get("content") or "")
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    return content.strip()


class HospitalLlmClient:
    def __init__(self, *, client=None):
        self._client = client
        self._base = (settings.hospital_llm_base_url or "").rstrip("/")

    def _validate_base(self) -> None:
        parsed = urlparse(self._base)
        allowed = set(settings.hospital_llm_allowed_hosts or [])
        if (
            parsed.scheme != "http"
            or not parsed.hostname
            or parsed.hostname not in allowed
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/api"}
            or parsed.port not in {None, 9000}
        ):
            raise HospitalLlmError("ssrf_blocked", "Hospital LLM host is not allowlisted")

    def _api_key(self) -> str:
        ref = settings.hospital_llm_api_key_ref or ""
        if ref.startswith("env:"):
            key = os.environ.get(ref[4:], "").strip()
        elif ref.startswith("file://"):
            path = Path(ref[7:])
            try:
                if not path.is_absolute() or not path.is_file():
                    raise HospitalLlmError("not_configured", "Hospital LLM key file is invalid")
                mode = path.stat().st_mode & 0o777
                if mode & 0o077:
                    raise HospitalLlmError("not_configured", "Hospital LLM key file permissions are too broad")
                key = path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise HospitalLlmError("not_configured", "Hospital LLM key file is unreadable") from exc
        else:
            key = ""
        if not key or "\n" in key or "\r" in key or len(key) > 4096:
            raise HospitalLlmError("not_configured", "Hospital LLM key is not configured")
        return key

    def _http(self):
        if self._client is not None:
            return self._client
        return httpx.Client(
            timeout=httpx.Timeout(settings.hospital_llm_read_timeout_seconds, connect=settings.hospital_llm_connect_timeout_seconds),
            verify=False,
            follow_redirects=False,
        )

    def configured(self) -> bool:
        try:
            self._validate_base()
            self._api_key()
            return True
        except HospitalLlmError:
            return False

    def connection_test(self) -> dict:
        reply = self.complete("只回复：只读分析已接通。", max_tokens=32)
        return {"reachable": True, "model": reply.model, "sample": reply.text[:80]}

    def complete(self, user_text: str, *, max_tokens: int | None = None) -> HospitalLlmResponse:
        self._validate_base()
        key = self._api_key()
        if len(user_text.encode("utf-8")) > settings.hospital_llm_max_payload_bytes:
            raise HospitalLlmError("payload_too_large")
        body = {
            "model": settings.hospital_llm_model,
            "temperature": 0.1,
            "max_tokens": max_tokens or settings.hospital_llm_max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是医院数据资产质控助手。输入只来自数据资产平台库，不能直连业务库。"
                        "直接写中文说明，不要输出 JSON。举例要用传入的字段或关系。"
                        "不得建议执行 SQL/DDL。不确定就写待复核。"
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        }
        client = None
        response = None
        try:
            client = self._http()
            request = client.build_request(
                "POST",
                f"{self._base}/api/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            response = client.send(request, stream=True, follow_redirects=False)
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > settings.hospital_llm_max_response_bytes:
                    raise HospitalLlmError("response_too_large")
            raw = bytes(content)
        except httpx.TimeoutException as exc:
            raise HospitalLlmError("timeout") from exc
        except httpx.RequestError as exc:
            raise HospitalLlmError("network") from exc
        finally:
            if response is not None:
                response.close()
            if self._client is None and client is not None:
                client.close()
        if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
            raise HospitalLlmError("redirect_blocked")
        if response.status_code in {401, 403}:
            raise HospitalLlmError("auth")
        if response.status_code == 429:
            raise HospitalLlmError("rate_limited")
        if response.status_code >= 500:
            raise HospitalLlmError("server")
        if response.status_code >= 400:
            raise HospitalLlmError("validation")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HospitalLlmError("invalid_json") from exc
        if not isinstance(payload, dict):
            raise HospitalLlmError("invalid_json")
        text = extract_assistant_text(payload)
        if not text:
            raise HospitalLlmError("empty_response")
        return HospitalLlmResponse(text=text, model=str(payload.get("model") or settings.hospital_llm_model), raw=payload)

    def complete_stream(self, user_text: str, *, max_tokens: int | None = None):
        """Yield visible answer tokens. Think-blocks are discarded."""
        self._validate_base()
        key = self._api_key()
        if len(user_text.encode("utf-8")) > settings.hospital_llm_max_payload_bytes:
            raise HospitalLlmError("payload_too_large")
        body = {
            "model": settings.hospital_llm_model,
            "temperature": 0.1,
            "stream": True,
            "max_tokens": max_tokens or settings.hospital_llm_max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是医院数据资产质控助手。输入只来自数据资产平台库，不能直连业务库。"
                        "只分析当前问题。直接写中文【结论】【问题定位】【明细举例】【要不要处理】【处理建议】，不要输出 JSON。"
                        "举例必须用传入的缺注释字段或关系键。不得建议执行 SQL/DDL。"
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        }
        client = None
        response = None
        try:
            client = self._http()
            request = client.build_request(
                "POST",
                f"{self._base}/api/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            response = client.send(request, stream=True, follow_redirects=False)
            if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
                raise HospitalLlmError("redirect_blocked")
            if response.status_code in {401, 403}:
                raise HospitalLlmError("auth")
            if response.status_code == 429:
                raise HospitalLlmError("rate_limited")
            if response.status_code >= 500:
                raise HospitalLlmError("server")
            if response.status_code >= 400:
                raise HospitalLlmError("validation")
            hold = ""
            in_think = False
            for line in response.iter_lines():
                for piece in iter_stream_deltas([line]):
                    hold += piece
                    while hold:
                        if in_think:
                            end = hold.find("</think>")
                            if end < 0:
                                hold = hold[-20:]
                                break
                            hold = hold[end + 8:]
                            in_think = False
                            continue
                        start = hold.find("<think>")
                        if start >= 0:
                            if start:
                                yield hold[:start]
                            hold = hold[start + 7:]
                            in_think = True
                            continue
                        if len(hold) > 20:
                            yield hold[:-20]
                            hold = hold[-20:]
                        break
            if hold and not in_think:
                yield hold
        except httpx.TimeoutException as exc:
            raise HospitalLlmError("timeout") from exc
        except httpx.RequestError as exc:
            raise HospitalLlmError("network") from exc
        finally:
            if response is not None:
                response.close()
            if self._client is None and client is not None:
                client.close()
