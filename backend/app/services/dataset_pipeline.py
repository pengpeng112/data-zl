"""193 B06—B10 + 210 S4：身份关联、批次编排、标准化、质量对账与版本发布。

合成闭环实现：确定性匹配优先、幂等批次、检查点与提交边界一致、
未知码隔离、发布门禁（质量/安全/审批独立）、发布失败旧版可用。

210 S4（F07）修订：
- freeze 绑定具体 fact 行为版本成员（asset_ds_version_members），此后所有
  读/统计/训练/导出仅取成员清单——新批次/迟到修改不进入旧冻结版本。
- publish 不再信任请求 body 的质量/安全结论：只认持久化质量断言与独立安全评审
  （security_conclusion），必需断言缺失/未评/过期一律拒绝。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dataset import (
    AssetDsBatch, AssetDsDataset, AssetDsDatasetVersion, AssetDsFact,
    AssetDsIdentityMap, AssetDsQualityAssertion, AssetDsVersionMember,
)

# 版本状态机（B10）：合法迁移
VERSION_TRANSITIONS = {
    "draft": {"validated", "revoked"},
    "validated": {"approved", "draft", "revoked"},
    "approved": {"published", "deprecated", "revoked"},
    "published": {"deprecated", "revoked"},
    "deprecated": set(),
    "revoked": set(),
}


class StateMachineError(Exception):
    pass


def transition_version(status: str, target: str) -> str:
    if target not in VERSION_TRANSITIONS.get(status, set()):
        raise StateMachineError(f"非法状态迁移: {status} → {target}")
    return target


# ---------------- B06 身份关联与拆分 ----------------

@dataclass
class MatchResult:
    internal_patient_id: str
    confidence: str  # deterministic|probable
    created: bool


def deterministic_patient_id(source_code: str, source_key: str) -> str:
    """确定性内部 ID：同 (source, key) 稳定；不做跨源自动合并（同名不同人不合并）。"""
    digest = hashlib.sha256(f"{source_code}|{source_key}".encode()).hexdigest()[:10]
    return f"DS-P{digest}"


def register_identity(db: Session, source_code: str, source_key: str,
                      rule_version: str = "deterministic_v1") -> MatchResult:
    """登记/复用身份映射。不同源同号不自动串人；跨源合并只能走人工合并 API。

    SessionLocal autoflush=False：add 后必须显式 flush，
    否则同批次内同患者第二条记录的存在性检查看不到 pending 行（B07 踩坑）。
    """
    pid = deterministic_patient_id(source_code, source_key)
    existing = db.scalar(select(AssetDsIdentityMap).where(
        AssetDsIdentityMap.internal_patient_id == pid,
        AssetDsIdentityMap.source_code == source_code,
        AssetDsIdentityMap.source_key == source_key))
    if existing:
        return MatchResult(pid, "deterministic", created=False)
    db.add(AssetDsIdentityMap(internal_patient_id=pid, source_code=source_code,
                              source_key=source_key, match_rule_version=rule_version,
                              confidence="deterministic", review_status="auto"))
    db.flush()
    return MatchResult(pid, "deterministic", created=True)


def merge_identities(db: Session, primary_pid: str, secondary_pid: str, operator: str) -> int:
    """人工合并：secondary 的映射指向 primary，保留历史（merged_into）。"""
    rows = db.scalars(select(AssetDsIdentityMap).where(
        AssetDsIdentityMap.internal_patient_id == secondary_pid,
        AssetDsIdentityMap.merged_into.is_(None))).all()
    for r in rows:
        r.merged_into = primary_pid
    db.flush()  # autoflush=False：立即落事务，后续 select 可见
    return len(rows)


def split_identity(db: Session, secondary_pid: str, operator: str) -> int:
    """错误合并撤销（拆分）：恢复 secondary 的映射为独立身份；影响行返回。"""
    rows = db.scalars(select(AssetDsIdentityMap).where(
        AssetDsIdentityMap.internal_patient_id == secondary_pid,
        AssetDsIdentityMap.merged_into.isnot(None))).all()
    for r in rows:
        r.split_from = r.merged_into
        r.merged_into = None
    db.flush()  # autoflush=False：同上
    return len(rows)


def effective_patient_ids(db: Session, pids: list[str]) -> dict[str, str]:
    """解析合并链：内部 ID → 最终主体 ID（含被合并者）。"""
    chain = {p: p for p in pids}
    maps = db.scalars(select(AssetDsIdentityMap).where(
        AssetDsIdentityMap.internal_patient_id.in_(pids))).all()
    merged = {m.internal_patient_id: m.merged_into for m in maps if m.merged_into}
    for p in pids:
        cur, hops = p, 0
        while cur in merged and hops < 10:
            cur = merged[cur]
            hops += 1
        chain[p] = cur
    return chain


# ---------------- B07 批次编排（幂等+检查点） ----------------

def ingest_batch(db: Session, run_id: str, source_code: str, object_name: str,
                 records: list[dict], rule_version: str,
                 shard_window: dict | None = None) -> dict:
    """幂等写入治理事实：fact_key+rule_version 冲突跳过；检查点=已提交键集。

    records 每条：{fact_key, fact_kind, source_patient_key, source_visit_id?,
    original_value_ref, standard_value?, code_system?, unit?, business_time?,
    available_time?, deleted?}
    同一 run 重跑零重复（返回 skipped 计数）。
    """
    batch = db.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == run_id))
    if batch is None:
        batch = AssetDsBatch(run_id=run_id, source_code=source_code,
                             object_name=object_name, shard_window=shard_window or {})
        db.add(batch)
        db.flush()
    checkpoints: dict = dict(batch.checkpoints or {})
    written = skipped = quarantined = 0
    for rec in records:
        key = rec["fact_key"]
        if key in checkpoints:
            skipped += 1
            continue
        match = register_identity(db, source_code, rec["source_patient_key"])
        flag = rec.get("quality_flag", "ok")
        if rec.get("standard_value") is None and rec.get("require_standard", False):
            flag = "unknown_code"
            quarantined += 1
        db.add(AssetDsFact(
            fact_key=key, fact_kind=rec["fact_kind"],
            internal_patient_id=match.internal_patient_id,
            internal_visit_id=rec.get("source_visit_id"),
            source_code=source_code,
            original_value_ref=rec["original_value_ref"],
            standard_value=rec.get("standard_value"),
            standard_code_system=rec.get("code_system"),
            unit=rec.get("unit"),
            rule_version=rule_version,
            quality_flag=flag,
            business_time=rec.get("business_time"),
            available_time=rec.get("available_time"),
            batch_run_id=run_id,
            deleted="true" if rec.get("deleted") else "false"))
        checkpoints[key] = {"patient": match.internal_patient_id}
        written += 1
    counters = dict(batch.counters or {})
    counters["written"] = counters.get("written", 0) + written
    counters["skipped"] = counters.get("skipped", 0) + skipped
    counters["quarantined"] = counters.get("quarantined", 0) + quarantined
    batch.counters = counters
    batch.checkpoints = checkpoints
    batch.status = "checkpointed" if checkpoints else "running"
    return {"written": written, "skipped": skipped, "quarantined": quarantined,
            "total_keys": len(checkpoints)}


def resume_batch_from_checkpoint(db: Session, run_id: str) -> list[str]:
    """断点恢复：返回已提交键集（重跑据此跳过，不漏不重）。"""
    batch = db.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == run_id))
    return sorted((batch.checkpoints or {}).keys()) if batch else []


def ingest_batch_chunked(db: Session, run_id: str, source_code: str, object_name: str,
                         records: list[dict], rule_version: str,
                         chunk_size: int = 2,
                         crash_after_chunks: int | None = None) -> dict:
    """B07 断电模拟：按 chunk 提交（提交边界=检查点边界），可在指定 chunk 后崩溃。

    崩溃=抛 InterruptionSimulated（调用方 rollback 后重跑全量）；
    每 chunk 提交后其检查点已持久化，重跑从检查点续跑：不漏数、不重数。
    """
    class InterruptionSimulated(RuntimeError):
        pass

    done = {"written": 0, "skipped": 0, "quarantined": 0, "crashed": False}
    for ci in range(0, len(records), chunk_size):
        chunk = records[ci:ci + chunk_size]
        r = ingest_batch(db, run_id, source_code, object_name, chunk, rule_version)
        db.commit()  # 提交边界与检查点一致
        done["written"] += r["written"]
        done["skipped"] += r["skipped"]
        done["quarantined"] += r["quarantined"]
        if crash_after_chunks is not None and (ci // chunk_size) + 1 >= crash_after_chunks:
            done["crashed"] = True
            raise InterruptionSimulated(
                f"模拟断电：已提交 {(ci // chunk_size) + 1} chunks，剩余未写入")
    return done


def cancel_batch(db: Session, run_id: str, reason: str = "timeout") -> dict:
    """B07 超时/取消：批次置 cancelled；检查点保留，恢复=直接重跑同 run。"""
    batch = db.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == run_id))
    if batch is None:
        raise StateMachineError("批次不存在")
    batch.status = "cancelled"
    batch.error_class = "cancelled"
    batch.error_detail = reason
    batch.finished_at = datetime.now(timezone.utc)
    db.flush()
    return {"run_id": run_id, "status": "cancelled", "reason": reason}


def late_modify_fact(db: Session, fact_key: str, new_standard_value: str | None,
                     modifying_run_id: str, note: str = "") -> dict:
    """B07 迟到修改：旧值不覆盖语义=追加新规则版本行；原行保留（来源保真）。

    事实唯一键 (fact_key, rule_version)：修改以新 rule_version 落行，
    原行不动，读侧按 (fact_key) 取最新 rule_version。
    """
    existing = db.scalars(select(AssetDsFact).where(
        AssetDsFact.fact_key == fact_key,
        AssetDsFact.deleted == "false").order_by(AssetDsFact.id.desc())).all()
    if not existing:
        raise StateMachineError(f"事实不存在：{fact_key}")
    latest = existing[0]
    new_rule = f"{latest.rule_version}+late@{modifying_run_id}"
    db.add(AssetDsFact(
        fact_key=fact_key, fact_kind=latest.fact_kind,
        internal_patient_id=latest.internal_patient_id,
        internal_visit_id=latest.internal_visit_id,
        source_code=latest.source_code,
        original_value_ref=latest.original_value_ref,
        standard_value=new_standard_value,
        standard_code_system=latest.standard_code_system,
        unit=latest.unit,
        rule_version=new_rule,
        quality_flag="late_modified",
        business_time=latest.business_time,
        available_time=datetime.now(timezone.utc),  # 修改结果现在才可用
        batch_run_id=modifying_run_id, deleted="false"))
    db.flush()
    return {"fact_key": fact_key, "new_rule_version": new_rule,
            "superseded_rule_version": latest.rule_version, "note": note}


def latest_facts(db: Session) -> list:
    """读侧视图：每个 fact_key 取未删除的最新规则版本行（迟到修改生效口径）。"""
    facts = db.scalars(select(AssetDsFact).where(AssetDsFact.deleted == "false")).all()
    by_key: dict[str, object] = {}
    for f in sorted(facts, key=lambda x: x.id):
        by_key[f.fact_key] = f  # 后写覆盖=最新版本
    return list(by_key.values())


def late_delete_fact(db: Session, fact_key: str, deleting_run_id: str,
                     reason: str = "") -> dict:
    """B07 迟到删除：软删除标记（源端撤销语义），计数与发布清单立即排除。"""
    rows = db.scalars(select(AssetDsFact).where(AssetDsFact.fact_key == fact_key)).all()
    if not rows:
        raise StateMachineError(f"事实不存在：{fact_key}")
    for r in rows:
        r.deleted = "true"
        r.quality_flag = "late_deleted"
    db.flush()
    return {"fact_key": fact_key, "rows_marked": len(rows),
            "deleting_run_id": deleting_run_id, "reason": reason}


def detect_schema_drift(expected_fields: list[str], record_fields: list[str]) -> dict:
    """B07 schema 漂移检测：新增字段默认受限（提示），缺失/类型语义变化=漂移。

    返回 {drifted: bool, added: [...], missing: [...]}。
    """
    exp, act = set(expected_fields), set(record_fields)
    missing = sorted(exp - act)
    added = sorted(act - exp)
    # 缺失字段=源结构破坏（漂移）；新增字段=兼容扩展（默认受限，不算漂移阻断）
    return {"drifted": bool(missing), "missing": missing, "added": added}


def ingest_batch_with_drift_guard(db: Session, run_id: str, source_code: str,
                                  object_name: str, records: list[dict],
                                  rule_version: str,
                                  expected_fields: list[str] | None = None) -> dict:
    """B07 漂移隔离：检测到漂移→该批次隔离（error_class=schema_drift，零写入），
    不影响其他批次/其他源（调用方按 run_id 天然隔离）。
    """
    if expected_fields and records:
        sample_fields = sorted({k for rec in records[:5] for k in rec})
        drift = detect_schema_drift(expected_fields, sample_fields)
        if drift["drifted"]:
            batch = db.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == run_id))
            if batch is None:
                batch = AssetDsBatch(run_id=run_id, source_code=source_code,
                                     object_name=object_name)
                db.add(batch)
                db.flush()
            batch.status = "failed"
            batch.error_class = "schema_drift"
            batch.error_detail = f"missing={drift['missing']} added={drift['added']}"
            db.flush()
            return {"isolated": True, "written": 0, "drift": drift}
    result = ingest_batch(db, run_id, source_code, object_name, records, rule_version)
    result["isolated"] = False
    return result


# ---------------- B08 标准化（未知码隔离） ----------------

def standardize_code(raw_value: str | None, mapping: dict[str, str],
                     rule_version: str) -> tuple[str | None, str]:
    """未知码不猜：无映射返回 (None, unknown_code) 由调用方隔离。"""
    if raw_value is None:
        return None, "unknown_code"
    std = mapping.get(raw_value)
    if std is None:
        return None, "unknown_code"
    return std, "ok"


def convert_unit(value: float | None, from_unit: str, to_unit: str) -> tuple[float | None, str]:
    """单位错配不换算（首期仅同单位直通），错配隔离。"""
    if from_unit != to_unit:
        return None, "unit_mismatch"
    return value, "ok"


# ---------------- B09 质量断言 ----------------

# 210 S4：发布必需的质量维度（缺失任一维度 = 未评估 = 拒绝发布）
REQUIRED_QUALITY_DIMENSIONS = ("coverage", "identity", "linkage")


def evaluate_assertions(db: Session, scope_type: str, scope_ref: str,
                        checks: list[dict]) -> list[dict]:
    """checks: {dimension, metric_name, numerator, denominator, threshold:{op,value}}。

    质量失败（任一 fail）→ 调用方禁止发布（B10 门禁）。
    """
    results = []
    for c in checks:
        th = c.get("threshold") or {}
        op, target = th.get("op", ">="), th.get("value", 1.0)
        num, den = c.get("numerator", 0), c.get("denominator", 0) or 1
        ratio = (num / den) if den else 0.0
        passed = {
            ">=": ratio >= target, ">": ratio > target,
            "<=": ratio <= target, "<": ratio < target, "==": ratio == target,
        }.get(op, False)
        results.append({"dimension": c["dimension"], "metric_name": c["metric_name"],
                        "result": "pass" if passed else "fail", "ratio": round(ratio, 6)})
        db.merge(AssetDsQualityAssertion(
            scope_type=scope_type, scope_ref=scope_ref, dimension=c["dimension"],
            metric_name=c["metric_name"], numerator=num, denominator=den,
            threshold=th, result="pass" if passed else "fail",
            detail={"ratio": round(ratio, 6)}))
    return results


def coverage_by_source_year(db: Session, dataset_version_id: int) -> dict:
    """分源分年覆盖统计（B09 验收：分源分年覆盖可查；210 S4 改按版本成员取数）。"""
    facts = version_member_facts(db, dataset_version_id)
    by: dict[tuple[str, str], int] = {}
    for f in facts:
        year = f.business_time.year if f.business_time else "unknown"
        by[(f.source_code, str(year))] = by.get((f.source_code, str(year)), 0) + 1
    return {f"{s}|{y}": n for (s, y), n in sorted(by.items())}


# ---------------- B10 数据集版本发布 ----------------

def manifest_digest(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False)
                          .encode()).hexdigest()


def _fact_content_digest(fact: AssetDsFact) -> str:
    payload = {
        "fact_key": fact.fact_key, "fact_kind": fact.fact_kind,
        "internal_patient_id": fact.internal_patient_id,
        "source_code": fact.source_code, "original_value_ref": fact.original_value_ref,
        "standard_value": fact.standard_value, "rule_version": fact.rule_version,
        "business_time": fact.business_time.isoformat() if fact.business_time else None,
        "deleted": fact.deleted,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False)
                          .encode()).hexdigest()


def version_batch_run_ids(db: Session, version: AssetDsDatasetVersion) -> list[str]:
    """版本声明的来源批次 run_id 清单（source_batch_ids）。"""
    return [str(x) for x in (version.source_batch_ids or [])]


def version_scope_facts(db: Session, version: AssetDsDatasetVersion) -> list[AssetDsFact]:
    """版本范围事实：仅版本声明批次的行，每个 fact_key 取最新规则版本且未删除。"""
    run_ids = version_batch_run_ids(db, version)
    if not run_ids:
        return []
    facts = db.scalars(select(AssetDsFact).where(
        AssetDsFact.batch_run_id.in_(run_ids),
        AssetDsFact.deleted == "false").order_by(AssetDsFact.id)).all()
    by_key: dict[str, AssetDsFact] = {}
    for f in facts:
        by_key[f.fact_key] = f  # id 升序遍历，后写覆盖=最新版本
    return list(by_key.values())


def bind_version_members(db: Session, version: AssetDsDatasetVersion,
                         facts: list[AssetDsFact]) -> int:
    """把具体 fact 行绑定为版本冻结成员（幂等：已绑定行跳过）。"""
    existing = set(db.scalars(select(AssetDsVersionMember.fact_id).where(
        AssetDsVersionMember.dataset_version_id == version.id)).all())
    added = 0
    for f in facts:
        if f.id in existing:
            continue
        db.add(AssetDsVersionMember(dataset_version_id=version.id, fact_id=f.id,
                                    fact_key=f.fact_key,
                                    content_sha256=_fact_content_digest(f)))
        added += 1
    db.flush()
    return added


def version_member_facts(db: Session, version_id: int) -> list[AssetDsFact]:
    """版本成员查询入口（210 S4 单一出口）：时间线/统计/训练/覆盖/导出共用。

    冻结后新写入的 fact 行不在成员内（版本隔离硬边界）；成员行本身被迟到删除
    标记（fact.deleted=true）时按安全控制覆盖读取许可（不返回）。
    """
    rows = db.execute(
        select(AssetDsFact, AssetDsVersionMember)
        .join(AssetDsVersionMember,
              AssetDsVersionMember.fact_id == AssetDsFact.id)
        .where(AssetDsVersionMember.dataset_version_id == version_id,
               AssetDsFact.deleted == "false")
        .order_by(AssetDsFact.id)).all()
    by_key: dict[str, AssetDsFact] = {}
    for fact, _member in rows:
        by_key[fact.fact_key] = fact
    return list(by_key.values())


def freeze_version(db: Session, version_id: int, frozen_by: str | None = None) -> dict:
    """冻结：绑定具体 fact 行成员并生成清单与摘要（同输入同摘要，确定性）。

    210 S4：清单基于成员行；冻结人记录用于审批职责分离对照。
    """
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None:
        raise StateMachineError("版本不存在")
    facts = version_scope_facts(db, v)
    added = bind_version_members(db, v, facts)
    members = db.scalars(select(AssetDsVersionMember).where(
        AssetDsVersionMember.dataset_version_id == version_id)).all()
    manifest = {"row_count": len(members),
                "kinds": sorted({m.fact_key.split(":")[1] for m in members if ":" in m.fact_key}),
                "member_digests_added": added,
                "rule_versions": v.rule_versions or {},
                "cutoff_at": v.cutoff_at.isoformat() if v.cutoff_at else None}
    v.manifest = manifest
    v.manifest_sha256 = manifest_digest(manifest)
    if frozen_by:
        v.frozen_by = frozen_by
    v.status = transition_version(v.status, "validated")
    v.validated_at = datetime.now(timezone.utc)
    return manifest


def record_security_review(db: Session, version_id: int, reviewer: str,
                           passed: bool, note: str = "") -> dict:
    """210 S4：独立安全评审持久化（发布门禁只认此记录，不认 body 结论）。

    评审人与冻结人必须不同（职责分离）——由 API 层校验后调用。
    """
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None:
        raise StateMachineError("版本不存在")
    if not v.manifest_sha256:
        raise StateMachineError("尚未冻结，缺少清单摘要")
    v.security_conclusion = {
        "reviewed_by": reviewer, "passed": bool(passed), "note": note,
        "manifest_sha256": v.manifest_sha256,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    db.flush()
    return dict(v.security_conclusion)


def publish_version(db: Session, version_id: int, operator: str = "") -> dict:
    """发布门禁（210 S4 重写）：质量断言 + 安全结论 + 审批三独立持久化条件。

    - 质量只认 asset_ds_quality_assertions 中 scope=本版本的持久化断言：
      必需维度（coverage/identity/linkage）齐全且全 pass；缺失/未评/失败拒绝。
    - 安全只认 record_security_review 持久化结论（通过且绑定当前清单摘要）。
    - 审批由 API 层完成主体分离核验；本函数不再接收 body 结论。
    发布失败抛异常且不改状态——旧 published 版本仍可用。
    """
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None:
        raise StateMachineError("版本不存在")
    if v.status != "approved":
        raise StateMachineError(f"发布前置失败：状态={v.status}（需 approved）")
    if not v.manifest_sha256:
        raise StateMachineError("尚未冻结，缺少清单摘要")
    assertions = db.scalars(select(AssetDsQualityAssertion).where(
        AssetDsQualityAssertion.scope_type == "dataset_version",
        AssetDsQualityAssertion.scope_ref == str(version_id))).all()
    by_dim: dict[str, AssetDsQualityAssertion] = {a.dimension: a for a in assertions}
    missing = [d for d in REQUIRED_QUALITY_DIMENSIONS if d not in by_dim]
    if missing:
        raise StateMachineError(f"必需质量维度缺失/未评估: {missing}")
    failed = [f"{a.dimension}:{a.metric_name}" for a in by_dim.values() if a.result != "pass"]
    if failed:
        raise StateMachineError(f"质量门禁未通过: {failed[:3]}")
    sec = v.security_conclusion or {}
    if not sec.get("passed"):
        raise StateMachineError("安全结论未通过或未评审（需独立安全评审记录）")
    if sec.get("manifest_sha256") != v.manifest_sha256:
        raise StateMachineError("安全评审绑定的清单摘要与当前版本不一致（内容已变动，需重审）")
    v.status = transition_version(v.status, "published")
    v.published_at = datetime.now(timezone.utc)
    v.quality_conclusion = {"checks": [
        {"dimension": a.dimension, "metric_name": a.metric_name, "result": a.result}
        for a in by_dim.values()]}
    return {"status": v.status, "manifest_sha256": v.manifest_sha256}


def revoke_version(db: Session, version_id: int, reason: str) -> dict:
    """撤销：禁止新下载（B15 传播由导出端实时校验状态）。"""
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None:
        raise StateMachineError("版本不存在")
    v.status = transition_version(v.status, "revoked")
    v.revoked_at = datetime.now(timezone.utc)
    return {"status": v.status, "reason": reason}
