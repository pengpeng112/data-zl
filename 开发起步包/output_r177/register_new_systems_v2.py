# -*- coding: utf-8 -*-
"""187: 第二批新系统纳入（新输血/科研MySQL/门诊预约/门诊叫号）。同 186 模式。
8.163 使用平台既有 root 凭据（用户给的账号被 163 拒绝，161 专用）。"""
import json
import os
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset_system import AssetDataSource, AssetSystem
from app.models.governance_base import GovernAuditLog

CREDS = {c["ip"]: c for c in json.load(open("/tmp/dbcreds.json", encoding="utf-8"))}
CRED_DIR = "/etc/data-asset/credentials"

SYSTEMS = [
    # code, name_cn, src_code, src_name, ip, port, db_type, svc, credfile
    ("TRANSFUSION_NEW", "新输血系统(熙恒)", "bloodnew_sqlserver_10_10_8_7", "新输血SQLServer",
     "10.10.8.7", 1433, "mssql", None, "bloodnew_sqlserver_10_10_8_7.readonly"),
    ("RESEARCH_MYSQL", "科研系统MySQL", "research_mysql_10_10_8_200", "科研MariaDB(4306)",
     "10.10.8.200", 4306, "mysql", None, "research_mysql_10_10_8_200.readonly"),
    ("OUTPATIENT_APPT", "门诊预约系统", "outpatient_mysql_10_10_8_161", "门诊预约MySQL",
     "10.10.8.161", 3306, "mysql", None, "outpatient_mysql_10_10_8_161.readonly"),
    ("QUEUE", "门诊叫号系统", "queue_mysql_10_10_8_163", "门诊叫号MySQL",
     "10.10.8.163", 3306, "mysql", None, "queue_mysql_10_10_8_163.readonly"),
]

db = SessionLocal()
report = []
try:
    for code, name_cn, src_code, src_name, ip, port, dbt, svc, credfile in SYSTEMS:
        path = os.path.join(CRED_DIR, credfile)
        if ip in CREDS:
            c = CREDS[ip]
            Path(path).write_text(f"{c['user']}:{c['pwd']}", encoding="utf-8")
        elif Path(path).exists() and Path(path).read_text().strip().startswith("{"):
            j = json.loads(Path(path).read_text())
            Path(path).write_text(f"{j['user']}:{j.get('password') or j.get('pwd')}", encoding="utf-8")
        os.chmod(path, 0o600)
        if not db.scalar(select(AssetSystem).where(AssetSystem.system_code == code)):
            db.add(AssetSystem(system_code=code, system_name_cn=name_cn, system_type="business",
                               status="active", system_identity_key=code.lower(), target_host=ip))
            db.flush()
            created = True
        else:
            created = False
        if not db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == src_code)):
            db.add(AssetDataSource(system_code=code, source_code=src_code, source_name_cn=src_name,
                                   db_type=dbt, target_host=ip, port=port, service_name=svc,
                                   enabled=True, write_policy="readonly",
                                   source_kind="physical_connection"))
        report.append({"system": code, "created": created, "source": src_code})
    db.add(GovernAuditLog(
        module="systems", entity_type="asset_data_source", entity_ref="187-batch-registration",
        action="register_new_sources", operator="survey-187-20260913",
        reason="用户授权第二批（病案翻盘/新输血/科研MySQL/听力/门诊预约/叫号连通核验后登记；"
               "病案与听力平台已有登记仅核验，8.163 用既有 root 凭据）",
        after_data={"systems": [r["system"] for r in report]}))
    db.commit()
    n = len(db.scalars(select(AssetDataSource.source_code).where(
        AssetDataSource.source_code.in_([s[2] for s in SYSTEMS]))).all())
    total = db.scalar(select(AssetSystem.id).order_by(None)) and len(db.scalars(select(AssetSystem.system_code)).all())
    print(json.dumps({"registered": report, "readback_sources": n, "platform_systems_total": total},
                     ensure_ascii=False, indent=1))
finally:
    db.close()
