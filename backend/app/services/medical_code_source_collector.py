
"""Read-only collectors for diagnosis and operation code sync diffs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.asset_system import AssetDataSource
from ..models.dict_medical import DictMedicalCodeItem, DictMedicalSyncDiff
from ..services.credentials import resolve
from ..services.db_connectors import DB_CONNECTOR_MAP


LOCAL_CODE_SETS = {
    "diagnosis": "diagnosis_local_clinical",
    "operation": "operation_local_clinical",
}


def _build_connector(source: AssetDataSource):
    db_type = (source.db_type or "").lower()
    connector_cls = DB_CONNECTOR_MAP.get(db_type)
    if connector_cls is None:
        raise HTTPException(status_code=400, detail=f"unsupported db_type: {source.db_type}")
    user, password = resolve(source.credential_ref)
    database = source.service_name or source.database_name or ""
    return connector_cls(
        host=source.host_masked or "",
        port=source.port or 0,
        database=database,
        user=user or "",
        password=password or "",
        connection_mode=source.connection_mode or "direct",
    )


def _row_value(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    upper_key = key.upper()
    if upper_key in row:
        return row[upper_key]
    lower_key = key.lower()
    if lower_key in row:
        return row[lower_key]
    return None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _open_diff_exists(
    db: Session,
    *,
    category_code: str,
    target_system: str,
    target_source_code: str,
    diff_type: str,
    code_set_code: str,
    item_code: str,
) -> bool:
    stmt = select(DictMedicalSyncDiff).where(
        DictMedicalSyncDiff.category_code == category_code,
        DictMedicalSyncDiff.target_system == target_system,
        DictMedicalSyncDiff.target_source_code == target_source_code,
        DictMedicalSyncDiff.diff_type == diff_type,
        DictMedicalSyncDiff.code_set_code == code_set_code,
        DictMedicalSyncDiff.item_code == item_code,
        DictMedicalSyncDiff.status == "open",
    )
    return db.scalar(stmt.limit(1)) is not None


def _add_diff(
    db: Session,
    *,
    category_code: str,
    target_system: str,
    target_source_code: str,
    diff_type: str,
    code_set_code: str,
    item_code: str,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any] | None,
    severity: str = "medium",
) -> bool:
    if _open_diff_exists(
        db,
        category_code=category_code,
        target_system=target_system,
        target_source_code=target_source_code,
        diff_type=diff_type,
        code_set_code=code_set_code,
        item_code=item_code,
    ):
        return False
    db.add(DictMedicalSyncDiff(
        category_code=category_code,
        target_system=target_system,
        target_source_code=target_source_code,
        diff_type=diff_type,
        code_set_code=code_set_code,
        item_code=item_code,
        before_data=before_data,
        after_data=after_data,
        severity=severity,
        status="open",
    ))
    return True


def _collect_source_rows(connector: Any, category_code: str, max_rows: int) -> list[dict[str, Any]]:
    if category_code == "diagnosis":
        sql = """
SELECT
  \u9662\u6807\u7f16\u7801 AS LOCAL_CODE,
  \u9662\u6807\u540d\u79f0 AS LOCAL_NAME,
  \u56fd\u6807\u7f16\u7801 AS STANDARD_CODE,
  \u56fd\u6807\u540d\u79f0 AS STANDARD_NAME
FROM CDA.CDA_DICTIONARY
WHERE \u5b57\u5178\u540d\u79f0 = 'ICD-10\u8bca\u65ad\u7f16\u7801'
  AND \u7cfb\u7edf\u6807\u8bc6 = 'HIS'
  AND ROWNUM <= :max_rows
"""
        return [dict(r) for r in connector.execute_readonly(sql, params={"max_rows": max_rows}, max_rows=max_rows)]
    if category_code == "operation":
        sql = """
SELECT DISTINCT
  OPERATION_CODE AS LOCAL_CODE,
  OPERATION AS LOCAL_NAME,
  OPERATION_SCALE AS OPERATION_LEVEL
