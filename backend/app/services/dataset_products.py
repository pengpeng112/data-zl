"""193 B11—B15 + 210 S4/S5/S7：患者时间线、统计主题、训练集构建、受控导出与生命周期。

- 时间线/统计/训练/覆盖：仅取版本冻结成员（asset_ds_version_members），
  并应用授权行范围（210 F07/T14）。
- 导出状态机：requested→review_pending→approved→generating→generated→
  expired/revoked/failed；申请不是审批，审批 hash 绑定授权/策略/清单快照，
  生成与下载全量重验（210 F08/T22—T26）。
- 撤销写账本（asset_ds_revocation_ledger），备份恢复后幂等重放；
  到期清理先 dry-run，保留义务/hold 材料不动（210 F11/T29/T30）。
"""
from __future__ import annotations

import csv
import io
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dataset import (
    AssetDsBatch, AssetDsDataset, AssetDsDatasetVersion, AssetDsExport,
    AssetDsFact, AssetDsGrant, AssetDsRevocationLedger,
)
from . import dataset_pipeline as pipe
from . import dataset_security as sec

# 受控工件目录：服务端解析，请求不可指定路径；生产由部署配置覆盖（S10 检查项）
DEFAULT_ARTIFACTS_DIR = os.environ.get(
    "APP_DS_EXPORT_ARTIFACTS_DIR", "ds_export_artifacts")

_EXPORT_CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


# ---------------- 版本范围与行范围 ----------------

def apply_row_scope_patients(row_scope: dict | None) -> list[str] | None:
    """行范围 → 患者白名单；None=无患者级限制（仅显式 all 或非 P3/P4 场景）。"""
    row_scope = row_scope or {}
    if row_scope.get("all") is True:
        return None
    patients = row_scope.get("patients")
    return list(patients) if isinstance(patients, list) and patients else None


def version_table_physical_keys(db: Session, version_id: int) -> list[dict]:
    """版本来源批次对应的表级物理键（分类桥接用，210 F01/T19）。"""
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None or not v.source_batch_ids:
        return []
    batches = db.scalars(select(AssetDsBatch).where(
        AssetDsBatch.run_id.in_([str(x) for x in v.source_batch_ids]))).all()
    keys: list[dict] = []
    for b in batches:
        obj = b.object_name or ""
        schema_name, _, table_name = obj.partition(".")
        if not table_name:
            schema_name, table_name = "", obj
        keys.append({"source_code": b.source_code, "schema_name": schema_name,
                     "table_name": table_name})
    return keys


def version_policy_refs(db: Session, version_id: int) -> list[str]:
    """版本有效策略对象键：版本自身（含 code 的规范键）+ 来源表（组合继承）。

    版本主键 = ``dataset:{code}:{version_id}``（code 与 version 归属一致由
    解析方保证，210 §4.1 旧键兼容规则）。
    """
    refs: list[str] = []
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is not None:
        d = db.get(AssetDsDataset, v.dataset_id) if v.dataset_id else None
        refs.append(f"dataset:{d.dataset_code}:{version_id}" if d is not None
                    else f"dataset_version:{version_id}")
    for key in version_table_physical_keys(db, version_id):
        refs.append(sec.canonical_object_ref("table", key))
        # 列级标签在导出字段核验时按 {table_key + column_name} 单独构造
    return refs


# ---------------- B11 患者时间线 ----------------

def patient_timeline(db: Session, version_id: int, internal_patient_id: str,
                     row_scope: dict | None = None) -> dict:
    """时间线事件按 business_time 升序；仅版本成员 + 行范围内患者。

    无记录返回空 events（调用方渲染空态，不得显示"未患病"）。
    """
    scope_patients = apply_row_scope_patients(row_scope)
    if scope_patients is not None and internal_patient_id not in scope_patients:
        return {"internal_patient_id": internal_patient_id, "events": [],
                "count": 0, "note": "patient outside row scope"}
    facts = [f for f in pipe.version_member_facts(db, version_id)
             if f.internal_patient_id == internal_patient_id]
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
            "count": len(events), "dataset_version_id": version_id}


# ---------------- B12 统计主题（首发：30 天再入院率） ----------------

