from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.asset import AssetTable, AssetColumn
from ...models.asset_system import AssetDataSource, AssetSystem
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["systems"])


class SystemUpsert(BaseModel):
    system_code: str
    system_name_cn: str
    system_name_en: str | None = None
    system_type: str | None = None
    owner_department: str | None = None
    description_cn: str | None = None
    status: str | None = "active"


class DataSourceUpsert(BaseModel):
    system_code: str
    source_code: str
    source_name_cn: str
    db_type: str | None = None
    host_masked: str | None = None
    port: int | None = None
    service_name: str | None = None
    database_name: str | None = None
    connection_mode: str | None = None
    environment: str | None = None
    collect_mode: str | None = "metadata_only"
    credential_ref: str | None = None
    write_credential_ref: str | None = None
    description_cn: str | None = None
    enabled: bool = True


# ── 系统 ──

@router.get("/systems", summary="系统列表")
def list_systems(
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetSystem).order_by(AssetSystem.system_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "system_code": r.system_code,
            "system_name_cn": r.system_name_cn,
            "system_type": r.system_type, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ])


@router.put("/systems", summary="新增/更新系统")
def upsert_system(req: SystemUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if existing:
        existing.system_name_cn = req.system_name_cn
        existing.system_name_en = req.system_name_en
        existing.system_type = req.system_type
        existing.owner_department = req.owner_department
        existing.description_cn = req.description_cn
        existing.status = req.status
        existing.updated_at = datetime.now(timezone.utc)
        sys = existing
    else:
        sys = AssetSystem(
            system_code=req.system_code,
            system_name_cn=req.system_name_cn,
            system_name_en=req.system_name_en,
            system_type=req.system_type,
            owner_department=req.owner_department,
            description_cn=req.description_cn,
            status=req.status or "active",
        )
        db.add(sys)
    db.commit()
    db.refresh(sys)
    return ApiResponse(data={"id": sys.id, "system_code": sys.system_code})


@router.post("/sources/peripheral/bootstrap", summary="L14 登记周边系统并可选活库元数据采集（只读）")
def bootstrap_peripheral_sources(
    collect: bool = Query(True, description="是否立即对各 owner 做 live 元数据采集"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...services.peripheral_sources import collect_peripheral_metadata, ensure_peripheral_registry

    reg = ensure_peripheral_registry(db)
    out: dict = {"registry": reg, "collect": None}
    if collect:
        out["collect"] = collect_peripheral_metadata(db)
    return ApiResponse(data=out)


@router.delete("/systems/{system_code}", summary="删除系统")
def delete_system(system_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys:
        raise HTTPException(status_code=404)
    # remove referencing sources first
    refs = db.scalars(select(AssetDataSource).where(AssetDataSource.system_code == system_code)).all()
    for r in refs:
        db.delete(r)
    db.delete(sys)
    db.commit()
    return ApiResponse(data={"deleted": system_code})


# ── 数据源 ──

@router.get("/sources", summary="数据源列表")
def list_sources(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetDataSource)
    if system_code:
        stmt = stmt.where(AssetDataSource.system_code == system_code)
    rows = db.scalars(stmt.order_by(AssetDataSource.source_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "system_code": r.system_code,
            "source_code": r.source_code, "source_name_cn": r.source_name_cn,
            "db_type": r.db_type, "environment": r.environment,
            "collect_mode": r.collect_mode,
            "enabled": r.enabled, "last_check_status": r.last_check_status,
        }
        for r in rows
    ])


@router.put("/sources", summary="新增/更新数据源")
def upsert_source(req: DataSourceUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if not sys:
        raise HTTPException(status_code=400, detail=f"系统 {req.system_code} 不存在，请先创建系统")
    existing = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == req.source_code))
    if existing:
        existing.system_code = req.system_code
        existing.source_name_cn = req.source_name_cn
        existing.db_type = req.db_type
        existing.host_masked = req.host_masked
        existing.port = req.port
        existing.service_name = req.service_name
        existing.database_name = req.database_name
        existing.connection_mode = req.connection_mode
        existing.environment = req.environment
        existing.collect_mode = req.collect_mode
        existing.credential_ref = req.credential_ref
        existing.write_credential_ref = req.write_credential_ref
        existing.description_cn = req.description_cn
        existing.enabled = req.enabled
        existing.updated_at = datetime.now(timezone.utc)
        ds = existing
    else:
        ds = AssetDataSource(
            system_code=req.system_code,
            source_code=req.source_code,
            source_name_cn=req.source_name_cn,
            db_type=req.db_type,
            host_masked=req.host_masked,
            port=req.port,
            service_name=req.service_name,
            database_name=req.database_name,
            connection_mode=req.connection_mode,
            environment=req.environment,
            collect_mode=req.collect_mode or "metadata_only",
            credential_ref=req.credential_ref,
            write_credential_ref=req.write_credential_ref,
            description_cn=req.description_cn,
            enabled=req.enabled,
        )
        db.add(ds)
    db.commit()
    db.refresh(ds)
    return ApiResponse(data={"id": ds.id, "source_code": ds.source_code})


@router.post("/sources/{source_code}/check", summary="数据源连通性检测")
def check_source(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)

    try:
        from ...services.db_connectors import DB_CONNECTOR_MAP
        from ...services.credentials import resolve
        user, pwd = resolve(ds.credential_ref)
        connector_cls = DB_CONNECTOR_MAP.get(ds.db_type or "oracle")
        if not connector_cls:
            ds.last_check_status = "unsupported"
            ds.last_check_at = datetime.now(timezone.utc)
            db.commit()
            return ApiResponse(data={"source_code": ds.source_code, "status": "unsupported", "message": f"不支持的数据库类型: {ds.db_type}"})

        connector = connector_cls(
            host=ds.host_masked or "localhost", port=ds.port or 1521,
            database=ds.database_name or ds.service_name or "",
            user=user or "", password=pwd or "",
            connection_mode=ds.connection_mode or "direct",
        )
        ok, msg, elapsed_ms = connector.test_connectivity()
        ds.last_check_status = "connected" if ok else "failed"
        ds.last_check_at = datetime.now(timezone.utc)
        db.commit()
        return ApiResponse(data={
            "source_code": ds.source_code,
            "status": "connected" if ok else "failed",
            "message": msg,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as e:
        ds.last_check_status = "failed"
        ds.last_check_at = datetime.now(timezone.utc)
        db.commit()
        return ApiResponse(data={"source_code": ds.source_code, "status": "failed", "message": str(e)[:200], "elapsed_ms": 0})


@router.delete("/sources/{source_code}", summary="删除数据源")
def delete_source(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    db.delete(ds)
    db.commit()
    return ApiResponse(data={"deleted": source_code})


# ── 资产树（五层：系统大类 -> 系统/库 -> schema -> 表 -> 字段） ──

_CATEGORY_CN = {
    "ods_center": "ODS 数据中心系统",
    "his_source": "HIS 源端系统",
    "hrp_source": "HRP 源端系统",
    "external_business": "其他业务系统",
    "platform_asset": "平台元数据系统",
}

_SOURCE_SYSTEM_CN = {
    "ods_his": "HIS 抽取区",
    "ods_lis": "LIS 抽取区",
    "ods_pacs": "PACS 抽取区",
    "ods_emr": "EMR/病历抽取区",
    "ods_ydhl": "移动护理抽取区",
    "ods_sm": "手麻抽取区",
    "ods_cda": "CDA/标准字典区",
    "ods_other": "其他抽取区",
    "his_prod": "HIS 业务库",
    "hrp": "HRP 源端",
    "lis": "检验 LIS",
    "pacs": "影像 PACS",
    "emr": "电子病历",
    "mobile_nursing": "移动护理",
    "sm": "手麻",
    "platform": "平台 asset",
}


def _classify_asset_source(system_code: str | None, source_code: str | None) -> tuple[str, str, str, str]:
    """Return (system_category, category_cn, source_system, source_system_cn)."""
    sc = (system_code or "").upper()
    src = (source_code or "").lower()

    if sc == "HIS_SOURCE" or "his_source" in src or src.startswith("his_"):
        return "his_source", _CATEGORY_CN["his_source"], "his_prod", _SOURCE_SYSTEM_CN["his_prod"]
    if sc == "HRP" or "hrp" in src:
        return "hrp_source", _CATEGORY_CN["hrp_source"], "hrp", _SOURCE_SYSTEM_CN["hrp"]
    if sc == "LIS" or src.endswith("_lis") or src == "ods_lis":
        cat = "external_business" if sc == "LIS" else "ods_center"
        if cat == "ods_center":
            return cat, _CATEGORY_CN[cat], "ods_lis", _SOURCE_SYSTEM_CN["ods_lis"]
        return cat, _CATEGORY_CN[cat], "lis", _SOURCE_SYSTEM_CN["lis"]
    if sc == "PACS" or src.endswith("_pacs") or src == "ods_pacs":
        if sc == "PACS":
            return "external_business", _CATEGORY_CN["external_business"], "pacs", _SOURCE_SYSTEM_CN["pacs"]
        return "ods_center", _CATEGORY_CN["ods_center"], "ods_pacs", _SOURCE_SYSTEM_CN["ods_pacs"]
    if sc == "EMR" or src.endswith("_emr") or src == "ods_emr":
        if sc == "EMR":
            return "external_business", _CATEGORY_CN["external_business"], "emr", _SOURCE_SYSTEM_CN["emr"]
        return "ods_center", _CATEGORY_CN["ods_center"], "ods_emr", _SOURCE_SYSTEM_CN["ods_emr"]
    if sc in ("MOBILE_NURSING", "YDHL") or "ydhl" in src:
        if sc in ("MOBILE_NURSING", "YDHL"):
            return "external_business", _CATEGORY_CN["external_business"], "mobile_nursing", _SOURCE_SYSTEM_CN["mobile_nursing"]
        return "ods_center", _CATEGORY_CN["ods_center"], "ods_ydhl", _SOURCE_SYSTEM_CN["ods_ydhl"]
    if sc == "SM" or src.endswith("_sm") or src == "ods_sm":
        if sc == "SM":
            return "external_business", _CATEGORY_CN["external_business"], "sm", _SOURCE_SYSTEM_CN["sm"]
        return "ods_center", _CATEGORY_CN["ods_center"], "ods_sm", _SOURCE_SYSTEM_CN["ods_sm"]
    if sc == "DATA_CENTER" or src.startswith("ods") or "8_216" in src:
        if "cda" in src:
            return "ods_center", _CATEGORY_CN["ods_center"], "ods_cda", _SOURCE_SYSTEM_CN["ods_cda"]
        # 主 ODS 汇聚源：按表 namespace 在前端再分；树节点先标 his 抽取区为主入口
        if src in ("ods_8_216",) or "ods" in src:
            return "ods_center", _CATEGORY_CN["ods_center"], "ods_his", _SOURCE_SYSTEM_CN["ods_his"]
        return "ods_center", _CATEGORY_CN["ods_center"], "ods_other", _SOURCE_SYSTEM_CN["ods_other"]
    return "platform_asset", _CATEGORY_CN["platform_asset"], "platform", _SOURCE_SYSTEM_CN["platform"]


@router.get("/assets/tree", summary="系统大类 -> 系统/库 -> schema -> 表 树（字段在前端懒加载）")
def assets_tree(
    system_code: str | None = Query(None),
    system_category: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    sources_stmt = select(AssetDataSource)
    if system_code:
        sources_stmt = sources_stmt.where(AssetDataSource.system_code == system_code)
    sources = {s.source_code: s for s in db.scalars(sources_stmt).all()}

    tables = db.scalars(select(AssetTable)).all()

    grouped: dict[str, dict] = {}
    for t in tables:
        sc = t.source_code or "DATA_CENTER"
        ns = t.namespace_name or t.schema_name or ""
        if sc not in grouped:
            grouped[sc] = {"schemas": {}}
        if ns not in grouped[sc]["schemas"]:
            grouped[sc]["schemas"][ns] = []
        # ODS 主源按 owner 再映射 source_system，便于五层第二层拆分
        owner_hint = (ns or "").upper()
        grouped[sc]["schemas"][ns].append({
            "id": t.id,
            "table_name": t.table_name,
            "table_name_cn": t.table_name_cn,
            "column_count": t.column_count,
            "domain": t.domain,
            "owner_hint": owner_hint,
        })

    tree = []
    for sc, sc_data in sorted(grouped.items()):
        ds = sources.get(sc)
        sys_code = ds.system_code if ds else "DATA_CENTER"
        cat, cat_cn, src_sys, src_sys_cn = _classify_asset_source(sys_code, sc)
        # 主 ODS 汇聚：按 namespace 拆分到抽取区
        if sc in ("ods_8_216",) or (sys_code == "DATA_CENTER" and "216" in sc):
            by_zone: dict[str, dict] = {}
            for ns, tbls in sc_data["schemas"].items():
                zone = _ods_owner_zone(ns)
                if zone not in by_zone:
                    by_zone[zone] = {"schemas": {}}
                by_zone[zone]["schemas"][ns] = tbls
            for zone, zdata in sorted(by_zone.items()):
                z_cn = _SOURCE_SYSTEM_CN.get(zone, zone)
                node = {
                    "source_code": sc,
                    "source_name_cn": (ds.source_name_cn if ds else sc) + f" / {z_cn}",
                    "system_code": sys_code,
                    "system_category": cat,
                    "system_category_cn": cat_cn,
                    "source_system": zone,
                    "source_system_cn": z_cn,
                    "schemas": [],
                    "table_count": sum(len(v) for v in zdata["schemas"].values()),
                }
                for ns, tbls in sorted(zdata["schemas"].items()):
                    node["schemas"].append({
                        "namespace": ns,
                        "tables": tbls,
                        "table_count": len(tbls),
                    })
                if system_category and node["system_category"] != system_category:
                    continue
                tree.append(node)
            continue

        node = {
            "source_code": sc,
            "source_name_cn": ds.source_name_cn if ds else sc,
            "system_code": sys_code,
            "system_category": cat,
            "system_category_cn": cat_cn,
            "source_system": src_sys,
            "source_system_cn": src_sys_cn,
            "schemas": [],
            "table_count": sum(len(v) for v in sc_data["schemas"].values()),
        }
        for ns, tbls in sorted(sc_data["schemas"].items()):
            node["schemas"].append({
                "namespace": ns,
                "tables": tbls,
                "table_count": len(tbls),
            })
        if system_category and node["system_category"] != system_category:
            continue
        tree.append(node)

    return ApiResponse(data=tree)


def _ods_owner_zone(namespace: str) -> str:
    owner = (namespace or "").upper()
    if owner in ("HIS",) or owner.startswith("HIS"):
        return "ods_his"
    if owner == "LIS":
        return "ods_lis"
    if owner == "PACS":
        return "ods_pacs"
    if owner in ("JHEMR", "MTL", "YBEMR"):
        return "ods_emr"
    if owner == "YDHL":
        return "ods_ydhl"
    if owner == "SM":
        return "ods_sm"
    if owner == "CDA":
        return "ods_cda"
    return "ods_other"
