"""L14 周边系统只读接入：在 ODS 上登记 LIS/PACS/EMR/YDHL/SM 逻辑源并采元数据。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.asset_system import AssetDataSource, AssetSystem
from ..models.governance import MetadataSnapshot
from .asset_catalog import CANONICAL_SYSTEMS, normalize_system_code

# 周边系统挂在数据中心 ODS 同一连接上，按 owner 过滤采集（不另连库、不写源库）
PERIPHERAL = [
    {
        "system_code": "LIS",
        "system_name_cn": CANONICAL_SYSTEMS["DATA_CENTER"],
        "system_type": "LIS",
        "source_code": "ods_lis",
        "source_name_cn": "ODS.LIS（数据中心镜像）",
        "schemas": ["LIS"],
        "description_cn": "L14 只读：经 ODS 8.216 采集 LIS owner；凭据复用 ods_8_216",
    },
    {
        "system_code": "PACS",
        "system_name_cn": CANONICAL_SYSTEMS["DATA_CENTER"],
        "system_type": "PACS",
        "source_code": "ods_pacs",
        "source_name_cn": "ODS.PACS（数据中心镜像）",
        "schemas": ["PACS"],
        "description_cn": "L14 只读：经 ODS 8.216 采集 PACS owner",
    },
    {
        "system_code": "EMR",
        "system_name_cn": CANONICAL_SYSTEMS["DATA_CENTER"],
        "system_type": "EMR",
        "source_code": "ods_emr",
        "source_name_cn": "ODS.JHEMR+MTL（数据中心镜像）",
        "schemas": ["JHEMR", "MTL"],
        "description_cn": "L14 只读：新老 EMR owner",
    },
    {
        "system_code": "MOBILE_NURSING",
        "system_name_cn": CANONICAL_SYSTEMS["DATA_CENTER"],
        "system_type": "NURSING",
        "source_code": "ods_ydhl",
        "source_name_cn": "ODS.YDHL（数据中心镜像）",
        "schemas": ["YDHL"],
        "description_cn": "L14 只读：移动护理",
    },
    {
        "system_code": "SM",
        "system_name_cn": CANONICAL_SYSTEMS["DATA_CENTER"],
        "system_type": "OTHER",
        "source_code": "ods_sm",
        "source_name_cn": "ODS.SM（数据中心镜像）",
        "schemas": ["SM"],
        "description_cn": "L14 只读：手麻",
    },
]

ODS_CRED_REF = "file:///etc/data-asset/credentials/ods_8_216"
ODS_HOST = "10.10.8.216"
ODS_PORT = 1521
ODS_SERVICE = "orcl"


def ensure_peripheral_registry(db: Session) -> dict[str, Any]:
    """Idempotent systems + data sources for peripheral owners on ODS."""
    created_sys = 0
    created_src = 0
    for item in PERIPHERAL:
        canonical_code = normalize_system_code(item["system_code"], source_code=item["source_code"], source_kind="legacy_alias")
        canonical_name = CANONICAL_SYSTEMS.get(canonical_code, item["system_name_cn"])
        sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == canonical_code))
        if not sys:
            db.add(
                AssetSystem(
                    system_code=canonical_code,
                    system_name_cn=canonical_name,
                    system_type=item["system_type"],
                    description_cn=item["description_cn"],
                    status="active",
                )
            )
            created_sys += 1
        else:
            # Existing catalog names are authoritative; never let an alias
            # registration overwrite the system overview label.
            if not (sys.system_name_cn or "").strip():
                sys.system_name_cn = canonical_name
            sys.system_type = item["system_type"]
            sys.description_cn = item["description_cn"]
            sys.status = "active"
            sys.updated_at = datetime.now(timezone.utc)

        src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == item["source_code"]))
        if not src:
            db.add(
                AssetDataSource(
                    system_code=canonical_code,
                    source_code=item["source_code"],
                    source_name_cn=item["source_name_cn"],
                    db_type="oracle",
                    host_masked=ODS_HOST,
                    port=ODS_PORT,
                    service_name=ODS_SERVICE,
                    connection_mode="direct",
                    environment="prod",
                    collect_mode="metadata_only",
                    credential_ref=ODS_CRED_REF,
                    description_cn=item["description_cn"] + f"；schema_filter={','.join(item['schemas'])}",
                    enabled=True,
                    last_check_status="registered",
                    last_check_at=datetime.now(timezone.utc),
                )
            )
            created_src += 1
        else:
            src.credential_ref = ODS_CRED_REF
            src.enabled = True
            src.description_cn = item["description_cn"] + f"；schema_filter={','.join(item['schemas'])}"
            src.host_masked = ODS_HOST
            src.port = ODS_PORT
            src.service_name = ODS_SERVICE
            src.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "systems_upserted": len(PERIPHERAL),
        "systems_created": created_sys,
        "sources_created": created_src,
        "credential_ref": ODS_CRED_REF,
        "items": [
            {"system_code": i["system_code"], "source_code": i["source_code"], "schemas": i["schemas"]}
            for i in PERIPHERAL
        ],
    }


def collect_peripheral_metadata(db: Session, *, only_source: str | None = None) -> dict[str, Any]:
    """Live metadata collect per peripheral source (SELECT only on ODS)."""
    from ..api.v1.metadata_changes import _collect_metadata_snapshot

    results = []
    for item in PERIPHERAL:
        if only_source and item["source_code"] != only_source:
            continue
        label = f"l14_{item['source_code']}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
        try:
            snap = _collect_metadata_snapshot(
                item["source_code"],
                label,
                db,
                mode="live_source",
                schema_filter=item["schemas"],
            )
            db.commit()
            # update last_check
            src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == item["source_code"]))
            if src:
                src.last_check_status = "ok"
                src.last_check_at = datetime.now(timezone.utc)
                db.commit()
            results.append({"source_code": item["source_code"], "status": "ok", **snap})
        except Exception as ex:
            db.rollback()
            results.append(
                {
                    "source_code": item["source_code"],
                    "status": "error",
                    "error": f"{type(ex).__name__}:{str(ex)[:200]}",
                }
            )
    return {
        "status": "success",
        "mode": "live_source_readonly",
        "collected": results,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
