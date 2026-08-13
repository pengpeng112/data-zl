import httpx
import pytest

from app.core.config import settings
from app.services.dify_quality_client import DifyClientError, DifyQualityClient


def _client(status=200, content=b'{"data":{"outputs":{}}}', headers=None):
    def handler(request):
        return httpx.Response(status, content=content, headers=headers or {}, request=request)
    return DifyQualityClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_allowlist_rejects_userinfo_query_fragment_and_port(monkeypatch):
    monkeypatch.setattr(settings, "dify_base_url", "http://user:pass@10.10.8.53:8080/v1")
    monkeypatch.setattr(settings, "dify_allowed_hosts", ["10.10.8.53"])
    with pytest.raises(DifyClientError, match="allowlisted"):
        _client().run_workflow(inputs={}, user="u")


def test_redirect_and_oversize_are_blocked(monkeypatch):
    monkeypatch.setattr(settings, "dify_base_url", "http://10.10.8.53/v1")
    monkeypatch.setattr(settings, "dify_allowed_hosts", ["10.10.8.53"])
    monkeypatch.setattr(settings, "dify_max_response_bytes", 8)
    monkeypatch.setattr(settings, "dify_quality_api_key_ref", "env:TEST_DIFY_KEY")
    monkeypatch.setenv("TEST_DIFY_KEY", "secret")
    with pytest.raises(DifyClientError, match="response_too_large"):
        _client(content=b"0123456789").run_workflow(inputs={}, user="u")


def test_status_never_contains_key(monkeypatch, tmp_path):
    key = tmp_path / "key"
    key.write_text("secret", encoding="utf-8")
    key.chmod(0o600)
    monkeypatch.setattr(settings, "dify_quality_api_key_ref", f"file://{key}")
    assert "secret" not in repr(DifyQualityClient())


@pytest.mark.parametrize(
    ("status", "error_class"),
    [(401, "auth"), (403, "auth"), (429, "rate_limited"), (500, "server"), (422, "validation")],
)
def test_http_error_matrix(monkeypatch, status, error_class):
    monkeypatch.setattr(settings, "dify_base_url", "http://10.10.8.53/v1")
    monkeypatch.setattr(settings, "dify_allowed_hosts", ["10.10.8.53"])
    monkeypatch.setattr(settings, "dify_quality_api_key_ref", "env:TEST_DIFY_KEY")
    monkeypatch.setenv("TEST_DIFY_KEY", "secret")
    with pytest.raises(DifyClientError) as exc:
        _client(status=status).run_workflow(inputs={}, user="u")
    assert exc.value.error_class == error_class


def test_redirect_invalid_json_and_timeout(monkeypatch):
    monkeypatch.setattr(settings, "dify_base_url", "http://10.10.8.53/v1")
    monkeypatch.setattr(settings, "dify_allowed_hosts", ["10.10.8.53"])
    monkeypatch.setattr(settings, "dify_quality_api_key_ref", "env:TEST_DIFY_KEY")
    monkeypatch.setenv("TEST_DIFY_KEY", "secret")
    with pytest.raises(DifyClientError) as redirect:
        _client(status=307, headers={"location": "http://127.0.0.1/private"}).run_workflow(inputs={}, user="u")
    assert redirect.value.error_class == "redirect_blocked"
    with pytest.raises(DifyClientError) as malformed:
        _client(content=b"not-json").run_workflow(inputs={}, user="u")
    assert malformed.value.error_class == "invalid_json"

    def timeout_handler(request):
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    timed = DifyQualityClient(client=httpx.Client(transport=httpx.MockTransport(timeout_handler)))
    with pytest.raises(DifyClientError) as timeout:
        timed.run_workflow(inputs={}, user="u")
    assert timeout.value.error_class == "timeout"
