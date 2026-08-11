"""Unified first-level business system catalog (plan 90).

Single source of truth for system display names: AssetSystem.system_name_cn.
Independent source systems are peers of HIS/HRP/DATA_CENTER; DATA_CENTER
internal owners stay nested and must never become first-level systems.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.asset import AssetColumn, AssetRelation, AssetTable
from ..models.asset_system import AssetDataSource, AssetSystem

# Canonical first-level business systems (plan 90)
CANONICAL_SYSTEMS: dict[str, str] = {
    "HIS_SOURCE": "HIS",
    "HRP": "HRP",
    "DATA_CENTER": "数据中心",
    "JHEMR_VASTBASE": "嘉和电子病历",
    "DOCARE": "Docare手术麻醉",
    "MOBILE_NURSING": "移动护理",
    "LIS_SOURCE": "LIS",
    "PACS_SOURCE": "PACS",
    "PAPERLESS_CDMS": "无纸化病案",
    "ULTRASOUND_ENDOSCOPY": "超声内镜",
}

# Old system_code → canonical when physical source is independent (not DATA_CENTER owner)
LEGACY_SYSTEM_MAP: dict[str, str] = {
    "HIS": "HIS_SOURCE",
    "EMR": "JHEMR_VASTBASE",
    "LIS": "LIS_SOURCE",
    "PACS": "PACS_SOURCE",
    "SM": "DOCARE",
    "YDHL": "MOBILE_NURSING",
}

# DATA_CENTER internal owner/schema labels (never first-level systems)
DATA_CENTER_OWNER_CN: dict[str, str] = {
    "HIS": "HIS业务镜像区",
    "ODS": "标准视图区",
    "CDA": "标准字典区",
    "MTL": "老电子病历区",
    "JHEMR": "新电子病历区",
    "YBEMR": "电子病历交换区",
    "YDHL": "移动护理镜像区",
    "SM": "手术麻醉镜像区",
    "LIS": "检验镜像区",
    "PACS": "影像镜像区",
}

# Owners that indicate DATA_CENTER mirror semantics even if system_code is wrong
ODS_MIRROR_OWNERS = set(DATA_CENTER_OWNER_CN.keys()) | {"HRP"}


def normalize_system_code(
    system_code: str | None,
    *,
    source_code: str | None = None,
    schema_name: str | None = None,
    source_kind: str | None = None,
) -> str:
    """Map legacy codes to canonical; keep DATA_CENTER for ODS mirror assets."""
    sc = (system_code or "").strip().upper()
    src = (source_code or "").strip().lower()
    schema = (schema_name or "").strip().upper()
    kind = (source_kind or "").strip().lower()

    # ODS / data-center connections always DATA_CENTER
    # This check intentionally precedes the canonical-code shortcut: legacy
    # ODS aliases may carry an otherwise canonical owner code (for example
    # MOBILE_NURSING + ods_ydhl) but remain nested under DATA_CENTER.
    if sc == "DATA_CENTER" or src.startswith("ods") or "8_216" in src or "8.216" in src:
        return "DATA_CENTER"
    if sc in CANONICAL_SYSTEMS:
        return sc
    # Mirror owner under data center connection must stay DATA_CENTER
    if schema in ODS_MIRROR_OWNERS and (
        src.startswith("ods") or sc in {"", "LIS", "PACS", "SM", "EMR", "YDHL", "MOBILE_NURSING"}
    ):
        if src.startswith("ods") or kind == "legacy_alias":
            return "DATA_CENTER"
    # Independent physical sources: remap legacy
    if sc in LEGACY_SYSTEM_MAP:
        # If this is clearly an ODS alias source, force DATA_CENTER
        if src in {"ods_lis", "ods_pacs", "ods_emr", "ods_ydhl", "ods_sm"} or (
            kind == "legacy_alias" and "ods" in src
        ):
            return "DATA_CENTER"
        return LEGACY_SYSTEM_MAP[sc]
    if not sc:
        if src.startswith("his"):
            return "HIS_SOURCE"
        if "hrp" in src:
            return "HRP"
        if "docare" in src:
            return "DOCARE"
        if "jhemr" in src:
            return "JHEMR_VASTBASE"
        if "lis" in src and "ods" not in src:
            return "LIS_SOURCE"
        if "pacs" in src and "ods" not in src:
            return "PACS_SOURCE"
        if "paperless" in src or "cdms" in src:
            return "PAPERLESS_CDMS"
        if "ultrasound" in src or "endoscop" in src:
            return "ULTRASOUND_ENDOSCOPY"
        if "mobile" in src or "ydhl" in src or "nursing" in src:
            if "ods" in src:
                return "DATA_CENTER"
            return "MOBILE_NURSING"
        if src.startswith("ods"):
            return "DATA_CENTER"
    return sc or "UNKNOWN"


def load_system_name_map(db: Session) -> dict[str, str]:
    """system_code -> system_name_cn from DB, with canonical fallbacks."""
    names = dict(CANONICAL_SYSTEMS)
    for row in db.scalars(select(AssetSystem)).all():
        code = (row.system_code or "").strip().upper()
        if not code:
            continue
        cn = (row.system_name_cn or "").strip()
        if cn:
            names[code] = cn
        elif code in CANONICAL_SYSTEMS:
            names[code] = CANONICAL_SYSTEMS[code]
    return names


def system_name_cn(db: Session, system_code: str | None) -> str:
    code = normalize_system_code(system_code)
    names = load_system_name_map(db)
    return names.get(code) or code or "未知系统"


def is_first_level_business_system(system_code: str | None) -> bool:
    return normalize_system_code(system_code) in CANONICAL_SYSTEMS


def owner_display_cn(schema_name: str | None, *, parent_system: str | None = None) -> str | None:
    schema = (schema_name or "").strip().upper()
    if not schema:
        return None
    if normalize_system_code(parent_system) == "DATA_CENTER":
        return DATA_CENTER_OWNER_CN.get(schema)
    return None


def classify_for_tree(
    system_code: str | None,
    source_code: str | None,
    *,
    source_kind: str | None = None,
    source_name_cn: str | None = None,
    schema_name: str | None = None,
    system_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return first-level business system identity for tree/list APIs.

    No external_business / platform_asset presentation groups for UI.
    """
    canonical = normalize_system_code(
        system_code, source_code=source_code, schema_name=schema_name, source_kind=source_kind
    )
    names = system_names or dict(CANONICAL_SYSTEMS)
    name = names.get(canonical) or CANONICAL_SYSTEMS.get(canonical) or source_name_cn or canonical
    catalog_ok = canonical in CANONICAL_SYSTEMS
    return {
        "system_code": canonical,
        "system_name_cn": name,
        # legacy fields kept null/empty so UI must not show old categories
        "system_category": None if catalog_ok else "catalog_anomaly",
        "system_category_cn": None if catalog_ok else "目录异常",
        "source_system": canonical.lower(),
        "source_system_cn": name,
        "catalog_ok": catalog_ok,
    }