FROM SM.MED_OPERATION_NAME
WHERE OPERATION_CODE IS NOT NULL
  AND ROWNUM <= :max_rows
"""
        return [dict(r) for r in connector.execute_readonly(sql, params={"max_rows": max_rows}, max_rows=max_rows)]
    raise HTTPException(status_code=400, detail="category_code must be diagnosis/operation")


def _source_payload(row: dict[str, Any], category_code: str, source_code: str) -> dict[str, Any]:
    payload = {
        "source_code": source_code,
        "category_code": category_code,
        "item_code": _text_or_none(_row_value(row, "LOCAL_CODE")),
        "item_name_cn": _text_or_none(_row_value(row, "LOCAL_NAME")),
        "standard_code": _text_or_none(_row_value(row, "STANDARD_CODE")),
        "standard_name": _text_or_none(_row_value(row, "STANDARD_NAME")),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    if category_code == "operation":
        payload["operation_level"] = _text_or_none(_row_value(row, "OPERATION_LEVEL"))
    return payload


def collect_medical_code_diffs(
    db: Session,
    *,
    source_code: str,
    target_system: str = "asset",
    category_code: str | None = None,
    max_rows: int = 5000,
) -> dict[str, Any]:
    """Collect source medical codes and generate local sync diffs only."""
    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise HTTPException(status_code=400, detail=f"source_code not found: {source_code}")

    categories = [category_code] if category_code else ["diagnosis", "operation"]
    connector = _build_connector(source)
    try:
        scanned = 0
        created = 0
        skipped_existing = 0
        by_category: dict[str, dict[str, int]] = {}
        for category in categories:
            if category not in LOCAL_CODE_SETS:
                raise HTTPException(status_code=400, detail="category_code must be diagnosis/operation")
            rows = _collect_source_rows(connector, category, max_rows=max_rows)
            code_set = LOCAL_CODE_SETS[category]
            cat_scanned = 0
            cat_created = 0
            cat_skipped = 0
            for row in rows:
                payload = _source_payload(row, category, source_code)
                item_code = payload.get("item_code")
                if not item_code:
                    continue
                cat_scanned += 1
                item = db.scalar(select(DictMedicalCodeItem).where(
                    DictMedicalCodeItem.code_set_code == code_set,
                    DictMedicalCodeItem.item_code == item_code,
                ))
                if item is None:
                    added = _add_diff(
                        db,
                        category_code=category,
                        target_system=target_system,
                        target_source_code=source_code,
                        diff_type="missing_target",
                        code_set_code=code_set,
                        item_code=item_code,
                        before_data=None,
                        after_data=payload,
                        severity="high",
                    )
                    cat_created += int(added)
                    cat_skipped += int(not added)
                    continue
                source_name = payload.get("item_name_cn")
                if source_name and item.item_name_cn and source_name != item.item_name_cn:
                    added = _add_diff(
                        db,
                        category_code=category,
                        target_system=target_system,
                        target_source_code=source_code,
                        diff_type="name_mismatch",
                        code_set_code=code_set,
                        item_code=item_code,
                        before_data={"item_code": item.item_code, "item_name_cn": item.item_name_cn},
                        after_data=payload,
                        severity="medium",
                    )
                    cat_created += int(added)
                    cat_skipped += int(not added)
            by_category[category] = {
                "scanned": cat_scanned,
                "diffs_created": cat_created,
                "diffs_skipped_existing": cat_skipped,
            }
            scanned += cat_scanned
            created += cat_created
            skipped_existing += cat_skipped
    finally:
        connector.close()

    return {
        "status": "success",
        "mode": "live_source_diff",
        "source_code": source_code,
        "target_system": target_system,
        "entity_type": "medical_code",
        "category_code": category_code,
        "max_rows": max_rows,
        "scanned": scanned,
        "diffs_created": created,
        "diffs_skipped_existing": skipped_existing,
        "by_category": by_category,
    }
