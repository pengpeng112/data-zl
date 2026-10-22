"""企微公共告警 relay v2 客户端：HMAC 原字节签名、202 只入队、逐目标送达跟踪。

对应《企业微信公共告警接口对接设计.md》与候选配置：
- 签名输入 = UTF8(source_id + "." + unix_seconds + ".") + 实际请求字节
  （body 为冻结的 UTF-8 JSON 原字节）；HMAC-SHA256 hex 小写；GET 以空 body 签。
- POST 202 = ACK_QUEUED（入队≠送达）；200 duplicate 复用 relay_event_id；
  401 停通道盲重试；400/422 永久报文错误；409 分型（防重放可跨秒重签 /
  内容冲突 NEEDS_ATTENTION）；429 至少 60s 且尊重更长 Retry-After；503 按
  Retry-After；5xx/超时有界退避+抖动，同一不可变事件原 ID 原字节。
- 重签必须等时钟真实跨秒，不人为 +1 绕防重放。
- Transport 可注入：本地一律 FakeTransport；真实 HTTP 仅在明确联调批准下
  由生产实现提供，本模块不内置任何生产 URL 调用。
- 请求绝不携带 receivers；metadata 白名单 ≤32 键；不含患者/SQL/secret。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, Protocol

from app.services.reporting_pipeline.contracts import ContractViolation

PATH_POST = "/api/v2/events"
PATH_GET_TEMPLATE = "/api/v2/events/{relay_event_id}"

METADATA_ALLOWLIST = frozenset({
    "system", "environment", "canonical_table", "source_group", "stage",
    "business_date", "batch_id", "incident_id", "error_class", "error_code",
    "affected_count", "task_status", "ticket_ref", "deadline", "detail_ref",
    "recommended_action",
})
PAYLOAD_TOP_KEYS = frozenset({
    "source_event_id", "event_type", "category", "severity", "title", "body",
    "occurred_at", "metadata",
})
METADATA_MAX_KEYS = 32
SOURCE_EVENT_ID_MAX = 200
MIN_RETRY_AFTER_429 = 60


class AlertConfigError(ContractViolation):
    """告警配置/载荷违反契约（未登记源、越白名单、含 receivers 等）。"""


class ClockStalled(ContractViolation):
    """时钟未跨秒且等待预算耗尽：宁可失败也不伪造时间戳。"""


@dataclass
class TransportResponse:
    status_code: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


class Transport(Protocol):
    def post(
        self, url: str, headers: dict[str, str], body: bytes, *, timeout_seconds: float
    ) -> TransportResponse: ...

    def get(self, url: str, headers: dict[str, str], *, timeout_seconds: float) -> TransportResponse: ...


class TransportUnavailable(Exception):
    """传输层不可达/超时（DNS、连接拒绝、读超时等）。

    客户端把它映射为 RETRY_SCHEDULED（有界退避），不当作送达或永久失败；
    调用方不得把异常文本（可能含内部主机名）写进告警正文。
    """


class UrllibTransport:
    """真实 HTTP transport（R06）：urllib 实现，连接/读超时落在 socket 上。

    - 仅在显式提供 base_url 的生产装配中实例化；本模块不含任何生产 URL。
    - 不在 transport 内重试：重试节奏由 outbox sender 的退避与轮询预算
      控制，避免双层重试放大。
    - 超时同时约束连接和单次读；阻塞读被超时打断后连接被关闭。
    """

    def post(
        self, url: str, headers: dict[str, str], body: bytes, *, timeout_seconds: float
    ) -> TransportResponse:
        return self._call("POST", url, headers, body, timeout_seconds)

    def get(
        self, url: str, headers: dict[str, str], *, timeout_seconds: float
    ) -> TransportResponse:
        return self._call("GET", url, headers, None, timeout_seconds)

    def _call(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> TransportResponse:
        import urllib.error
        import urllib.request

        request = urllib.request.Request(url, data=body, method=method)
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return TransportResponse(
                    status_code=response.status,
                    body=response.read(),
                    headers={k: v for k, v in response.headers.items()},
                )
        except urllib.error.HTTPError as exc:
            # HTTPError 也是响应：保留状态码/头/体供分型（401/429/409 等）
            return TransportResponse(
                status_code=exc.code,
                body=exc.read() if exc.fp else b"",
                headers={k: v for k, v in (exc.headers or {}).items()},
            )
        except Exception as exc:  # noqa: BLE001 - DNS/拒绝/超时统一映射不可达
            raise TransportUnavailable(type(exc).__name__) from exc


def now_unix_seconds() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def build_event_body(
    *,
    source_event_id: str,
    event_type: str,
    category: str,
    severity: str,
    title: str,
    body: str,
    occurred_at: str,
    metadata: Mapping[str, object],
) -> bytes:
    """构造并冻结请求字节：顶层键白名单、metadata 白名单≤32、无 receivers。"""
    if len(source_event_id) > SOURCE_EVENT_ID_MAX or not source_event_id:
        raise AlertConfigError("source_event_id 长度非法（1..200）")
    extra = set(metadata) - METADATA_ALLOWLIST
    if extra:
        raise AlertConfigError(f"metadata 越白名单: {sorted(extra)}")
    if len(metadata) > METADATA_MAX_KEYS:
        raise AlertConfigError(f"metadata 超 {METADATA_MAX_KEYS} 键")
    payload = {
        "source_event_id": source_event_id,
        "event_type": event_type,
        "category": category,
        "severity": severity,
        "title": title,
        "body": body,
        "occurred_at": occurred_at,
        "metadata": dict(metadata),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sign_headers(
    *, source_id: str, secret: bytes, unix_ts: int, body: bytes
) -> dict[str, str]:
    signed = (
        source_id.encode("utf-8") + b"." + str(unix_ts).encode("ascii") + b"." + body
    )
    digest = hmac.new(secret, signed, hashlib.sha256).hexdigest()
    return {
        "X-Source-Id": source_id,
        "X-Timestamp": str(unix_ts),
        "X-Signature": digest,
        "Content-Type": "application/json",
    }


@dataclass
class SendOutcome:
    acceptance_state: str  # ACK_QUEUED / DUPLICATE / REJECTED_PERMANENT / PAUSED_AUTH / RETRY_SCHEDULED / NEEDS_ATTENTION
    relay_event_id: str | None
    retry_after_seconds: int | None
    http_code: int | None
    error_class: str | None


@dataclass
class PollOutcome:
    delivery_state: str  # DELIVERED / PARTIAL / ROUTE_UNRESOLVED / PENDING / NEEDS_ATTENTION / PAUSED_AUTH / RETRY_SCHEDULED
    target_status_summary: dict
    http_code: int | None = None


@dataclass
class RelayConfig:
    base_url: str
    source_id: str
    secret_ref: str
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 10.0
    max_attempts: int = 5
    max_backlog_seconds: int = 3600


class RelayV2Client:
    """v2 客户端：只与注入 Transport 交互；未注册源/密钥时拒绝发送。"""

    def __init__(
        self,
        transport: Transport,
        config: RelayConfig,
        *,
        secret_resolver: Callable[[str], bytes],
        clock: Callable[[], int] = now_unix_seconds,
        sleep_fn: Callable[[float], None] | None = None,
        jitter_seed: int = 20261019,
    ) -> None:
        self.transport = transport
        self.config = config
        self._secret_resolver = secret_resolver
        self._clock = clock
        self._sleep = sleep_fn or (lambda s: None)
        self._rng = random.Random(jitter_seed)
        self._last_ts: dict[str, int] = {}

    # -- POST ---------------------------------------------------------------

    def send_event(
        self, *, source_event_id: str, body_bytes: bytes, previous_attempts: int = 0
    ) -> SendOutcome:
        if not self.config.source_id or not self.config.secret_ref:
            raise AlertConfigError(
                "告警源未登记（source_id/secret_ref 缺失，WAITING_INTEGRATION_SETUP）"
            )
        if previous_attempts >= self.config.max_attempts:
            return SendOutcome(
                acceptance_state="RETRY_SCHEDULED",
                relay_event_id=None, retry_after_seconds=None,
                http_code=None, error_class="MAX_ATTEMPTS_EXHAUSTED",
            )
        secret = self._secret_resolver(self.config.secret_ref)
        ts = self._await_new_second(source_event_id)
        headers = sign_headers(
            source_id=self.config.source_id,
            secret=secret,
            unix_ts=ts,
            body=body_bytes,
        )
        try:
            response = self.transport.post(
                self.config.base_url + PATH_POST, headers, body_bytes,
                timeout_seconds=self.config.read_timeout_seconds,
            )
        except TransportUnavailable:
            # 抽取不等告警 HTTP 返回；不可达 → 有界退避，outbox 留存重试
            return SendOutcome(
                "RETRY_SCHEDULED", None, self._bounded_backoff(), None,
                "TRANSPORT_UNAVAILABLE",
            )
        return self._classify_post(response)

    def _classify_post(self, response: TransportResponse) -> SendOutcome:
        code = response.status_code
        if code == 202:
            relay_id = self._extract_relay_event_id(response.body)
            return SendOutcome("ACK_QUEUED", relay_id, None, code, None)
        if code == 200:
            relay_id = self._extract_relay_event_id(response.body)
            return SendOutcome("DUPLICATE", relay_id, None, code, None)
        if code == 401:
            # 停通道自动重试：避免触发源锁定；记录待核凭据/时钟
            return SendOutcome("PAUSED_AUTH", None, None, code, "AUTH_FAILED")
        if code in (400, 422):
            return SendOutcome("REJECTED_PERMANENT", None, None, code, "PAYLOAD_INVALID")
        if code == 409:
            return SendOutcome(
                "NEEDS_ATTENTION", None, None, code, "CONFLICT_CLASSIFY_REPLAY_OR_CONTENT",
            )
        if code == 429:
            retry_after = max(
                MIN_RETRY_AFTER_429,
                _parse_retry_after(response.headers.get("Retry-After")),
            )
            return SendOutcome("RETRY_SCHEDULED", None, retry_after, code, "RATE_LIMITED")
        if code == 503:
            retry_after = _parse_retry_after(response.headers.get("Retry-After")) or 60
            return SendOutcome("RETRY_SCHEDULED", None, retry_after, code, "SERVICE_UNAVAILABLE")
        if code >= 500:
            backoff = self._bounded_backoff()
            return SendOutcome("RETRY_SCHEDULED", None, backoff, code, "SERVER_ERROR")
        return SendOutcome("NEEDS_ATTENTION", None, None, code, "UNEXPECTED_STATUS")

    def _bounded_backoff(self) -> int:
        # 指数退避 + 抖动，受总积压预算约束
        base = min(60 * (2 ** min(self.config.max_attempts, 5)), self.config.max_backlog_seconds)
        return int(base * (1 + self._rng.uniform(0, 0.3)))

    # -- GET（空 body 签名，按响应 event_id 查询） ---------------------------

    def poll_event(self, *, relay_event_id: str, source_event_id: str) -> PollOutcome:
        secret = self._secret_resolver(self.config.secret_ref)
        ts = self._await_new_second(f"get:{relay_event_id}")
        headers = sign_headers(
            source_id=self.config.source_id, secret=secret,
            unix_ts=ts, body=b"",
        )
        url = self.config.base_url + PATH_GET_TEMPLATE.format(relay_event_id=relay_event_id)
        try:
            response = self.transport.get(
                url, headers, timeout_seconds=self.config.read_timeout_seconds
            )
        except TransportUnavailable:
            return PollOutcome(
                "RETRY_SCHEDULED", {"retry_after": 60}, None
            )
        if response.status_code == 401:
            return PollOutcome("PAUSED_AUTH", {}, 401)
        if response.status_code == 404:
            return PollOutcome(
                "NEEDS_ATTENTION", {"note": "GET 404：核源身份/UUID/部署差异"}, 404
            )
        if response.status_code == 429:
            retry_after = max(
                MIN_RETRY_AFTER_429,
                _parse_retry_after(response.headers.get("Retry-After")),
            )
            return PollOutcome("RETRY_SCHEDULED", {"retry_after": retry_after}, 429)
        if response.status_code != 200:
            return PollOutcome("RETRY_SCHEDULED", {}, response.status_code)
        try:
            document = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return PollOutcome("NEEDS_ATTENTION", {"note": "响应非 JSON"}, 200)
        targets = document.get("tasks") or []
        return _evaluate_targets(targets)

    # -- 时钟 ---------------------------------------------------------------

    def _await_new_second(self, key: str) -> int:
        """重签必须等真实跨秒；不 +1 伪造。等待预算 2.5s，超时拒绝发送。"""
        ts = self._clock()
        last = self._last_ts.get(key)
        if last is not None and ts <= last:
            waited = 0.0
            while ts <= last and waited < 2.5:
                self._sleep(0.1)
                waited += 0.1
                ts = self._clock()
            if ts <= last:
                raise ClockStalled(
                    f"时钟未跨秒（key={key}）：拒绝伪造时间戳重签"
                )
        self._last_ts[key] = ts
        return ts

    @staticmethod
    def _extract_relay_event_id(body: bytes) -> str | None:
        try:
            document = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        for key in ("event_id", "id", "uuid"):
            value = document.get(key)
            if isinstance(value, str):
                return value
        return None


def _evaluate_targets(targets: list) -> PollOutcome:
    """逐目标判定：全部 sent 且无不确定才 DELIVERED；零目标=ROUTE_UNRESOLVED。

    pending/processing 是正常中间态（按轮询预算继续等）；needs_attention/
    outcome_uncertain/dead/cancelled/failed 才升级待人工。
    """
    if not targets:
        return PollOutcome("ROUTE_UNRESOLVED", {"targets": 0})
    summary: dict[str, int] = {}
    attention_states = {
        "needs_attention", "outcome_uncertain", "dead", "cancelled", "failed",
    }
    wait_states = {"pending", "processing"}
    all_sent = True
    needs_attention = False
    still_waiting = False
    for target in targets:
        state = str(target.get("status", "unknown"))
        summary[state] = summary.get(state, 0) + 1
        if state != "sent":
            all_sent = False
        if state in attention_states:
            needs_attention = True
        if state in wait_states:
            still_waiting = True
    if all_sent and not needs_attention:
        return PollOutcome("DELIVERED", summary)
    if needs_attention:
        return PollOutcome("NEEDS_ATTENTION", summary)
    if still_waiting:
        return PollOutcome("PENDING", summary)
    return PollOutcome("NEEDS_ATTENTION", summary)


def _parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def verify_payload_privacy(body_bytes: bytes) -> dict:
    """结构级隐私自检：顶层键白名单、无 receivers、无凭据样键。"""
    try:
        document = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "problems": [f"非JSON: {exc!r}"]}
    problems: list[str] = []
    if "receivers" in document:
        problems.append("请求含 receivers 字段（收件人只由 relay 订阅决定）")
    extra = set(document) - PAYLOAD_TOP_KEYS
    if extra:
        problems.append(f"顶层键越白名单: {sorted(extra)}")
    metadata = document.get("metadata") or {}
    if len(metadata) > METADATA_MAX_KEYS:
        problems.append(f"metadata 超 {METADATA_MAX_KEYS} 键")
    meta_extra = set(metadata) - METADATA_ALLOWLIST
    if meta_extra:
        problems.append(f"metadata 越白名单: {sorted(meta_extra)}")
    for banned in ("password", "secret", "token", "sql"):
        if banned in json.dumps(document).lower():
            problems.append(f"载荷疑似包含 {banned} 字段")
    return {"ok": not problems, "problems": problems}
