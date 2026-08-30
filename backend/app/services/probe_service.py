"""165 E1: 探查发现服务层——只写 open/观测/relapse，无任何终态写入路径。

165 §1 铁律 4：confirmed/false_positive/resolved 仅人工（166 transition）。
本模块不得提供任何写终态的函数；单测以源码断言锁死。

两键语义（round-4 A1）：
  - 幂等键 = 问题身份四元组 (probe_type, system_pair, object_key_digest, metric_name)
    （不含 window）+ 同 window_start → 仅更新 metric_value/evidence_digest，不动 status；
  - 新窗重跑命中既有行 → 更新观测（metric_value/window/last_seen_run）并做复发判定：
    resolved → open 且 relapse_count+1；confirmed → 保持且 note 追加；false_positive → 不动。
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.probe import AssetProbeFinding, AssetProbeRun

# 服务层禁止写入的状态值（终态归人工，166 F5 transition）
_TERMINAL_STATUSES = {"confirmed", "false_positive", "resolved"}
FORBIDDEN_TOKENS = (
    'status = "confirmed"',
    "status = 'confirmed'",
    'status = "resolved"',
    "status = 'resolved'",
    'status = "false_positive"',
    "status = 'false_positive'",
)


def object_digest(object_desc: str) -> str:
    """问题身份摘要：sha256(object_desc) 前 32 hex（A1，防 btree 超限）。"""
    return hashlib.sha256(object_desc.encode("utf-8")).hexdigest()[:32]


def evidence_digest(sql_text: str, window_start: date, window_end: date) -> str:
    """规范化 SQL + 参数窗的摘要（漂移检测用）。"""
    norm = " ".join((sql_text or "").split())
    return hashlib.sha256(f"{norm}|{window_start}|{window_end}".encode("utf-8")).hexdigest()


def find_finding(
    db: Session,
    *,
    probe_type: str,
    system_pair: str,
    object_key_digest: str,
    metric_name: str,
) -> AssetProbeFinding | None:
    return db.scalar(
        select(AssetProbeFinding).where(
            AssetProbeFinding.probe_type == probe_type,
            AssetProbeFinding.system_pair == system_pair,
            AssetProbeFinding.object_key_digest == object_key_digest,
            AssetProbeFinding.metric_name == metric_name,
        )
    )


def upsert_finding(
    db: Session,
    *,
    run_id: str,
    probe_type: str,
    system_pair: str,
    object_desc: str,
    metric_name: str,
    metric_value: float,
    metric_unit: str,
    threshold: float,
    window_start: date,
    window_end: date,
    severity: str,
    evidence_sql: str,
    note: str | None = None,
) -> dict[str, Any]:
    """越阈事实入库。返回 {"outcome": created|same_window_updated|new_window_updated|false_positive_skipped, "relapse": bool}。

    165 §1 铁律 2：evidence_sql 必须为模板文本（无 ID/住院号/姓名字面量）；
    执行器（run_probe.py）负责保证，本函数做最后防线校验。
    """
    if any(t in (evidence_sql or "") for t in FORBIDDEN_TOKENS):
        raise ValueError("evidence_sql 终态字面量非法（服务层无终态写入）")

    digest = object_digest(object_desc)
    ev_digest = evidence_digest(evidence_sql, window_start, window_end)
    existing = find_finding(
        db,
        probe_type=probe_type,
        system_pair=system_pair,
        object_key_digest=digest,
        metric_name=metric_name,
    )
    now = datetime.now(timezone.utc)

    if existing is None:
        row = AssetProbeFinding(
            probe_type=probe_type,
            system_pair=system_pair,
            object_desc=object_desc,
            object_key_digest=digest,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            threshold=threshold,
            window_start=window_start,
            window_end=window_end,
            severity=severity,
            status="open",
            first_seen_run=run_id,
            last_seen_run=run_id,
            relapse_count=0,
            evidence_sql=evidence_sql,
            evidence_digest=ev_digest,
            note=note,
        )
        db.add(row)
        db.flush()
        return {"outcome": "created", "relapse": False, "id": row.id}

    # false_positive：防噪音，不动（A1 裁决）
    if existing.status == "false_positive":
        return {"outcome": "false_positive_skipped", "relapse": False, "id": existing.id}

    same_window = existing.window_start == window_start
    if same_window:
        # 同窗重跑：仅更新观测值与摘要，不动 status
        existing.metric_value = metric_value
        existing.evidence_digest = ev_digest
        existing.last_seen_run = run_id
        existing.updated_at = now
        db.flush()
        return {"outcome": "same_window_updated", "relapse": False, "id": existing.id}

    # 新窗重跑：更新观测 + 复发判定
    relapse = False
    if existing.status == "resolved":
        existing.status = "open"
        existing.relapse_count = (existing.relapse_count or 0) + 1
        existing.resolved_by = None
        existing.resolved_at = None
        relapse = True
    elif existing.status == "confirmed":
        extra = f"[{run_id}] 新窗仍越阈（{metric_value}{metric_unit}）"
        existing.note = f"{existing.note}；{extra}" if existing.note else extra

    existing.metric_value = metric_value
    existing.window_start = window_start
    existing.window_end = window_end
    existing.severity = severity
    existing.last_seen_run = run_id
    existing.evidence_sql = evidence_sql
    existing.evidence_digest = ev_digest
    existing.updated_at = now
    db.flush()
    return {"outcome": "new_window_updated", "relapse": relapse, "id": existing.id}


def register_run(
    db: Session,
    *,
    run_id: str,
    started_at: datetime | None = None,
    status: str = "running",
    created_by: str | None = None,
) -> AssetProbeRun:
    """登记 run 行（执行器创建→done/partial/blocked 收尾均由 update_run 完成）。"""
    row = AssetProbeRun(
        run_id=run_id,
        started_at=started_at or datetime.now(timezone.utc),
        status=status,
        created_by=created_by or f"probe:{run_id}",
    )
    db.add(row)
    db.flush()
    return row


def update_run(
    db: Session,
    *,
    run_id: str,
    status: str,
    probe_count: int = 0,
    finding_new: int = 0,
    finding_updated: int = 0,
    relapse_count: int = 0,
    metrics_summary: dict[str, Any] | None = None,
    error_summary: str | None = None,
) -> AssetProbeRun | None:
    """收尾 run（状态机 running→done/partial/blocked；不触终态语义——runs 无人工终态）。"""
    row = db.scalar(select(AssetProbeRun).where(AssetProbeRun.run_id == run_id))
    if row is None:
        return None
    row.status = status
    row.finished_at = datetime.now(timezone.utc)
    row.probe_count = probe_count
    row.finding_new = finding_new
    row.finding_updated = finding_updated
    row.relapse_count = relapse_count
    if metrics_summary is not None:
        row.metrics_summary = metrics_summary
    if error_summary is not None:
        row.error_summary = error_summary
    db.flush()
    return row


# ─────────────────────────────────────────────────────────────────────────
# 166 F5：人工终态流转（只增不改——165 既有函数不触碰）
#
# B6 迁移表（人工四值互转+重开全允许，仅禁同态原地转）：
#   from\to      open   confirmed   false_positive   resolved
#   open          —        ✓             ✓              ✓
#   confirmed     ✓        —             ✓              ✓
#   false_positive ✓       ✓             —              ✓
#   resolved      ✓        ✓             ✓              —
#
# 执行器身份（created_by/user 前缀 "probe:"）禁止调用（路由层 403）；
# 165 复发机制（resolved→open 由新窗观测驱动）独立于本函数，不冲突。
# ─────────────────────────────────────────────────────────────────────────

FINDING_TERMINAL_STATUSES = ("confirmed", "false_positive", "resolved")
FINDING_ALL_STATUSES = ("open", *FINDING_TERMINAL_STATUSES)


class FindingTransitionError(Exception):
    """非法流转（终态值非法/同态原地转）。路由层映射 422。"""


def finding_transition_allowed(from_status: str, to_status: str) -> bool:
    """人工四值互转+重开全允许；同态原地转非法（B6 表 12 条合法迁移）。"""
    if from_status not in FINDING_ALL_STATUSES or to_status not in FINDING_ALL_STATUSES:
        return False
    return from_status != to_status


def transition_finding(
    db: Session,
    *,
    finding_id: int,
    to_status: str,
    reason: str,
    operator: str,
) -> AssetProbeFinding:
    """人工终态流转（166 F5）。reason 必填由路由层校验；此处只做状态机。

    resolved_by/resolved_at 快照：转 resolved 记录操作人/时间；
    离开 resolved（重开/改判）清空快照（与 165 复发清空口径一致）。
    """
    row = db.get(AssetProbeFinding, finding_id)
    if row is None:
        raise LookupError(f"finding {finding_id} not found")
    if to_status not in FINDING_ALL_STATUSES:
        raise FindingTransitionError(f"终态值非法: {to_status}")
    if not finding_transition_allowed(row.status, to_status):
        raise FindingTransitionError(f"不允许的迁移: {row.status} -> {to_status}（同态原地转非法）")

    row.status = to_status
    if to_status == "resolved":
        row.resolved_by = operator
        row.resolved_at = datetime.now(timezone.utc)
    else:
        row.resolved_by = None
        row.resolved_at = None
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return row
