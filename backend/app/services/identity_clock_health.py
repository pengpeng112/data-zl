"""186 v1.10 §13.2：目标数据库时间合同与有界偏差采样（只读）。

不修改两目标主机/数据库时间；只从 8.83 对 JHEMR（Vastbase）与 CDMS
（Oracle）做有界往返采样，建立"目标时间相对平台时钟的偏差区间 +
合同（字段类型/会话时区/写入表达式/证据时间）"。

工程默认（settings）：样本≤3、单次超时 5s、RTT 上限 2s、健康 TTL 300s。

关键语义（§13.1/§13.3）：
- 偏差估计 T-(t0+t1)/2 的误差区间至少含 RTT/2 与目标量化误差；不假设
  网络对称，多次采样区间不相容 → unstable，不强行平均。
- UTC 换算仅用于审计排列；时间接近/稳定不能证明锁所有权，enable 门禁
  还需 §13.3 的所有权证据（当前两目标无审计/版本合同 →
  automatic_enable_supported=False）。
- raw 值原样留存并标注类型，不猜 PRC/UTC、不给 naive 值强贴时区。
- 偏差绝对值大但稳定 → 告警，不修改目标时间、不扩大容差。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ..core.config import settings

# 目标侧目前没有可证明锁所有权的审计/版本/锁原因合同（§13.3-3/-5）。
# 该常量为 False 时自动 enable 一律不可放行——即使三台时钟完全一致。
AUTOMATIC_ENABLE_SUPPORTED = False
AUTOMATIC_ENABLE_UNSUPPORTED_REASONS = [
    "jhemr_users_has_no_lock_reason_or_version_column",
    "cdms_t_mss_emp_dict_has_no_lock_reason_or_version_column",
    "no_target_audit_contract_covers_repeat_lock_or_same_second_relock",
]


@dataclass
class TargetClockSample:
    """One bounded round-trip sample against one target database."""

    source_code: str
    sample_index: int
    t0_utc: str
    t1_utc: str
    rtt_s: float
    target_time_raw: str | None
    target_time_type: str | None  # e.g. "oracle DATE(s)" / "pg timestamptz text"
    session_timezone: str | None
    db_timezone: str | None
    offset_s: float | None
    error_bound_s: float | None
    valid: bool
    error: str | None = None


@dataclass
class TargetClockContract:
    """Per-target serialization contract (§13.2)。"""

    source_code: str
    db_product: str
    time_expression: str  # e.g. SYSDATE / clock_timestamp()
    field_types: dict[str, str] = field(default_factory=dict)
    session_timezone: str | None = None
    db_timezone: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ClockHealth:
    """Aggregated health over one sampling round."""

    healthy: bool
    reasons: list[str] = field(default_factory=list)
    samples: dict[str, list[TargetClockSample]] = field(default_factory=dict)
    contracts: dict[str, TargetClockContract] = field(default_factory=dict)
    offsets: dict[str, dict[str, float | None]] = field(default_factory=dict)
    evaluated_at: str | None = None
    ttl_expires_at_monotonic: float | None = None
    automatic_enable_supported: bool = AUTOMATIC_ENABLE_SUPPORTED
    automatic_enable_unsupported_reasons: list[str] = field(
        default_factory=lambda: list(AUTOMATIC_ENABLE_UNSUPPORTED_REASONS)
    )

    def to_report(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "reasons": self.reasons,
            "evaluated_at": self.evaluated_at,
            "automatic_enable_supported": self.automatic_enable_supported,
            "automatic_enable_unsupported_reasons": self.automatic_enable_unsupported_reasons,
            "targets": {
                code: {
                    "offset_min_s": data.get("min"),
                    "offset_max_s": data.get("max"),
                    "stable": data.get("stable"),
                    "contract": {
                        "db_product": self.contracts[code].db_product,
                        "time_expression": self.contracts[code].time_expression,
                        "field_types": self.contracts[code].field_types,
                        "session_timezone": self.contracts[code].session_timezone,
                        "db_timezone": self.contracts[code].db_timezone,
                        "notes": self.contracts[code].notes,
                    } if code in self.contracts else None,
                    "samples": [
                        {
                            "t0_utc": s.t0_utc,
                            "t1_utc": s.t1_utc,
                            "rtt_s": round(s.rtt_s, 4),
                            "target_time_raw": s.target_time_raw,
                            "target_time_type": s.target_time_type,
                            "offset_s": None if s.offset_s is None else round(s.offset_s, 4),
                            "error_bound_s": None if s.error_bound_s is None else round(s.error_bound_s, 4),
                            "valid": s.valid,
                            "error": s.error,
                        }
                        for s in self.samples.get(code, [])
                    ],
                }
                for code, data in self.offsets.items()
            },
        }


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_target_time(value: Any) -> datetime | None:
    """Parse the raw server-side time expression result (text/epoch/datetime).

    No timezone is *assumed*: a naive value is treated as target-wall-clock
    and only compared against platform wall-clock for a bounded offset
    estimate; the raw text is always preserved.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    # numeric epoch seconds
    try:
        return datetime.fromtimestamp(float(text), tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        pass
    try:
        parsed = datetime.fromisoformat(text.replace(" ", "T", 1) if "T" not in text[:30] else text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# --- JHEMR (Vastbase; PostgreSQL-reference semantics, must degrade safely) ---

_JHEMR_TIME_SQL = "SELECT clock_timestamp()::text AS ts, current_setting('TimeZone') AS tz"


def sample_jhemr_clock(query_fn: Callable[[str], list[dict[str, Any]]]) -> dict[str, Any] | None:
    """One read-only sample against JHEMR. ``query_fn(sql)`` returns rows.

    Returns None when the expression is unsupported (compat probe failed) —
    caller records an unusable-contract note, never guesses PRC/UTC.
    """
    row = (query_fn(_JHEMR_TIME_SQL) or [{}])[0]
    tz = row.get("tz")
    ts = row.get("ts")
    if ts is None:
        return None
    return {"target_time_raw": str(ts), "session_timezone": tz if tz else None, "db_timezone": None}


# --- CDMS (Oracle 11g) ---

_CDMS_TIME_SQL = "SELECT SYSDATE AS sd, SYSTIMESTAMP AS st, DBTIMEZONE AS dbtz, SESSIONTIMEZONE AS stz FROM DUAL"


def sample_cdms_clock(query_fn: Callable[[str], list[dict[str, Any]]]) -> dict[str, Any] | None:
    row = (query_fn(_CDMS_TIME_SQL) or [{}])[0]
    sd, st = row.get("sd"), row.get("st")
    if sd is None and st is None:
        return None
    # Prefer SYSTIMESTAMP (带 DB 时区偏移，量化到微秒)；SYSDATE 为秒级 DATE。
    raw = st if st is not None else sd
    return {
        "target_time_raw": str(raw),
        "target_time_type": "oracle SYSTIMESTAMP" if st is not None else "oracle DATE (second precision)",
        "session_timezone": row.get("stz"),
        "db_timezone": row.get("dbtz"),
    }


def _offset_interval(samples: list[TargetClockSample]) -> dict[str, float | None]:
    """Aggregate per-target offset interval; incompatible intervals → unstable."""
    valid = [s for s in samples if s.valid and s.offset_s is not None and s.error_bound_s is not None]
    if not valid:
        return {"min": None, "max": None, "stable": False}
    lo = max(s.offset_s - s.error_bound_s for s in valid)
    hi = min(s.offset_s + s.error_bound_s for s in valid)
    stable = lo <= hi  # intervals intersect
    return {"min": round(lo, 4), "max": round(hi, 4), "stable": bool(stable)}


def evaluate_clock_health(
    *,
    jhemr_query: Callable[[str], list[dict[str, Any]]] | None,
    cdms_query: Callable[[str], list[dict[str, Any]]] | None,
    monotonic: Callable[[], float] = time.monotonic,
) -> ClockHealth:
    """Bounded serial sampling of both targets; read-only, never throws.

    ``*_query`` None → target skipped (reason recorded); query raising →
    sample invalid, health degrades (fail-closed for enable, not for report).
    """
    health = ClockHealth(healthy=False)
    health.evaluated_at = _now_utc_iso()
    health.ttl_expires_at_monotonic = monotonic() + settings.identity_clock_health_ttl_s
    reasons: list[str] = []

    plan = (
        ("JHEMR", jhemr_query, sample_jhemr_clock, "vastbase"),
        ("CDMS", cdms_query, sample_cdms_clock, "oracle"),
    )
    for code, query_fn, sampler, product in plan:
        if query_fn is None:
            reasons.append(f"{code}:not_sampled")
            continue
        samples: list[TargetClockSample] = []
        contract_notes: list[str] = []
        for index in range(max(1, settings.identity_clock_samples)):
            t0 = datetime.now(timezone.utc)
            m0 = monotonic()
            raw_info = None
            error = None
            try:
                raw_info = sampler(query_fn)
                if raw_info is None:
                    error = "time_expression_unsupported"
            except Exception as exc:  # noqa: BLE001 — sampling must degrade, never crash the run
                error = f"{type(exc).__name__}: {str(exc)[:120]}"
            m1 = monotonic()
            t1 = datetime.now(timezone.utc)
            rtt_s = max(0.0, m1 - m0)
            sample = TargetClockSample(
                source_code=code,
                sample_index=index,
                t0_utc=t0.isoformat(),
                t1_utc=t1.isoformat(),
                rtt_s=rtt_s,
                target_time_raw=(raw_info or {}).get("target_time_raw"),
                target_time_type=(raw_info or {}).get("target_time_type"),
                session_timezone=(raw_info or {}).get("session_timezone"),
                db_timezone=(raw_info or {}).get("db_timezone"),
                offset_s=None,
                error_bound_s=None,
                valid=False,
                error=error,
            )
            if error is None and sample.target_time_raw is not None:
                target_dt = _parse_target_time(sample.target_time_raw)
                if target_dt is None:
                    sample.error = "target_time_unparseable"
                elif rtt_s > settings.identity_clock_max_rtt_s:
                    sample.error = "rtt_exceeded"
                else:
                    mid = t0 + (t1 - t0) / 2
                    sample.offset_s = (target_dt - mid).total_seconds()
                    # 误差区间 ≥ RTT/2 + 目标量化误差(1s for DATE) + 平台时钟未知项
                    quantization = 1.0 if sample.target_time_type and "DATE" in sample.target_time_type else 0.001
                    sample.error_bound_s = rtt_s / 2 + quantization
                    sample.valid = True
            samples.append(sample)
        health.samples[code] = samples
        valid_samples = [s for s in samples if s.valid]
        tz_values = {s.session_timezone for s in valid_samples if s.session_timezone}
        health.contracts[code] = TargetClockContract(
            source_code=code,
            db_product=product,
            time_expression="clock_timestamp()" if code == "JHEMR" else "SYSDATE/SYSTIMESTAMP",
            field_types={"time_column": "text (session tz)" if code == "JHEMR" else "DATE / TIMESTAMP WITH TIME ZONE"},
            session_timezone=next(iter(tz_values)) if len(tz_values) == 1 else None,
            db_timezone=next(iter({s.db_timezone for s in valid_samples if s.db_timezone}), None),
            notes=contract_notes,
        )
        interval = _offset_interval(samples)
        health.offsets[code] = interval
        if not valid_samples:
            reasons.append(f"{code}:no_valid_sample")
        elif not interval.get("stable"):
            reasons.append(f"{code}:offset_intervals_incompatible")
        else:
            span = (interval.get("max") or 0) - (interval.get("min") or 0)
            if abs(interval.get("min") or 0) > 600 or abs(interval.get("max") or 0) > 600:
                # 大偏差但稳定：只告警，不修改目标时间、不放行 enable。
                reasons.append(f"{code}:large_but_stable_offset")
        if any(s.error == "time_expression_unsupported" for s in samples):
            reasons.append(f"{code}:time_contract_unverified")

    health.reasons = reasons
    health.healthy = not any(
        r.endswith(":no_valid_sample") or r.endswith(":offset_intervals_incompatible") or r.endswith(":not_sampled")
        or r.endswith(":time_contract_unverified")
        for r in reasons
    )
    return health


def clock_health_allows_enable(health: ClockHealth | None) -> tuple[bool, list[str]]:
    """§13.2：enable 的时钟前置。健康缺失/过期/不健康 → 关闭。

    即使 healthy，锁所有权仍由 automatic_enable_supported 与执行器注册
    决定；本函数只是必要条件之一。
    """
    if health is None:
        return False, ["clock_health_missing"]
    reasons: list[str] = []
    if health.ttl_expires_at_monotonic is not None and time.monotonic() > health.ttl_expires_at_monotonic:
        reasons.append("clock_health_expired")
    if not health.healthy:
        reasons.extend(health.reasons or ["clock_health_unhealthy"])
    if not health.automatic_enable_supported:
        reasons.extend(health.automatic_enable_unsupported_reasons)
    return (not reasons), reasons


def _adapter_query_builder(target: str) -> Callable[[str], list[dict[str, Any]]] | None:
    """Build a bounded read-only query fn on the real target adapter (§13.2).

    生产夜跑采样用。连接串/凭据沿用既有身份适配器配置；查询只读、
    单行、失败即抛（由 evaluate_clock_health 降级），不做任何写操作。
    """
    if target == "JHEMR":
        from .jhemr_identity_adapter import JhemrIdentityAdapter

        def _q(sql: str) -> list[dict[str, Any]]:
            adapter = JhemrIdentityAdapter(
                credential_ref=settings.identity_sync_jhemr_credential_ref,
                hospital_no=settings.identity_sync_jhemr_hospital_no,
                jump_host=settings.his_source_jump_host,
                jump_port=settings.his_source_jump_port,
                jump_user=settings.his_source_jump_user,
                jump_key=settings.his_source_jump_key or None,
                db_host=settings.identity_sync_jhemr_host,
                db_port=settings.identity_sync_jhemr_port,
                db_name=settings.identity_sync_jhemr_dbname,
            )
            try:
                adapter.connect()
                # 2026-09-10 晨检修复：_fetch_one 需要 (sql, params) 双参；
                # 缺参会 TypeError → JHEMR 采样恒 no_valid_sample。
                return [adapter._fetch_one(sql, None)] if sql else []
            finally:
                adapter.close()

        return _q
    if target == "CDMS":
        from .cdms_identity_adapter import CdmsIdentityAdapter

        def _q(sql: str) -> list[dict[str, Any]]:
            adapter = CdmsIdentityAdapter(
                credential_ref=settings.identity_sync_cdms_credential_ref,
                cdms_host=settings.identity_sync_cdms_host,
                cdms_port=settings.identity_sync_cdms_port,
                cdms_service=settings.identity_sync_cdms_service,
                jump_host=settings.his_source_jump_host,
                jump_port=settings.his_source_jump_port,
                jump_user=settings.his_source_jump_user,
                jump_key=settings.his_source_jump_key or None,
                oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
            )
            try:
                adapter.connect()
                cursor = adapter._require_conn().cursor()
                try:
                    cursor.execute(sql)
                    cols = [c[0].lower() for c in cursor.description] if cursor.description else []
                    row = cursor.fetchone()
                    return [dict(zip(cols, row))] if row and cols else []
                finally:
                    cursor.close()
            finally:
                adapter.close()

        return _q
    return None
