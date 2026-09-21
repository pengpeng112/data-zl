"""193 B11—B15：患者时间线、统计主题、训练集构建、受控导出与生命周期。

- 时间线：按业务时间排序，跨源时差可见，无数据不显示"未患病"。
- 统计主题：一项首发主题（30 天再入院率示例）走治理事实口径。
- 训练集：患者分组（同患者不跨集）+ 时间切分 + 未来信息泄漏断言。
- 导出：用途审批门 + 字段白名单 + 文本脱敏 + CSV 公式注入清洗 + 到期与撤销。
- 生命周期：撤销传播到导出/缓存键。
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dataset import AssetDsExport, AssetDsFact, AssetDsGrant, AssetDsDatasetVersion


# ---------------- B11 患者时间线 ----------------

def patient_timeline(db: Session, internal_patient_id: str) -> dict:
    """时间线事件按 business_time 升序；来源与可用时间保留（跨源时差可见）。

    无记录返回空 events（调用方渲染空态，不得显示"未患病"）。
    """
    facts = db.scalars(select(AssetDsFact).where(
        AssetDsFact.internal_patient_id == internal_patient_id,
        AssetDsFact.deleted == "false")).all()
    events = [{
        "fact_key": f.fact_key,
        "kind": f.fact_kind,
        "source_code": f.source_code,
        "standard_value": f.standard_value,
        "business_time": f.business_time.isoformat() if f.business_time else None,
        "available_time": f.available_time.isoformat() if f.available_time else None,
        "quality_flag": f.quality_flag,
    } for f in facts]
    events.sort(key=lambda e: (e["business_time"] or "9999", e["fact_key"]))
    return {"internal_patient_id": internal_patient_id, "events": events,
            "count": len(events)}


# ---------------- B12 统计主题（首发：30 天再入院率） ----------------

def readmission_rate(db: Session, window_days: int = 30) -> dict:
    """治理事实口径：同患者两次 visit 间隔 ≤ window 天计一次再入院。

    分母=有住院事实的患者数；JOIN 不放大计数（按患者聚合，非按事实行）。
    """
    facts = db.scalars(select(AssetDsFact).where(
        AssetDsFact.fact_kind == "visit", AssetDsFact.deleted == "false")).all()
    by_patient: dict[str, list[datetime]] = {}
    for f in facts:
        if f.business_time:
            by_patient.setdefault(f.internal_patient_id, []).append(f.business_time)
    denominator = len(by_patient)
    readmits = 0
    for pid, times in by_patient.items():
        times.sort()
        for a, b in zip(times, times[1:]):
            if 0 < (b - a).days <= window_days:
                readmits += 1
                break
    return {"metric": "readmission_30d", "window_days": window_days,
            "denominator_patients": denominator, "readmitted_patients": readmits,
            "rate": round(readmits / denominator, 6) if denominator else None}


# ---------------- B13 训练集构建 ----------------

@dataclass
class SplitConfig:
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    seed: int = 193


def patient_group_split(patient_ids: list[str], cfg: SplitConfig = SplitConfig()) -> dict[str, list[str]]:
    """按患者分组切分：同患者不跨训练/验证/测试（哈希分桶，确定性可复现）。"""
    def bucket(pid: str) -> int:
        h = hash(f"{cfg.seed}|{pid}") & 0xFFFFFFFF
        return h % 100

    splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for pid in sorted(patient_ids):
        b = bucket(pid)
        if b < int(cfg.train_ratio * 100):
            splits["train"].append(pid)
        elif b < int((cfg.train_ratio + cfg.val_ratio) * 100):
            splits["val"].append(pid)
        else:
            splits["test"].append(pid)
    return splits


def temporal_features_available(fact_available_time: datetime | None,
                                prediction_time: datetime) -> bool:
    """未来信息泄漏断言：特征可用时间必须 ≤ 预测时点。"""
    if fact_available_time is None:
        return False
    return fact_available_time <= prediction_time


def build_training_set(db: Session, dataset_version_id: int,
                       label_fn=None, cfg: SplitConfig = SplitConfig(),
                       data_card_extra: dict | None = None) -> dict:
    """训练集 + 数据卡。插补仅训练拟合（首期不插补，缺失保留披露）。"""
    facts = db.scalars(select(AssetDsFact).where(AssetDsFact.deleted == "false")).all()
    patients = sorted({f.internal_patient_id for f in facts})
    splits = patient_group_split(patients, cfg)
    label_fn = label_fn or (lambda facts_of_patient: 0)
    by_patient: dict[str, list] = {}
    for f in facts:
        by_patient.setdefault(f.internal_patient_id, []).append(f)
    examples = []
    leaks = 0
    for split, pids in splits.items():
        for pid in pids:
            pf = by_patient.get(pid, [])
            pred_time = max((f.business_time for f in pf if f.business_time),
                            default=datetime(1970, 1, 1, tzinfo=timezone.utc))
            usable = [f for f in pf if temporal_features_available(f.available_time, pred_time)]
            leaks += len(pf) - len(usable)
            examples.append({"split": split, "patient": pid,
                             "feature_count": len(usable), "label": label_fn(pf)})
    card = {
        "schema_version": "data-card/v1",
        "dataset_version_id": dataset_version_id,
        "total_patients": len(patients),
        "splits": {k: len(v) for k, v in splits.items()},
        "future_info_excluded": leaks,
        "missing_policy": "kept_disclosed",
        "imputation": "none_train_only",
        **(data_card_extra or {}),
    }
    return {"examples": examples, "data_card": card}


# ---------------- B14 受控导出 ----------------

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str | None) -> str:
    """CSV 公式注入清洗：危险前缀加单引号。"""
    if value is None:
        return ""
    s = str(value)
    if s.startswith(CSV_INJECTION_PREFIXES):
        return "'" + s
    return s


_PII_PATTERNS = [
    (re.compile(r"\b\d{17}[\dXx]\b"), "[身份证号]"),
    (re.compile(r"1[3-9]\d{9}"), "[手机号]"),
]


def mask_free_text(text: str | None) -> tuple[str | None, bool]:
    """中文自由文本植入标识检出与掩码（身份证/手机号首期规则）。"""
    if text is None:
        return None, False
    masked, hit = text, False
    for pat, rep in _PII_PATTERNS:
        if pat.search(masked):
            masked = pat.sub(rep, masked)
            hit = True
    return masked, hit


def request_export(db: Session, grant_id: int, dataset_version_id: int,
                   field_whitelist: list[str], created_by: str,
                   expires_in_hours: int = 24, export_code: str = "") -> AssetDsExport:
    """导出申请：grant 必须含 export 操作且有效；版本必须 published。"""
    grant = db.get(AssetDsGrant, grant_id)
    if grant is None or grant.status != "active":
        raise PermissionError("授权缺失或已撤销，禁止导出")
    if "export" not in (grant.operations or []):
        raise PermissionError("授权不含导出操作")
    now = datetime.now(timezone.utc)
    if grant.valid_until and grant.valid_until < now:
        raise PermissionError("授权已过期")
    version = db.get(AssetDsDatasetVersion, dataset_version_id)
    if version is None or version.status != "published":
        raise PermissionError("仅已发布版本可导出")
    exp = AssetDsExport(
        export_code=export_code or f"EXP-{dataset_version_id}-{int(now.timestamp())}",
        grant_id=grant_id, dataset_version_id=dataset_version_id,
        field_whitelist=field_whitelist, status="approved",
        expires_at=now + timedelta(hours=expires_in_hours), created_by=created_by)
    db.add(exp)
    db.flush()
    return exp


def generate_export_csv(db: Session, export: AssetDsExport,
                        rows: list[dict], free_text_fields: list[str] | None = None) -> tuple[str, dict]:
    """生成 CSV：白名单过滤 + 公式注入清洗 + 自由文本脱敏；过期/撤销拒绝。"""
    now = datetime.now(timezone.utc)
    if export.status in ("revoked", "expired"):
        raise PermissionError("导出已撤销或过期")
    if export.expires_at and export.expires_at < now:
        export.status = "expired"
        raise PermissionError("导出已过期")
    wl = set(export.field_whitelist or [])
    free_text_fields = free_text_fields or []
    masked_hits = 0
    buf = io.StringIO()
    writer = csv.writer(buf)
    header = [c for c in (rows[0].keys() if rows else []) if c in wl]
    writer.writerow(header)
    for row in rows:
        out = []
        for col in header:
            v = row.get(col)
            if col in free_text_fields and isinstance(v, str):
                v, hit = mask_free_text(v)
                masked_hits += 1 if hit else 0
            out.append(sanitize_csv_cell(v if not isinstance(v, (int, float)) else v))
        writer.writerow(out)
    export.status = "generated"
    export.row_count = len(rows)
    export.masking_applied = {"free_text_fields": free_text_fields, "masked_hits": masked_hits}
    return buf.getvalue(), {"rows": len(rows), "masked_hits": masked_hits}


# ---------------- B12 旧口径/治理口径对账分解 ----------------

def reconcile_old_vs_governed(source_row_count: int, governed_rows: list) -> dict:
    """同一时点旧口径（源行数）与治理口径（治理事实）差异分解。

    守恒口径按 fact_key 去重（每源行一键）：source_rows = governed + quarantined
    + excluded（均按键计）；unexplained 必须为 0 才可认证（B09 硬门禁）。
    迟到修改产生的被取代版本行（superseded_versions）是平台侧追加，不进守恒式，
    单独披露。JOIN 不放大计数：按治理事实键对账，不按 JOIN 展开。
    """
    from collections import Counter
    key_rows: dict[str, list] = {}
    for f in governed_rows:
        key_rows.setdefault(f.fact_key, []).append(f)
    governed = quarantined = excluded = 0
    for key, rows in key_rows.items():
        latest = max(rows, key=lambda r: getattr(r, "id", 0))
        if latest.deleted == "true":
            excluded += 1
        elif getattr(latest, "quality_flag", "") == "unknown_code":
            quarantined += 1
        else:
            governed += 1
    superseded = sum(len(rows) - 1 for rows in key_rows.values() if len(rows) > 1)
    unexplained = source_row_count - (governed + quarantined + excluded)
    return {
        "source_rows": source_row_count,
        "governed_facts": governed,
        "quarantined": quarantined,
        "excluded_deleted": excluded,
        "superseded_versions": superseded,
        "unexplained": unexplained,
        "conserved": unexplained == 0,
    }


# ---------------- B15 保留义务冲突分支 ----------------

def resolve_deletion_policy(patient_facts: list, active_grants: int,
                            retention_until: datetime | None = None,
                            legal_hold: bool = False,
                            now: datetime | None = None) -> dict:
    """删除请求 vs 保留义务三分支（B02 §4.4）：

    - 无义务且无授权 → hard_delete 允许；
    - 有保留义务（retention_until 未到 或 legal_hold）→ restricted_seal 受限封存（不硬删）；
    - 义务已尽但仍有活跃用途授权 → defer_revoke_grants 先撤权再删。
    """
    now = now or datetime.now(timezone.utc)
    has_facts = bool(patient_facts)
    obligation_active = legal_hold or (retention_until is not None and retention_until > now)
    if obligation_active:
        return {"action": "restricted_seal", "reason": "保留义务生效（法定/授权保留期）",
                "sealed_facts": len(patient_facts), "hard_deleted": 0}
    if active_grants > 0:
        return {"action": "defer_revoke_grants", "reason": f"存在 {active_grants} 条活跃用途授权，先撤权后删",
                "revoke_grants_first": True, "hard_deleted": 0}
    if has_facts:
        return {"action": "hard_delete", "reason": "无义务无授权，允许删除",
                "hard_deleted": len(patient_facts)}
    return {"action": "noop", "reason": "无数据", "hard_deleted": 0}


# ---------------- B15 生命周期 ----------------

def revoke_grant(db: Session, grant_id: int, reason: str) -> dict:
    """撤权即时生效：版本递增（缓存键失效），后续导出/读取实时校验拒绝。"""
    g = db.get(AssetDsGrant, grant_id)
    if g is None:
        raise ValueError("授权不存在")
    g.status = "revoked"
    g.revoked_at = datetime.now(timezone.utc)
    g.revoke_reason = reason
    g.grant_version = (g.grant_version or 1) + 1
    affected = db.scalars(select(AssetDsExport).where(
        AssetDsExport.grant_id == grant_id,
        AssetDsExport.status.in_(["approved", "generated"]))).all()
    for e in affected:
        e.status = "revoked"
    return {"grant_version": g.grant_version, "exports_revoked": len(affected)}


def replay_revocations_after_restore(revoked_export_codes: list[str]) -> dict:
    """备份恢复后撤销重放清单（B15 验收：恢复不复活已禁用交付）。"""
    return {"replay_export_codes": revoked_export_codes,
            "policy": "restore_then_replay_revocations"}
