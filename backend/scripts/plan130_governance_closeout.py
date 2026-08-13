"""Plan 130 S3 platform governance closeout (dry-run by default).

This script is deliberately platform-only: it never resolves a business-source
credential or opens a source connection.  The apply path is guarded by an
environment switch, an operator supplied backup reference and an out-of-repo
0600 rollback manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

FORBIDDEN_KEYS = {"sample_data", "detail", "patient", "name", "phone", "identity"}
MUTABLE_FINDING_FIELDS = ("system_code", "source_code", "namespace_name", "schema_name", "table_name", "column_name")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _safe_ref(value: Any) -> str:
    raw = _text(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16] if raw else ""


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items() if k.lower() not in FORBIDDEN_KEYS}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) or len(value) <= 160 else value[:160] + "…"
    return str(value)[:160]


def _row_dict(row: Any, fields: Iterable[str]) -> dict[str, Any]:
    return {f: _safe(getattr(row, f, None)) for f in fields}


def duplicate_finding_groups(findings: Iterable[Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[Any]] = defaultdict(list)
    for finding in findings:
        key = tuple(getattr(finding, f, None) for f in (
            "run_id", "rule_code", "target_ref", "system_code", "source_code",
            "namespace_name", "schema_name", "table_name", "column_name", "severity", "metric_value",
            "total_cnt", "error_cnt",
        ))
        groups[key].append(finding)
    return [
        {"key_digest": hashlib.sha256(repr(k).encode()).hexdigest()[:16], "finding_ids": [getattr(x, "id", None) for x in rows], "count": len(rows)}
        for k, rows in groups.items() if len(rows) > 1
    ]


def match_finding_table(finding: Any, tables: Iterable[Any]) -> dict[str, Any]:
    """Match only on already present physical identity; ambiguity fails closed."""
    rows = list(tables)
    fields = {f: _text(getattr(finding, f, None)) for f in MUTABLE_FINDING_FIELDS}
    target = _text(getattr(finding, "target_ref", None))
    if target and not fields["table_name"]:
        parts = [p for p in re.split(r"[.:/|]", target) if p]
        if _text(getattr(finding, "target_type", None)).lower() == "column" and len(parts) >= 3:
            fields["schema_name"], fields["table_name"], fields["column_name"] = parts[-3:]
        elif len(parts) >= 2:
            fields["schema_name"], fields["table_name"] = parts[-2:]
    candidates = []
    for table in rows:
        ok = True
        for f in ("system_code", "source_code", "namespace_name", "schema_name", "table_name"):
            value = fields[f]
            if value and _text(getattr(table, f, None)).upper() != value.upper():
                ok = False
        if ok and fields["table_name"]:
            candidates.append(table)
    if len(candidates) != 1:
        return {"status": "missing" if not candidates else "ambiguous", "candidate_count": len(candidates), "target_digest": _safe_ref(target)}
    table = candidates[0]
    return {"status": "matched", "candidate_count": 1, "table_id": getattr(table, "id", None), "fields": {f: _text(getattr(table, f, None)) for f in MUTABLE_FINDING_FIELDS[:5]}}


def validate_manifest_path(path: str | Path, *, repo_root: Path = ROOT) -> Path:
    p = Path(path)
    if not p.is_absolute():
        raise ValueError("rollback manifest must be an absolute path")
    resolved = p.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return resolved
    raise ValueError("rollback manifest must be outside repository")


def write_manifest(path: str | Path, payload: dict[str, Any]) -> Path:
    target = validate_manifest_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(_safe(payload), ensure_ascii=False, indent=2).encode("utf-8")
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def apply_gate(*, env: dict[str, str] | None = None, backup_ref: str | None, manifest: str | None) -> None:
    env = env or os.environ
    if env.get("APP_PLAN130_PLATFORM_APPLY", "").lower() != "true":
        raise RuntimeError("apply requires APP_PLAN130_PLATFORM_APPLY=true")
    if not _text(backup_ref):
        raise RuntimeError("apply requires --backup-ref")
    if not manifest:
        raise RuntimeError("apply requires --rollback-manifest")
    validate_manifest_path(manifest)


def rollback_gate(*, env: dict[str, str] | None = None, backup_ref: str | None, manifest_from: str | None) -> None:
    env = env or os.environ
    if env.get("APP_PLAN130_PLATFORM_APPLY", "").lower() != "true":
        raise RuntimeError("rollback requires APP_PLAN130_PLATFORM_APPLY=true")
    if not _text(backup_ref):
        raise RuntimeError("rollback requires --backup-ref")
    if not manifest_from:
        raise RuntimeError("rollback requires --rollback-manifest-from")
    source = validate_manifest_path(manifest_from)
    if not source.is_file():
        raise RuntimeError("rollback manifest does not exist")


def require_formal_review_result(result: dict[str, Any]) -> None:
    """Reject candidate links even when the underlying review service returned ok."""
    if not result.get("ok") or result.get("action") != "linked_formal":
        raise RuntimeError("review must link an existing formal relation")


def rollback_state_matches(current: dict[str, Any], expected_after: dict[str, Any]) -> bool:
    return all(_safe(current.get(k)) == _safe(v) for k, v in expected_after.items())


def _seed_map() -> dict[str, dict[str, Any]]:
    from app.api.v1.quality import QUALITY_RULES_SEED
    return {str(x["rule_code"]): x for x in QUALITY_RULES_SEED}


def dry_run_report(db: Any) -> dict[str, Any]:
    from sqlalchemy import func, select
    from app.models.asset import AssetRelation, AssetRelationReview, AssetTable
    from app.models.quality import QualityFinding, QualityRule
    from app.models.recipe import AssetRelationRecipe
    from app.services.metric_stub_import import import_missing_metric_stubs
    rules = list(db.scalars(select(QualityRule)).all())
    findings = list(db.scalars(select(QualityFinding)).all())
    reviews = list(db.scalars(select(AssetRelationReview)).all())
    recipes = list(db.scalars(select(AssetRelationRecipe)).all())
    tables = list(db.scalars(select(AssetTable)).all())
    seed = _seed_map()
    # Global metadata rules legitimately have no single system/source.  Scope
    # fields are required; physical attribution belongs on each finding.
    missing_rules = [r for r in rules if any(not _text(getattr(r, f, None)) for f in ("rule_name", "rule_category", "check_scope"))]
    finding_matches = [match_finding_table(f, tables) for f in findings]
    formal_matches = []
    for review in reviews:
        rels = list(db.scalars(select(AssetRelation).where(AssetRelation.from_table == review.from_table, AssetRelation.to_table == review.to_table)).all())
        formal_matches.append({"review_id": review.id, "status": review.review_status, "formal_ids": [r.id for r in rels if (r.relation_layer or "").lower() == "formal" or (r.validation_status or "").lower() in {"verified", "approved", "manual_reviewed"}]})
    seed_diff = []
    for code, item in seed.items():
        existing = next((r for r in rules if r.rule_code == code), None)
        if not existing:
            seed_diff.append({"rule_code": code, "action": "missing_seed"})
        else:
            fields = [f for f in ("rule_name", "rule_category", "check_scope", "description", "rule_type", "target_type", "execution_mode") if not _text(getattr(existing, f, None)) and item.get(f)]
            if fields:
                seed_diff.append({"rule_code": code, "action": "backfill_empty", "fields": fields})
    status_counts = Counter(_text(getattr(f, "status", None)) or "null" for f in findings)
    enabled_counts = Counter("enabled" if bool(getattr(r, "enabled", False)) else "disabled" for r in rules)
    return {
        "mode": "dry_run", "writes": 0,
        "counts": {"rules": len(rules), "findings": len(findings), "tables": len(tables), "reviews": len(reviews), "recipes": len(recipes)},
        "rule_missing_governance": {"count": len(missing_rules), "rule_ids": [r.id for r in missing_rules]},
        "finding_physical_identity": Counter(x["status"] for x in finding_matches),
        "finding_duplicate_groups": duplicate_finding_groups(findings),
        "finding_status_counts": dict(status_counts), "rule_enabled_counts": dict(enabled_counts),
        "review_formal_matches": formal_matches, "recipe_seed_diff": seed_diff,
        "core48_blocked_metrics": import_missing_metric_stubs(db, dry_run=True)["items"],
        "safety": {"source_connections": 0, "sample_data_emitted": False, "detail_emitted": False, "people_data_emitted": False},
    }


def apply_changes(db: Any, *, manifest_path: str, backup_ref: str, approve_ids: list[int]) -> dict[str, Any]:
    """Apply the narrowly scoped, platform-only changes in one transaction."""
    from sqlalchemy import select
    from app.models.asset import AssetRelation, AssetRelationReview, AssetTable
    from app.models.governance_base import GovernAuditLog
    from app.models.quality import QualityFinding, QualityRule
    from app.models.recipe import AssetRelationRecipe
    from app.models.metric_asset import AssetMetricDefinition, AssetMetricVersion
    from app.services.relation_review_service import approve_review
    from app.services.recipe_service import canonical_recipe_payload, normalize_recipe_joins, recipe_hash, map_seed_status
    from app.services.metric_stub_import import MISSING_CORE_METRICS, import_missing_metric_stubs

    findings = list(db.scalars(select(QualityFinding)).all())
    if duplicate_finding_groups(findings):
        raise RuntimeError("duplicate findings refuse apply")
    tables = list(db.scalars(select(AssetTable)).all())
    changes: list[dict[str, Any]] = []

    # (0) Close the 20 non-executable core metrics with evidence-backed
    # blocked reasons.  This fixes the misleading definition-level "active"
    # status while preserving all historical results.
    metric_codes = [f"MET_CORE_{num:02d}" for num in MISSING_CORE_METRICS]
    metric_defs = list(db.scalars(select(AssetMetricDefinition).where(AssetMetricDefinition.metric_code.in_(metric_codes))).all())
    metric_versions = list(db.scalars(select(AssetMetricVersion).where(AssetMetricVersion.metric_code.in_(metric_codes))).all())
    if len(metric_defs) != len(metric_codes) or any(not any(v.metric_code == d.metric_code for v in metric_versions) for d in metric_defs):
        raise RuntimeError("core48 placeholder set is incomplete; refuse non-reversible apply")
    metric_before = {
        ("metric_definition", row.id): _row_dict(row, ("title", "meaning", "status", "current_version_id"))
        for row in metric_defs
    }
    metric_before.update({
        ("metric_version", row.id): _row_dict(row, ("status", "is_active", "definition_text", "limitations", "revision_reason"))
        for row in metric_versions
    })
    # Keep this inside the closeout transaction.  The service normally commits
    # for its standalone CLI/API callers, but a partial commit here would make
    # the rollback manifest incomplete if a later review/recipe step failed.
    import_missing_metric_stubs(db, dry_run=False, created_by="plan130_s4", commit=False)
    db.flush()
    for row in metric_defs:
        before = metric_before[("metric_definition", row.id)]
        after = _row_dict(row, before)
        if before != after:
            changes.append({"entity": "metric_definition", "id": row.id, "before": before, "after": after, "fields": list(before)})
    for row in metric_versions:
        before = metric_before[("metric_version", row.id)]
        after = _row_dict(row, before)
        if before != after:
            changes.append({"entity": "metric_version", "id": row.id, "before": before, "after": after, "fields": list(before)})

    # (a) Backfill only empty governance fields. Existing enabled/status values are immutable here.
    seed = _seed_map()
    for rule in db.scalars(select(QualityRule)).all():
        source = seed.get(rule.rule_code, {})
        before = {f: getattr(rule, f, None) for f in ("rule_name", "rule_category", "check_scope", "description", "rule_type", "target_type", "execution_mode")}
        changed = []
        for field, value in source.items():
            if field in before and not _text(before[field]) and value is not None:
                setattr(rule, field, value); changed.append(field)
        if changed:
            changes.append({"entity": "quality_rule", "id": rule.id, "before": before, "after": _row_dict(rule, before), "fields": changed})
            db.add(GovernAuditLog(module="plan130", entity_type="quality_rule", entity_ref=str(rule.id), action="backfill_empty_governance", before_data=_safe(before), after_data=_safe(_row_dict(rule, before)), operator="plan130", reason="S3 closeout"))

    # (b) Fill only physical identity fields when exactly one table matches.
    for finding in findings:
        match = match_finding_table(finding, tables)
        if match["status"] != "matched":
            continue
        table = next(t for t in tables if getattr(t, "id", None) == match["table_id"])
        before = {f: getattr(finding, f, None) for f in MUTABLE_FINDING_FIELDS}
        after = {f: getattr(table, f, None) for f in MUTABLE_FINDING_FIELDS}
        changed = [f for f in MUTABLE_FINDING_FIELDS if not _text(before[f]) and _text(after[f])]
        if changed:
            for f in changed: setattr(finding, f, after[f])
            changes.append({"entity": "quality_finding", "id": finding.id, "before": _safe(before), "after": _safe({f: getattr(finding, f, None) for f in MUTABLE_FINDING_FIELDS}), "fields": changed})
            db.add(GovernAuditLog(module="plan130", entity_type="quality_finding", entity_ref=str(finding.id), action="backfill_physical_identity", before_data=_safe(before), after_data=_safe({f: getattr(finding, f, None) for f in MUTABLE_FINDING_FIELDS}), operator="plan130", reason="S3 closeout"))

    # (c) Explicit reviews only; approve_review is accepted only when it links formal.
    if approve_ids:
        reviews = {r.id: r for r in db.scalars(select(AssetRelationReview).where(AssetRelationReview.id.in_(approve_ids))).all()}
        for review_id in approve_ids:
            review = reviews.get(review_id)
            if review is None: raise RuntimeError(f"review not found: {review_id}")
            before = _row_dict(review, ("review_status", "source_relation_id", "reviewer", "review_note"))
            result = approve_review(db, review, reviewer="plan130")
            try:
                require_formal_review_result(result)
            except RuntimeError as exc:
                raise RuntimeError(f"review {review_id} did not link formal") from exc
            changes.append({"entity": "review", "id": review_id, "before": before, "after": _row_dict(review, ("review_status", "source_relation_id", "reviewer", "review_note"))})
            db.add(GovernAuditLog(module="plan130", entity_type="relation_review", entity_ref=str(review_id), action="approve_linked_formal", before_data=_safe(before), after_data=_safe(_row_dict(review, ("review_status", "source_relation_id", "reviewer", "review_note"))), operator="plan130", reason="explicit --approve-review"))

    # (d) Import seed recipes directly into this transaction; every new version is inactive.
    seed_path = Path(__file__).resolve().parents[2] / "开发起步包" / "数据资产_关系图谱" / "view_relation_recipes.json"
    recipe_changes = []
    if seed_path.exists():
        for item in json.loads(seed_path.read_text(encoding="utf-8")):
            rid = item.get("recipe_id") or item.get("id")
            if not rid: continue
            payload = canonical_recipe_payload(item)
            digest = recipe_hash(payload)
            current = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == rid).order_by(AssetRelationRecipe.version.desc()))
            if current and current.content_hash == digest: continue
            version = (current.version + 1) if current else 1
            rec = AssetRelationRecipe(recipe_id=rid, version=version, recipe_name=item.get("recipe_name") or item.get("recommended_view_name"), status=map_seed_status(item.get("status")), is_active=False, domain=item.get("domain"), source_system=item.get("source_system"), recommended_view_name=item.get("recommended_view_name"), description=item.get("description"), business_domain=item.get("business_domain", item.get("domain")), primary_tables=item.get("primary_tables") or [], joins=normalize_recipe_joins(item.get("joins") or []), recipe_json=payload, content_hash=digest, imported_from="view_relation_recipes.json", ai_readable=False, evidence_summary=item.get("validation_evidence"), risk_summary={"hard_rules": item.get("hard_rules"), "do_not_use_as_primary_join": item.get("do_not_use_as_primary_join")}, created_by="plan130")
            db.add(rec); db.flush()
            recipe_changes.append({"recipe_id": rid, "version": version, "id": rec.id, "content_hash": digest})
            db.add(GovernAuditLog(module="plan130", entity_type="relation_recipe", entity_ref=f"{rid}:{version}", action="import_inactive_recipe", before_data=None, after_data={"recipe_id": rid, "version": version, "is_active": False}, operator="plan130", reason="S3 closeout"))

    manifest = {"tool": "plan130_governance_closeout", "backup_ref": backup_ref, "changes": changes, "created_recipes": recipe_changes}
    write_manifest(manifest_path, manifest)
    db.commit()
    return {"mode": "apply", "writes": len(changes) + len(recipe_changes), "rollback_manifest": str(Path(manifest_path).resolve()), "changed_entities": len(changes), "created_recipes": len(recipe_changes)}


def rollback_changes(db: Any, manifest_path: str) -> dict[str, Any]:
    """Restore only unchanged rows recorded by this tool; conflicts fail closed."""
    from sqlalchemy import delete, select
    from app.models.asset import AssetRelationReview
    from app.models.governance_base import GovernAuditLog
    from app.models.quality import QualityFinding, QualityRule
    from app.models.recipe import AssetRelationRecipe
    from app.models.metric_asset import AssetMetricDefinition, AssetMetricVersion
    payload = json.loads(Path(validate_manifest_path(manifest_path)).read_text(encoding="utf-8"))
    restored = 0
    for item in payload.get("changes", []):
        model = {
            "quality_rule": QualityRule,
            "quality_finding": QualityFinding,
            "review": AssetRelationReview,
            "metric_definition": AssetMetricDefinition,
            "metric_version": AssetMetricVersion,
        }.get(item.get("entity"))
        if model is None: continue
        row = db.get(model, item.get("id"))
        if row is None: raise RuntimeError(f"rollback missing row {item.get('entity')}:{item.get('id')}")
        before = item.get("before") or {}
        after = item.get("after") or {}
        for key, value in before.items():
            if key in after and not rollback_state_matches({key: getattr(row, key, None)}, {key: after.get(key)}):
                raise RuntimeError(f"rollback conflict {item.get('entity')}:{item.get('id')}:{key}")
        # The manifest stores before values; after apply current values are expected to differ.
        # Restore only fields listed by the original change.
        for key in item.get("fields", before.keys()):
            setattr(row, key, before.get(key))
        restored += 1
    for item in payload.get("created_recipes", []):
        row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.id == item.get("id")))
        if row is None: continue
        if row.content_hash != item.get("content_hash") or row.recipe_id != item.get("recipe_id"):
            raise RuntimeError(f"rollback recipe conflict {item.get('recipe_id')}:{item.get('version')}")
        db.delete(row); restored += 1
    db.add(GovernAuditLog(module="plan130", entity_type="rollback_manifest", entity_ref=_safe_ref(manifest_path), action="rollback", before_data={"manifest": _safe_ref(manifest_path)}, after_data={"restored": restored}, operator="plan130", reason="explicit rollback"))
    db.commit()
    return {"mode": "rollback", "writes": restored, "restored": restored}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan 130 S3 governance closeout")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-ref")
    parser.add_argument("--rollback-manifest")
    parser.add_argument("--rollback-manifest-from")
    parser.add_argument("--approve-review", nargs="*", type=int, default=[])
    args = parser.parse_args(argv)
    if args.apply:
        apply_gate(env=os.environ, backup_ref=args.backup_ref, manifest=args.rollback_manifest)
    elif args.rollback_manifest_from:
        rollback_gate(env=os.environ, backup_ref=args.backup_ref, manifest_from=args.rollback_manifest_from)
    url = os.environ.get("APP_DB_URL")
    if not url:
        raise SystemExit("APP_DB_URL is required")
    from sqlalchemy.engine import make_url
    parsed_url = make_url(url)
    if not parsed_url.drivername.startswith("postgresql") or parsed_url.database not in {"data_asset", "data_asset_test"}:
        raise SystemExit("refusing non-platform database")
    from app.core.db import SessionLocal
    db = SessionLocal()
    try:
        if args.rollback_manifest_from:
            report = rollback_changes(db, args.rollback_manifest_from)
        elif args.apply:
            report = apply_changes(db, manifest_path=args.rollback_manifest, backup_ref=args.backup_ref, approve_ids=args.approve_review)
        else:
            report = dry_run_report(db)
        print(json.dumps(_safe(report), ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