def list_first_level_systems(db: Session, *, include_merged: bool = False) -> list[dict[str, Any]]:
    names = load_system_name_map(db)
    rows = db.scalars(select(AssetSystem).order_by(AssetSystem.system_code)).all()
    by_code = { (r.system_code or "").upper(): r for r in rows if r.system_code }

    # First-level UI follows real catalog rows and physical connections. Do not
    # manufacture a system merely because its code exists in a Python constant.
    result = []
    for code, default_cn in CANONICAL_SYSTEMS.items():
        row = by_code.get(code)
        if row is None:
            continue
        status = (row.status if row else "active") or "active"
        if not include_merged and status.lower() in {"merged", "deleted"}:
            continue
        conn_count = db.scalar(
            select(func.count()).where(
                AssetDataSource.system_code == code,
                (AssetDataSource.source_kind.is_(None))
                | (AssetDataSource.source_kind != "legacy_alias"),
            )
        ) or 0
        # include legacy_alias under system for count of physical only above
        table_count = db.scalar(select(func.count()).where(
            AssetTable.system_code == code,
            (AssetTable.row_presence_status.is_(None))
            | (AssetTable.row_presence_status != "confirmed_empty"),
        )) or 0
        if conn_count == 0:
            continue
        result.append({
            "id": row.id if row else None,
            "system_code": code,
            "system_name_cn": names.get(code) or default_cn,
            "system_type": row.system_type if row else None,
            "status": status,
            "target_host": row.target_host if row else None,
            "connection_count": int(conn_count),
            "table_count": int(table_count),
            "is_canonical": True,
            "created_at": row.created_at.isoformat() if row and row.created_at else None,
        })

    # non-canonical active systems → catalog anomaly (admin)
    for code, row in sorted(by_code.items()):
        if code in CANONICAL_SYSTEMS:
            continue
        if code in {"", "PYTEST"} or code.startswith("TEST"):
            continue
        status = (row.status or "active").lower()
        if not include_merged and status in {"merged", "deleted", "inactive"}:
            continue
        result.append({
            "id": row.id,
            "system_code": code,
            "system_name_cn": row.system_name_cn or code,
            "system_type": row.system_type,
            "status": row.status,
            "target_host": row.target_host,
            "connection_count": 0,
            "table_count": int(
                db.scalar(select(func.count()).where(
                    AssetTable.system_code == code,
                    (AssetTable.row_presence_status.is_(None))
                    | (AssetTable.row_presence_status != "confirmed_empty"),
                )) or 0
            ),
            "is_canonical": False,
            "catalog_anomaly": True,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return result


def ensure_canonical_systems(db: Session) -> list[str]:
    """Upsert the ten canonical systems with default Chinese names if missing."""
    created = []
    for code, name in CANONICAL_SYSTEMS.items():
        row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == code))
        if not row:
            db.add(
                AssetSystem(
                    system_code=code,
                    system_name_cn=name,
                    system_type="business",
                    status="active",
                    system_identity_key=code.lower(),
                )
            )
            created.append(code)
        else:
            # do not overwrite human-confirmed names if already Chinese and non-empty
            if not (row.system_name_cn or "").strip():
                row.system_name_cn = name
            if (row.status or "").lower() in {"merged", "inactive", "deleted"} and code in CANONICAL_SYSTEMS:
                # re-activate canonical if marked wrong
                pass
    db.flush()
    return created
