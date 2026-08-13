from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.parse import urlparse

import httpx
import os
from pathlib import Path

from ..core.config import settings


class DifyClientError(RuntimeError):
    def __init__(self, error_class: str, message: str | None = None):
        super().__init__(message or error_class)
        self.error_class = error_class


@dataclass
class DifyResponse:
    payload: dict
    status_code: int


class DifyQualityClient:
    def __init__(self, *, client=None):
        self._client = client
        parsed = urlparse(settings.dify_base_url)
        self._base = settings.dify_base_url.rstrip("/")
        self._host = parsed.hostname or ""

    def _validate_base(self) -> None:
        parsed = urlparse(self._base)
        allowed = set(settings.dify_allowed_hosts or [])
        expected_port = 443 if parsed.scheme == "https" else 80
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.hostname not in allowed
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") != "/v1"
                or (parsed.port not in {None, expected_port})
                or (settings.env.lower() in {"prod", "production"} and parsed.scheme == "https" and not settings.dify_tls_verify)):
            raise DifyClientError("ssrf_blocked", "Dify host is not allowlisted")

    def _api_key(self) -> str:
        if not settings.dify_quality_api_key_ref:
            raise DifyClientError("not_configured", "Dify key is not configured")
        ref = settings.dify_quality_api_key_ref
        if ref.startswith("env:"):
            key = os.environ.get(ref[4:], "").strip()
        elif ref.startswith("file://"):
            path = Path(ref[7:])
            try:
                if not path.is_absolute() or not path.is_file():
                    raise DifyClientError("not_configured", "Dify key file is invalid")
                mode = path.stat().st_mode & 0o777
                if mode & 0o077:
                    raise DifyClientError("not_configured", "Dify key file permissions are too broad")
                key = path.read_text(encoding="utf-8").strip()
            except OSError:
                key = ""
        else:
            key = ""
        if not key or "\n" in key or "\r" in key or len(key) > 4096:
            raise DifyClientError("not_configured", "Dify key is not configured")
        return key

    def _http(self):
        if self._client is not None:
            return self._client
        verify = settings.dify_ca_bundle or settings.dify_tls_verify
        return httpx.Client(timeout=httpx.Timeout(settings.dify_read_timeout_seconds, connect=settings.dify_connect_timeout_seconds), verify=verify, follow_redirects=False)

    def _request(self, method: str, path: str, *, key: str, body: dict | None = None) -> tuple[int, bool, bytes]:
        client = None
        response = None
        try:
            client = self._http()
            request = client.build_request(
                method,
                f"{self._base}{path}",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            response = client.send(request, stream=True, follow_redirects=False)
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > settings.dify_max_response_bytes:
                    raise DifyClientError("response_too_large")
            return response.status_code, response.is_redirect, bytes(content)
        except httpx.TimeoutException as exc:
            raise DifyClientError("timeout") from exc
        except httpx.RequestError as exc:
            raise DifyClientError("network") from exc
        finally:
            if response is not None:
                response.close()
            if self._client is None and client is not None:
                client.close()

    @staticmethod
    def _classify(status_code: int, is_redirect: bool) -> None:
        if is_redirect or status_code in {301, 302, 303, 307, 308}:
            raise DifyClientError("redirect_blocked")
        if status_code in {401, 403}:
            raise DifyClientError("auth")
        if status_code == 429:
            raise DifyClientError("rate_limited")
        if status_code >= 500:
            raise DifyClientError("server")
        if status_code >= 400:
            raise DifyClientError("validation")

    def run_workflow(self, *, inputs: dict, user: str) -> DifyResponse:
        self._validate_base()
        key = self._api_key()
        body = {"inputs": inputs, "response_mode": "blocking", "user": user}
        status_code, is_redirect, content = self._request("POST", "/workflows/run", key=key, body=body)
        self._classify(status_code, is_redirect)
        try:
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("response must be an object")
            return DifyResponse(payload, status_code)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise DifyClientError("invalid_json") from exc

    def connection_test(self) -> dict:
        self._validate_base()
        key = self._api_key()
        status_code, is_redirect, _content = self._request("GET", "/parameters", key=key)
        self._classify(status_code, is_redirect)
        return {"reachable": True, "status_code": status_code}
