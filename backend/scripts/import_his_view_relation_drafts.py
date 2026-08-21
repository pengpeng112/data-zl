"""Import plan-136 HIS view evidence as review/recipe drafts.

The command is dry-run by default.  Apply requires an exact confirmation string.
It writes only platform governance tables; it never connects to or writes HIS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


for _candidate in (Path(__file__).resolve().parents[1], Path.cwd()):
    if (_candidate / "app").is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))


CONFIRM_TEXT = "APPLY_PLAN136_HIS_VIEW_DRAFTS"
BATCH_TAG = "plan136_his_view_relations_v1"
SOURCE_CODE = "his_source_10_10_10_15"
SYSTEM_CODE = "HIS_SOURCE"
IDENT_RE = re.compile(r"^[A-Z][A-Z0-9_$#]*$")


def _columns(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        values = value
    else:
        values = re.split(r"[|,+]", str(value or ""))
    return tuple(str(item).strip().upper() for item in values if str(item).strip())


def qualify_table(owner: str, value: Any) -> str:
    parts = [part.strip().strip('"[]`').upper() for part in str(value or "").split(".") if part.strip()]
    owner = owner.strip().upper()
    if not IDENT_RE.fullmatch(owner):
        raise ValueError(f"invalid view owner: {owner}")
    if len(parts) == 1:
        parts.insert(0, owner)
    if len(parts) != 2 or not all(IDENT_RE.fullmatch(part) for part in parts):
        raise ValueError(f"unsupported table identifier: {value}")
    return ".".join(parts)


def _identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    left = (str(row["from_table"]).upper(), _columns(row.get("from_columns")))
    right = (str(row["to_table"]).upper(), _columns(row.get("to_columns")))
    return tuple(sorted((left, right)))


def _qualifier_signature(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("qualifiers") or []
    if not isinstance(values, list):
        values = [values]
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def prepare_review_groups(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    for raw in payload.get("candidates", []):
        if not isinstance(raw, Mapping) or raw.get("intake_status") not in {"candidate", "partial"}:
            continue
        if str(raw.get("status") or "").upper() != "VALID":
            skipped.append({"view": raw.get("view"), "reason": "view_not_valid"})
            continue
        try:
            row = dict(raw)
            row["from_table"] = qualify_table(str(row.get("owner") or ""), row.get("from_table"))
            row["to_table"] = qualify_table(str(row.get("owner") or ""), row.get("to_table"))
            row["from_columns"] = list(_columns(row.get("from_columns")))
            row["to_columns"] = list(_columns(row.get("to_columns")))
            if not row["from_columns"] or len(row["from_columns"]) != len(row["to_columns"]):
                raise ValueError("empty_or_unbalanced_columns")
        except ValueError as exc:
            skipped.append({"view": raw.get("view"), "reason": str(exc)[:200]})
            continue
        key = (_identity(row), _qualifier_signature(row), row.get("intake_status"))
        evidence = {
            "owner": row.get("owner"),
            "view": row.get("view"),
            "source_sql_sha256": row.get("source_sql_sha256"),
            "runtime_status": row.get("runtime_status") or "runtime_skipped",
            "warnings": row.get("warnings") or [],
        }
        if key not in grouped:
            grouped[key] = {**row, "evidence": [evidence]}
        else:
            grouped[key]["evidence"].append(evidence)
    output = sorted(grouped.values(), key=lambda row: json.dumps(_identity(row), sort_keys=True))
    for row in output:
        row["evidence"] = sorted(
            {json.dumps(item, sort_keys=True): item for item in row["evidence"]}.values(),
            key=lambda item: (str(item.get("owner")), str(item.get("view"))),
        )
    return output, skipped


def prepare_recipe_groups(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in payload.get("recipe_candidates", []):
        if not isinstance(raw, Mapping) or str(raw.get("status") or "").upper() != "VALID":
            continue
        owner = str(raw.get("owner") or "").upper()
        view = str(raw.get("view") or "").upper()
        sha = str(raw.get("source_sql_sha256") or "")
        try:
            item = dict(raw)
            item["from_table"] = qualify_table(owner, raw.get("from_table"))
            item["to_table"] = qualify_table(owner, raw.get("to_table"))
            item["from_columns"] = list(_columns(raw.get("from_columns")))
            item["to_columns"] = list(_columns(raw.get("to_columns")))
        except ValueError:
            continue
        grouped[(owner, view, sha)].append(item)
    recipes: list[dict[str, Any]] = []
    for (owner, view, sha), joins in sorted(grouped.items()):
        unique = {
            json.dumps((_identity(row), _qualifier_signature(row), row.get("branch")), sort_keys=True): row
            for row in joins
        }
        clean_joins = sorted(unique.values(), key=lambda row: json.dumps(_identity(row), sort_keys=True))
        recipes.append(
            {
                "recipe_id": f"HIS_VIEW_{owner}_{view}_{sha[:12]}"[:240],
                "owner": owner,
                "view": view,
                "source_sql_sha256": sha,
                "joins": clean_joins,
            }
        )
    return recipes


def _metadata_index(db: Any) -> tuple[set[str], dict[str, set[str]]]:
    from sqlalchemy import func, select

    from app.models.asset import AssetColumn, AssetTable

    tables = db.scalars(select(AssetTable).where(AssetTable.source_code == SOURCE_CODE)).all()
    columns = db.scalars(select(AssetColumn).where(AssetColumn.source_code == SOURCE_CODE)).all()
    table_names = {f"{row.schema_name}.{row.table_name}".upper() for row in tables}
    column_names: dict[str, set[str]] = defaultdict(set)
    for row in columns:
        column_names[f"{row.schema_name}.{row.table_name}".upper()].add(str(row.column_name).upper())
    return table_names, column_names


def metadata_check(
    row: Mapping[str, Any], table_names: set[str], column_names: Mapping[str, set[str]]
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for side in ("from", "to"):
        table = str(row[f"{side}_table"]).upper()
        columns = _columns(row.get(f"{side}_columns"))
        if table not in table_names:
            errors.append(f"missing_table:{table}")
            continue
        missing = sorted(set(columns) - set(column_names.get(table, set())))
        if missing:
            errors.append(f"missing_columns:{table}:{','.join(missing)}")
    return not errors, errors


def _existing_identities(db: Any) -> tuple[set[tuple[Any, ...]], set[tuple[Any, ...]]]:
    from sqlalchemy import select

    from app.models.asset import AssetRelation, AssetRelationReview

    formal: set[tuple[Any, ...]] = set()
    reviews: set[tuple[Any, ...]] = set()
    for row in db.scalars(select(AssetRelation)).all():
        if row.from_table and row.to_table:
            formal.add(_identity(vars(row)))
    for row in db.scalars(select(AssetRelationReview)).all():
        if row.from_table and row.to_table:
            reviews.add(_identity(vars(row)))
    return formal, reviews


def _synchronize_platform_sequences(db: Any) -> int:
    """Advance known platform PK sequences without ever decreasing them."""
    from sqlalchemy import text

    tables = ("asset_relation_reviews", "asset_relation_recipes")
    for table in tables:
        qualified = f"asset.{table}"
        db.execute(
            text(
                "SELECT setval("
                f"pg_get_serial_sequence('{qualified}','id'),"
                "GREATEST("
                f"COALESCE(pg_sequence_last_value(pg_get_serial_sequence('{qualified}','id')::regclass),0),"
                f"COALESCE((SELECT MAX(id) FROM {qualified}),1)"
                "),true)"
            )
        )
    return len(tables)


def execute(payload: Mapping[str, Any], *, apply: bool, confirm: str) -> dict[str, Any]:
    if apply and confirm != CONFIRM_TEXT:
        raise RuntimeError(f"apply requires --confirm {CONFIRM_TEXT}")
    from sqlalchemy import func, select

    from app.core.db import SessionLocal
    from app.models.asset import AssetRelation, AssetRelationReview
    from app.models.recipe import AssetRelationRecipe

    reviews, skipped_prepare = prepare_review_groups(payload)
    recipes = prepare_recipe_groups(payload)
    summary: dict[str, Any] = {
        "mode": "apply" if apply else "dry_run",
        "prepared_reviews": len(reviews),
        "prepared_recipes": len(recipes),
        "eligible_reviews": 0,
        "eligible_recipes": 0,
        "inserted_reviews": 0,
        "inserted_recipes": 0,
        "skipped_existing_formal": 0,
        "skipped_existing_review": 0,
        "skipped_metadata": 0,
        "skipped_prepare": len(skipped_prepare),
        "source_writes": 0,
        "formal_relations_modified": 0,
        "metadata_tables": 0,
        "metadata_columns": 0,
        "metadata_error_types": {},
        "platform_relations_before": 0,
        "platform_reviews_before": 0,
        "platform_recipes_before": 0,
        "platform_relations_after": 0,
        "platform_reviews_after": 0,
        "platform_recipes_after": 0,
        "platform_sequences_synchronized": 0,
        "batch_review_statuses": {},
        "batch_recipe_statuses": {},
        "batch_active_recipes": 0,
    }
    with SessionLocal() as db:
        summary["platform_relations_before"] = db.scalar(
            select(func.count()).select_from(AssetRelation)
        ) or 0
        summary["platform_reviews_before"] = db.scalar(
            select(func.count()).select_from(AssetRelationReview)
        ) or 0
        summary["platform_recipes_before"] = db.scalar(
            select(func.count()).select_from(AssetRelationRecipe)
        ) or 0
        if apply:
            summary["platform_sequences_synchronized"] = _synchronize_platform_sequences(db)
        table_names, column_names = _metadata_index(db)
        summary["metadata_tables"] = len(table_names)
        summary["metadata_columns"] = sum(len(values) for values in column_names.values())
        formal_ids, review_ids = _existing_identities(db)
        for row in reviews:
            identity = _identity(row)
            if identity in formal_ids:
                summary["skipped_existing_formal"] += 1
                continue
            if identity in review_ids:
                summary["skipped_existing_review"] += 1
                continue
            verified, errors = metadata_check(row, table_names, column_names)
            if not verified:
                summary["skipped_metadata"] += 1
                for error in errors:
                    error_type = error.split(":", 1)[0]
                    summary["metadata_error_types"][error_type] = summary["metadata_error_types"].get(error_type, 0) + 1
                continue
            summary["eligible_reviews"] += 1
            if apply:
                evidence = json.dumps(
                    {"batch": BATCH_TAG, "views": row["evidence"][:20], "qualifiers": list(_qualifier_signature(row))},
                    ensure_ascii=False,
                    sort_keys=True,
                )[:4000]
                db.add(
                    AssetRelationReview(
                        relation_scope="candidate",
                        from_system_code=SYSTEM_CODE,
                        from_source_code=SOURCE_CODE,
                        from_table=row["from_table"],
                        from_columns=",".join(row["from_columns"]),
                        to_system_code=SYSTEM_CODE,
                        to_source_code=SOURCE_CODE,
                        to_table=row["to_table"],
                        to_columns=",".join(row["to_columns"]),
                        join_condition=str(row.get("join_condition") or "")[:4000],
                        relation_desc_cn="HIS 有效视图解析关系候选",
                        business_logic_cn="仅视图 SQL 证据与平台元数据确认；尚未独立审核，不自动提升正式关系。",
                        confidence="C",
                        validation_status="compile_valid_metadata_confirmed_runtime_skipped",
                        review_status="draft",
                        review_note=f"{BATCH_TAG}; intake_status={row.get('intake_status')}",
                        source_evidence=evidence,
                    )
                )
                summary["inserted_reviews"] += 1
            review_ids.add(identity)

        existing_recipes = {
            row.recipe_id
            for row in db.scalars(
                select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id.in_([r["recipe_id"] for r in recipes]))
            ).all()
        } if recipes else set()
        for recipe in recipes:
            if recipe["recipe_id"] in existing_recipes:
                continue
            recipe_checks = [metadata_check(row, table_names, column_names) for row in recipe["joins"]]
            checked = [item[0] for item in recipe_checks]
            if not checked or not all(checked):
                summary["skipped_metadata"] += 1
                for _, errors in recipe_checks:
                    for error in errors:
                        error_type = error.split(":", 1)[0]
                        summary["metadata_error_types"][error_type] = summary["metadata_error_types"].get(error_type, 0) + 1
                continue
            summary["eligible_recipes"] += 1
            if apply:
                joins = [
                    {
                        "from_table": row["from_table"],
                        "from_columns": row["from_columns"],
                        "to_table": row["to_table"],
                        "to_columns": row["to_columns"],
                        "qualifiers": list(_qualifier_signature(row)),
                        "warnings": row.get("warnings") or [],
                    }
                    for row in recipe["joins"]
                ]
                content = json.dumps(joins, ensure_ascii=False, sort_keys=True)
                db.add(
                    AssetRelationRecipe(
                        recipe_id=recipe["recipe_id"],
                        version=1,
                        recipe_name=f"{recipe['owner']}.{recipe['view']} 视图关系草稿",
                        status="draft",
                        is_active=False,
                        recipe_json={"owner": recipe["owner"], "view": recipe["view"], "joins": joins},
                        domain="HIS视图关系",
                        source_system=SYSTEM_CODE,
                        recommended_view_name=f"{recipe['owner']}.{recipe['view']}",
                        description="由有效视图 SQL 解析；含函数/聚合/分支等风险，仅供人工审核。",
                        primary_tables=sorted({row["from_table"] for row in recipe["joins"]} | {row["to_table"] for row in recipe["joins"]}),
                        joins=joins,
                        ai_readable=True,
                        evidence_summary={"batch": BATCH_TAG, "source_sql_sha256": recipe["source_sql_sha256"]},
                        risk_summary={"requires_manual_review": True, "runtime_status": "runtime_skipped"},
                        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        created_by="plan136_import",
                        imported_from=BATCH_TAG,
                    )
                )
                summary["inserted_recipes"] += 1
            existing_recipes.add(recipe["recipe_id"])
        db.flush()
        summary["platform_relations_after"] = db.scalar(
            select(func.count()).select_from(AssetRelation)
        ) or 0
        summary["platform_reviews_after"] = db.scalar(
            select(func.count()).select_from(AssetRelationReview)
        ) or 0
        summary["platform_recipes_after"] = db.scalar(
            select(func.count()).select_from(AssetRelationRecipe)
        ) or 0
        summary["batch_review_statuses"] = {
            str(status or "unknown"): int(count)
            for status, count in db.execute(
                select(AssetRelationReview.review_status, func.count(AssetRelationReview.id))
                .where(AssetRelationReview.review_note.contains(BATCH_TAG))
                .group_by(AssetRelationReview.review_status)
            ).all()
        }
        summary["batch_recipe_statuses"] = {
            str(status or "unknown"): int(count)
            for status, count in db.execute(
                select(AssetRelationRecipe.status, func.count(AssetRelationRecipe.id))
                .where(AssetRelationRecipe.imported_from == BATCH_TAG)
                .group_by(AssetRelationRecipe.status)
            ).all()
        }
        summary["batch_active_recipes"] = db.scalar(
            select(func.count()).select_from(AssetRelationRecipe).where(
                AssetRelationRecipe.imported_from == BATCH_TAG,
                AssetRelationRecipe.is_active.is_(True),
            )
        ) or 0
        if apply:
            db.commit()
        else:
            db.rollback()
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = execute(payload, apply=args.apply, confirm=args.confirm)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        detail = getattr(exc, "name", None) if isinstance(exc, (ModuleNotFoundError, NameError)) else None
        original = getattr(exc, "orig", None)
        diagnostic = getattr(original, "diag", None)
        constraint = getattr(diagnostic, "constraint_name", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_name": detail,
                    "constraint": constraint,
                    "sqlstate": sqlstate,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
