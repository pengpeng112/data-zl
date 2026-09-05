# -*- coding: utf-8 -*-
"""170：在生产容器内导出「数据资产系统图」所需展示数据（只读）。
输出 /tmp/export170.json（容器内），由外部 docker cp + scp 取回。
"""
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetTable
from app.models.asset_system import AssetDataSource, AssetSystem
from app.models.value_domain import AssetColumnValueDomain
from app.models.governance_base import GovernAuditLog

db = SessionLocal()


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def dump(model, cols=None, order_by=None, limit=None):
    stmt = select(model)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = db.scalars(stmt).all()
    out = []
    for r in rows:
        d = {}
        for c in (cols or [c.name for c in model.__table__.columns]):
            d[c] = _jsonable(getattr(r, c, None))
        out.append(d)
    return out


def cols_of(model):
    return [c.name for c in model.__table__.columns]


data = {
    "systems": dump(AssetSystem),
    "sources": dump(AssetDataSource),
    "columns": dump(AssetColumn, cols=[
        "system_code", "source_code", "namespace_name", "schema_name", "table_name",
        "column_id", "column_name", "data_type", "length", "nullable", "comment",
        "column_name_cn", "business_desc_cn", "value_desc_cn",
    ]),
    "value_domains": dump(AssetColumnValueDomain),
    "audit": dump(GovernAuditLog, order_by=GovernAuditLog.id.desc(), limit=50000),
}

# 质量规则：类名不确定，动态探测
try:
    import app.models.quality as qm
    rule_model = None
    for name in ("AssetQualityRule", "QualityRule"):
        if hasattr(qm, name):
            rule_model = getattr(qm, name)
            break
    if rule_model is None:
        for name in dir(qm):
            if name.startswith("AssetQuality"):
                rule_model = getattr(qm, name)
                break
    if rule_model is not None:
        data["quality_rules"] = dump(rule_model)
        data["_quality_model"] = rule_model.__name__
    else:
        data["quality_rules"] = []
        data["_quality_model"] = "NOT_FOUND"
except Exception as exc:  # noqa: BLE001
    data["quality_rules"] = []
    data["_quality_model"] = f"ERR:{exc}"

db.close()

with open("/tmp/export170.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, default=_jsonable)
print("exported:", {k: (len(v) if isinstance(v, list) else v) for k, v in data.items()})