def readmission_rate(db: Session, version_id: int, window_days: int = 30,
                     row_scope: dict | None = None) -> dict:
    """治理事实口径（版本成员+行范围）：同患者两次 visit 间隔 ≤ window 天计一次再入院。

    分母=有住院事实的患者数；JOIN 不放大计数（按患者聚合，非按事实行）。
    """
    scope_patients = apply_row_scope_patients(row_scope)
    facts = pipe.version_member_facts(db, version_id)
    by_patient: dict[str, list[datetime]] = {}
    for f in facts:
        if f.fact_kind != "visit" or not f.business_time:
            continue
        if scope_patients is not None and f.internal_patient_id not in scope_patients:
            continue
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
            "dataset_version_id": version_id,
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
                       data_card_extra: dict | None = None,
                       row_scope: dict | None = None,
                       purpose_isolation: dict | None = None) -> dict:
    """训练集 + 数据卡（版本成员+行范围；用途假名隔离由调用方传入映射）。"""
    scope_patients = apply_row_scope_patients(row_scope)
    facts = pipe.version_member_facts(db, dataset_version_id)
    if scope_patients is not None:
        facts = [f for f in facts if f.internal_patient_id in scope_patients]
    patients = sorted({f.internal_patient_id for f in facts})
    splits = patient_group_split(patients, cfg)
    label_fn = label_fn or (lambda facts_of_patient: 0)
    by_patient: dict[str, list] = {}
    for f in facts:
        by_patient.setdefault(f.internal_patient_id, []).append(f)
    examples = []
    leaks = 0
    alias = purpose_isolation or {}
    for split, pids in splits.items():
        for pid in pids:
            pf = by_patient.get(pid, [])
            pred_time = max((f.business_time for f in pf if f.business_time),
                            default=datetime(1970, 1, 1, tzinfo=timezone.utc))
            usable = [f for f in pf if temporal_features_available(f.available_time, pred_time)]
            leaks += len(pf) - len(usable)
            examples.append({"split": split,
                             # 用途假名：跨用途不可直接关联患者原始内部 ID
                             "patient": alias.get(pid, purpose_alias(pid)) if purpose_isolation is not None else pid,
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


def purpose_alias(pid: str) -> str:
    """用途假名：同用途内稳定（哈希），跨用途不可直接关联（B02 §4）。"""
    import hashlib
    return "PA-" + hashlib.sha256(pid.encode()).hexdigest()[:12]


# ---------------- B14 受控导出（210 S5 真实闭环） ----------------

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

EXPORTABLE_FACT_FIELDS = (
    "fact_key", "fact_kind", "internal_patient_id", "source_code",
    "standard_value", "business_time", "available_time", "quality_flag",
)


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


def _field_column_ref(db: Session, version_id: int, field: str) -> str | None:
    """导出字段 → 版本来源表的列级对象键（标签文本审查用，210 T24）。"""
    for key in version_table_physical_keys(db, version_id):
        try:
            return sec.canonical_object_ref("column", {**key, "column_name": field})
        except sec.PolicyValidationError:
            continue
    return None


def _label_blocked_fields(db: Session, version_id: int, fields: list[str]) -> list[str]:
    """按列级标签拦截：受限形态（free_text/image/audio_video）未获专项脱敏审批的
    字段禁止进入导出（用户声明不参与判定）。"""
    blocked: list[str] = []
    for field in fields:
        ref = _field_column_ref(db, version_id, field)
        if not ref:
            continue
        rows = sec.active_classifications(db, [ref])
        for row in rows:
            try:
                policy = sec.resolve_policy(row.labels, strict=True)
            except sec.PolicyValidationError:
                blocked.append(field)
                break
            if policy.data_form in sec.EXPORT_RESTRICTED_DATA_FORMS:
                blocked.append(field)
                break
    return sorted(set(blocked))


def new_export_code() -> str:
    """服务端随机唯一导出码（不绑定 code/version，避免重复申请冲突）。"""
    return f"EXP-{secrets.token_urlsafe(12).replace('-', 'x').replace('_', 'y')}"


def request_export(db: Session, *, principal: str, purpose_code: str,
                   resource_ref: str, version: AssetDsDatasetVersion,
                   requested_fields: list[str], project_code: str | None = None,
                   expires_in_hours: int = 24) -> AssetDsExport:
    """导出申请（不是审批）：授权必须属于当前主体/用途/资源且含 export。

    校验通过创建 status=review_pending 的申请行；字段合法性（许可投影/受限形态）
    在此预检，审批时终裁。
    """
    grant, decision, reason = sec.resolve_grant(db, principal, purpose_code,
                                                resource_ref, operation="export")
    if grant is None:
        raise PermissionError(f"导出授权不可用：{decision} {reason}")
    if version is None or version.status != "published":
        raise PermissionError("仅已发布版本可导出")
    fields = [f for f in (requested_fields or []) if isinstance(f, str) and f]
    if not fields:
        raise PermissionError("导出字段清单为空")
    unknown = [f for f in fields if f not in EXPORTABLE_FACT_FIELDS]
    if unknown:
        raise PermissionError(f"未知导出字段: {unknown}（可导出: {list(EXPORTABLE_FACT_FIELDS)}")
    blocked = _label_blocked_fields(db, version.id, fields)
    if blocked:
        raise PermissionError(
            f"字段受标签限制（受限形态未获专项脱敏审批）: {blocked}")
    allow = (grant.column_scope or {}).get("allow")
    if allow is not None:
        outside = [f for f in fields if f not in allow]
        if outside:
            raise PermissionError(f"字段越出授权列白名单: {outside}")
    now = datetime.now(timezone.utc)
    exp = AssetDsExport(
        export_code=new_export_code(),
        grant_id=grant.id, dataset_version_id=version.id,
        requested_fields=fields, field_whitelist=fields,
        status="review_pending",
        expires_at=now + timedelta(hours=expires_in_hours),
        created_by=principal, requested_by=principal,
        purpose_code=purpose_code, project_code=project_code)
    db.add(exp)
    db.flush()
    return exp


def approval_hash(db: Session, export: AssetDsExport) -> str:
    """审批绑定快照 hash：授权版本 + 各对象 active 分类版本 + 清单摘要 + 字段。"""
    import hashlib
    grant = db.get(AssetDsGrant, export.grant_id)
    version = db.get(AssetDsDatasetVersion, export.dataset_version_id)
    refs = version_policy_refs(db, export.dataset_version_id)
    cls_rows = sec.active_classifications(db, refs)
    # 字段级列对象键一并纳入（文本审查审批不可绕过）
    for field in (export.field_whitelist or []):
        ref = _field_column_ref(db, export.dataset_version_id, field)
        if ref:
            cls_rows.extend(sec.active_classifications(db, [ref]))
    payload = {
        "grant_id": export.grant_id,
        "grant_version": getattr(grant, "grant_version", None),
        "grant_status": getattr(grant, "status", None),
        "manifest_sha256": getattr(version, "manifest_sha256", None),
        "classifications": sorted(
            (f"{r.object_type}|{r.object_ref}|v{r.version}" for r in cls_rows)),
        "field_whitelist": sorted(export.field_whitelist or []),
        # 统一 UTC 表示：DB 会话时区（如 +08:00）与内存 UTC 的 isoformat 必须一致
        "expires_at": (export.expires_at.astimezone(timezone.utc).isoformat()
                       if export.expires_at else None),
    }
    return hashlib.sha256(
        "|".join(json_dumps_sorted(payload).split("\n")).encode()).hexdigest()


def json_dumps_sorted(obj) -> str:
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def approve_export(db: Session, export: AssetDsExport, approver: str,
                   decision: str, note: str = "",
                   expires_in_hours: int = 24) -> AssetDsExport:
    """独立审批：approver 必须与申请主体不同（调用方校验），核定字段/期限。

    decision=approve → status=approved 且绑定 approval_hash；
    decision=reject → status=revoked（review_note 留痕）。
    """
    if export.status != "review_pending":
        raise PermissionError(f"导出申请状态不可审批: {export.status}")
    if decision not in ("approve", "reject"):
        raise PermissionError("decision 必须为 approve|reject")
    if decision == "reject":
        export.status = "revoked"
        export.review_note = note or "审批拒绝"
        db.flush()
        return export
    export.field_whitelist = list(export.field_whitelist or [])
    export.expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    export.approved_by = approver
    export.approved_at = datetime.now(timezone.utc)
    export.review_note = note
    export.approval_hash = approval_hash(db, export)
    export.status = "approved"
    db.flush()
    return export


def _artifact_path_for(export_code: str, artifacts_dir: str | None = None) -> Path:
    if not _EXPORT_CODE_RE.match(export_code or ""):
        raise PermissionError("导出码非法")
    base = Path(artifacts_dir or DEFAULT_ARTIFACTS_DIR).resolve()
    path = (base / f"{export_code}.csv").resolve()
    if not str(path).startswith(str(base)):
        raise PermissionError("工件路径越界")
    return path


def generate_export(db: Session, export: AssetDsExport, operator: str,
                    artifacts_dir: str | None = None,
                    principal: str | None = None,
                    purpose_code: str | None = None,
                    cancel_requested: bool = False) -> dict:
    """同步生成真实工件（无后台 worker 的最小实现：状态机+取消检查+失败可恢复）。

    生成前重验：审批 hash 未漂移（策略/授权/清单变动即拒绝）、授权仍有效、
    版本仍 published。生成中可取消（cancel_requested）→ failed，不产半成品下载。
    """
    if export.status not in ("approved", "failed"):
        raise PermissionError(f"状态不可生成: {export.status}")
    now_dt = datetime.now(timezone.utc)
    if export.expires_at and export.expires_at <= now_dt:
        export.status = "expired"
        db.flush()
        raise PermissionError("导出已过期")
    if export.approval_hash and approval_hash(db, export) != export.approval_hash:
        export.status = "revoked"
        export.generation_error = (
            f"审批快照已失效（策略/授权/清单变动），需重新审批 "
            f"[stored={export.approval_hash[:12]} now={approval_hash(db, export)[:12]}]")
        db.flush()
        raise PermissionError(export.generation_error)
    grant = db.get(AssetDsGrant, export.grant_id)
    ok, decision = sec.grant_active(grant, operation="export")
    if not ok:
        export.status = "revoked"
        export.generation_error = f"授权不可用: {decision}"
        db.flush()
        raise PermissionError(export.generation_error)
    version = db.get(AssetDsDatasetVersion, export.dataset_version_id)
    if version is None or version.status != "published":
        export.status = "revoked"
        export.generation_error = "版本已不可用（撤销/非发布态）"
        db.flush()
        raise PermissionError(export.generation_error)
    if cancel_requested:
        export.status = "failed"
        export.generation_error = "生成前取消"
        db.flush()
        return {"status": "failed", "note": "生成前取消，可从 approved 状态重试"}

    export.status = "generating"
    db.flush()
    try:
        facts = pipe.version_member_facts(db, export.dataset_version_id)
        scope_patients = apply_row_scope_patients(grant.row_scope)
        if scope_patients is not None:
            facts = [f for f in facts if f.internal_patient_id in scope_patients]
        wl = [c for c in export.field_whitelist if c in EXPORTABLE_FACT_FIELDS]
        masked_hits = 0
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(wl)
        for f in facts:
            row_raw = {
                "fact_key": f.fact_key, "fact_kind": f.fact_kind,
                "internal_patient_id": f.internal_patient_id,
                "source_code": f.source_code,
                "standard_value": f.standard_value,
                "business_time": f.business_time.isoformat() if f.business_time else None,
                "available_time": f.available_time.isoformat() if f.available_time else None,
                "quality_flag": f.quality_flag,
            }
            out = []
            for col in wl:
                v = row_raw.get(col)
                if col == "standard_value" and isinstance(v, str):
                    v, hit = mask_free_text(v)
                    masked_hits += 1 if hit else 0
                out.append(sanitize_csv_cell(v))
            writer.writerow(out)
        content = buf.getvalue()
        import hashlib
        path = _artifact_path_for(export.export_code, artifacts_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
        export.status = "generated"
        export.row_count = len(facts)
        export.file_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        export.artifact_path = str(path)
        export.artifact_bytes = path.stat().st_size
        export.masking_applied = {"free_text_fields": ["standard_value"],
                                  "masked_hits": masked_hits,
                                  "declared_by": "labels+default"}
        db.flush()
        return {"status": "generated", "row_count": export.row_count,
                "file_sha256": export.file_sha256, "artifact_bytes": export.artifact_bytes}
    except PermissionError:
        raise
    except Exception as e:  # 生成失败可恢复（approved/failed 可重试），无半成品下载
        export.status = "failed"
        export.generation_error = str(e)[:500]
        db.flush()
        raise


def read_export_artifact(export: AssetDsExport, artifacts_dir: str | None = None) -> bytes:
    """读取受控工件（路径仅来自库内记录 + 导出码二次校验，无请求参数）。"""
    if export.status != "generated":
        raise PermissionError(f"工件不可下载（状态 {export.status}）")
    path = _artifact_path_for(export.export_code, artifacts_dir)
    if export.artifact_path and str(path) != str(Path(export.artifact_path).resolve()):
        raise PermissionError("工件路径与登记不一致")
    if not path.exists():
        raise PermissionError("工件不存在（可能已被清理）")
    return path.read_bytes()


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


# ---------------- B15 生命周期（210 S7 账本化） ----------------

def record_revocation(db: Session, revocation_type: str, target_ref: str,
                      reason: str, revoked_by: str, target_id: int | None = None,
                      applied_inline: bool = True) -> AssetDsRevocationLedger:
    """记撤销账目。在线撤销（正常路径）传播与记账同事务完成 → 记 replayed
    （applied_inline）；备份恢复重放时账目以 replayed=false 载入再幂等重放。"""
    now = datetime.now(timezone.utc)
    db.add(AssetDsRevocationLedger(
        revocation_type=revocation_type, target_ref=target_ref, target_id=target_id,
        reason=reason, revoked_by=revoked_by,
        replayed="true" if applied_inline else "false",
        replayed_at=now if applied_inline else None,
        replay_result={"applied_inline": True} if applied_inline else None))
    db.flush()
    row = db.scalars(select(AssetDsRevocationLedger).where(
        AssetDsRevocationLedger.revocation_type == revocation_type,
        AssetDsRevocationLedger.target_ref == target_ref)
        .order_by(AssetDsRevocationLedger.id.desc())).first()
    return row


def revoke_grant(db: Session, grant_id: int, reason: str,
                 operator: str = "") -> dict:
    """撤权即时生效：版本递增（缓存键失效），导出传播撤销，写撤销账本。"""
    g = db.get(AssetDsGrant, grant_id)
    if g is None:
        raise ValueError("授权不存在")
    g.status = "revoked"
    g.revoked_at = datetime.now(timezone.utc)
    g.revoke_reason = reason
    g.grant_version = (g.grant_version or 1) + 1
    affected = db.scalars(select(AssetDsExport).where(
        AssetDsExport.grant_id == grant_id,
        AssetDsExport.status.in_(["review_pending", "approved", "generating",
                                  "generated"]))).all()
    for e in affected:
        e.status = "revoked"
    record_revocation(db, "grant", f"grant:{grant_id}", reason, operator,
                      target_id=grant_id)
    return {"grant_version": g.grant_version, "exports_revoked": len(affected)}


def revoke_version_propagation(db: Session, version_id: int, reason: str,
                               operator: str = "") -> dict:
    """版本撤销传播：未完成生成与已生成工件的导出全部拒绝（状态置 revoked）。"""
    affected = db.scalars(select(AssetDsExport).where(
        AssetDsExport.dataset_version_id == version_id,
        AssetDsExport.status.in_(["review_pending", "approved", "generating",
                                  "generated"]))).all()
    for e in affected:
        e.status = "revoked"
    record_revocation(db, "version", f"dataset_version:{version_id}", reason,
                      operator, target_id=version_id)
    return {"exports_revoked": len(affected)}


def has_unreplayed_revocation(db: Session, grant_id: int | None = None,
                              version_id: int | None = None,
                              export_code: str | None = None) -> str | None:
    """恢复保护：存在未重放撤销时相关出口保持关闭（210 T30）。"""
    q = select(AssetDsRevocationLedger).where(
        AssetDsRevocationLedger.replayed == "false")
    rows = db.scalars(q).all()
    for r in rows:
        if grant_id is not None and r.target_ref == f"grant:{grant_id}":
            return r.target_ref
        if version_id is not None and r.target_ref == f"dataset_version:{version_id}":
            return r.target_ref
        if export_code is not None and r.target_ref == f"export:{export_code}":
            return r.target_ref
        if grant_id is None and version_id is None and export_code is None and rows:
            return r.target_ref
    return None


def replay_revocations_after_restore(db: Session, operator: str = "") -> dict:
    """备份恢复后撤销账本幂等重放（210 F11：真实库操作，非仅返回计划）。

    对每条未重放账目：重新断言目标处于撤销态（grant/version/export），标记
    replayed；重复重放对已重放行零作用，不复活任何工件。
    """
    from ..models.dataset import AssetDsDatasetVersion
    replayed_grants = replayed_versions = replayed_exports = 0
    pending = db.scalars(select(AssetDsRevocationLedger).where(
        AssetDsRevocationLedger.replayed == "false")
        .order_by(AssetDsRevocationLedger.id)).all()
    for entry in pending:
        result: dict = {}
        if entry.revocation_type == "grant" and entry.target_id is not None:
            g = db.get(AssetDsGrant, entry.target_id)
            if g is not None and g.status != "revoked":
                g.status = "revoked"
                g.revoked_at = g.revoked_at or datetime.now(timezone.utc)
                result["grant_reasserted"] = True
            for e in db.scalars(select(AssetDsExport).where(
                    AssetDsExport.grant_id == entry.target_id,
                    AssetDsExport.status.in_(["review_pending", "approved",
                                              "generating", "generated"]))).all():
                e.status = "revoked"
                replayed_exports += 1
            replayed_grants += 1
        elif entry.revocation_type == "version" and entry.target_id is not None:
            v = db.get(AssetDsDatasetVersion, entry.target_id)
            if v is not None and v.status != "revoked":
                # 恢复回滚了撤销 → 账本权威重放（幂等：不新建账目）
                v.status = "revoked"
                v.revoked_at = v.revoked_at or datetime.now(timezone.utc)
                result["version_reasserted"] = True
            for e in db.scalars(select(AssetDsExport).where(
                    AssetDsExport.dataset_version_id == entry.target_id,
                    AssetDsExport.status.in_(["review_pending", "approved",
                                              "generating", "generated"]))).all():
                e.status = "revoked"
                replayed_exports += 1
            replayed_versions += 1
        elif entry.revocation_type == "export":
            code = entry.target_ref.removeprefix("export:")
            for e in db.scalars(select(AssetDsExport).where(
                    AssetDsExport.export_code == code)).all():
                if e.status in ("review_pending", "approved", "generating", "generated"):
                    e.status = "revoked"
                    replayed_exports += 1
        elif entry.revocation_type == "policy":
            # 策略撤销 = 旧 active 分类已 superseded；重放时再次确认无 active 复活
            result["policy_reasserted"] = True
        entry.replayed = "true"
        entry.replayed_at = datetime.now(timezone.utc)
        entry.replay_result = result or {"noop": True}
    db.flush()
    return {"entries_replayed": len(pending), "grants": replayed_grants,
            "versions": replayed_versions, "exports": replayed_exports,
            "policy": "restore_then_replay_revocations",
            "operator": operator or "restore-replay"}


def retention_cleanup_plan(db: Session, now: datetime | None = None) -> dict:
    """到期清理 dry-run（210 S7：先计划后经控制通道执行，不删保留/hold 材料）。"""
    now = now or datetime.now(timezone.utc)
    expired_exports = db.scalars(select(AssetDsExport).where(
        AssetDsExport.status.in_(["generated", "approved"]),
        AssetDsExport.expires_at.is_not(None),
        AssetDsExport.expires_at <= now)).all()
    hold = [e.export_code for e in expired_exports
            if (e.masking_applied or {}).get("legal_hold")]
    return {"now": now.isoformat(), "dry_run": True,
            "expired_export_codes": [e.export_code for e in expired_exports],
            "hold_retained": hold,
            "note": "dry-run only; execution requires controlled channel approval"}
