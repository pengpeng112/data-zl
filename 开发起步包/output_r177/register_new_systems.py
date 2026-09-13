# -*- coding: utf-8 -*-
"""186: 新系统纳入数据资产管理平台（容器内执行）。
凭据写 /etc/data-asset/credentials/*.readonly（0600，155 先例）；
asset_systems + asset_data_sources 幂等 upsert；一行审计；回读验证。
凭据参数从 /tmp/dbcreds.json 读取（用后删），输出不含密码。"""
import json
import os

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset_system import AssetDataSource, AssetSystem
from app.models.governance_base import GovernAuditLog

CREDS = json.load(open("/tmp/dbcreds.json", encoding="utf-8"))

SYSTEMS = [
    # code, name_cn, source_code, source_name, ip, port, db_type, service, credfile, cred_user
    ("EMERGENCY_CLINIC", "急诊系统(麦迪斯顿)", "emergency_clinic_10_10_10_120", "急诊Oracle主库",
     "10.10.10.120", 1521, "oracle", "clinic", "emergency_clinic_oracle_10_10_10_120.readonly"),
    ("INFECTION_SURVEILLANCE", "医院感染实时监控(杏林)", "infection_10_10_9_45", "院感Oracle",
     "10.10.9.45", 1521, "oracle", "orcl", "infection_oracle_10_10_9_45.readonly"),
    ("ADVERSE_EVENT", "医疗安全不良事件(火龙果)", "adverse_event_10_10_10_50", "不良事件MariaDB",
     "10.10.10.50", 3306, "mysql", None, "adverse_event_mysql_10_10_10_50.readonly"),
    ("MEDICAL_RECORD_MGMT", "病案管理系统(华健)", "mr_mgmt_10_10_10_55", "病案Oracle(ycyl)",
     "10.10.10.55", 1521, "oracle", "ycyl", "mr_mgmt_oracle_10_10_10_55.readonly"),
    ("INTERCONNECT_PROV", "互联互通省平台", "interconnect_10_10_10_5", "互联互通Oracle",
     "10.10.10.5", 1521, "oracle", "orcl", "interconnect_oracle_10_10_10_5.readonly"),
    ("SDDW_TEST", "医保结算测试(山大地纬)", "sddw_test_10_10_10_155", "医保测试MySQL",
     "10.10.10.155", 3306, "mysql", None, "sddw_test_mysql_10_10_10_155.readonly"),
]
# 10.10.10.152 为 SDDW 正式 RAC 第二节点：挂到既有 SDDW 系统（若存在）作为附加数据源
RAC2 = ("sddw_oracle_10_10_10_152", "医保结算正式RAC节点2", "10.10.10.152", 1521, "oracle", "orcl",
        "sddw_oracle_10_10_10_152.readonly")

CRED_DIR = "/etc/data-asset/credentials"
db = SessionLocal()
report = []
try:
    for code, name_cn, src_code, src_name, ip, port, dbt, svc, credfile in SYSTEMS:
        pwd = next(c["pwd"] for c in CREDS if c["ip"] == ip)
        user = next(c["user"] for c in CREDS if c["ip"] == ip)
        path = os.path.join(CRED_DIR, credfile)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{user}:{pwd}")
        os.chmod(path, 0o600)
        sysrow = db.scalar(select(AssetSystem).where(AssetSystem.system_code == code))
        if not sysrow:
            sysrow = AssetSystem(system_code=code, system_name_cn=name_cn, system_type="business",
                                 status="active", system_identity_key=code.lower(),
                                 target_host=ip)
            sysrow.id = None
            db.add(sysrow)
            db.flush()
            created = True
        else:
            created = False
        if not db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == src_code)):
            db.add(AssetDataSource(
                system_code=code, source_code=src_code, source_name_cn=src_name,
                db_type=dbt, target_host=ip, port=port, service_name=svc,
                enabled=True, write_policy="readonly", source_kind="physical_connection",
            ))
        report.append({"system": code, "created": created, "source": src_code, "cred": credfile})
    # SDDW RAC2 附加数据源
    pwd = next(c["pwd"] for c in CREDS if c["ip"] == RAC2[2])
    user = next(c["user"] for c in CREDS if c["ip"] == RAC2[2])
    path = os.path.join(CRED_DIR, RAC2[6])
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{user}:{pwd}")
    os.chmod(path, 0o600)
    sddw = db.scalar(select(AssetSystem).where(AssetSystem.system_code == "SDDW"))
    if sddw and not db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == RAC2[0])):
        db.add(AssetDataSource(
            system_code="SDDW", source_code=RAC2[0], source_name_cn=RAC2[1],
            db_type=RAC2[4], target_host=RAC2[2], port=RAC2[3], service_name=RAC2[5],
            enabled=True, write_policy="readonly", source_kind="physical_connection",
        ))
        report.append({"system": "SDDW", "created": False, "source": RAC2[0], "cred": RAC2[6]})
    else:
        report.append({"system": "SDDW", "note": "system missing or source exists", "source": RAC2[0]})
    db.add(GovernAuditLog(
        module="systems", entity_type="asset_data_source",
        entity_ref="186-batch-registration", action="register_new_sources",
        operator="survey-186-20260913",
        reason="用户授权『纳入数据资产管理系统』（二院服务器及资产清单.xlsx 排查后，仅登记容器实测可登录的新系统，readonly）",
        after_data={"systems": [r.get("system") for r in report]}))
    db.commit()
    # 回读
    total_src = db.scalar(select(AssetDataSource.source_code).where(
        AssetDataSource.source_code.in_([s[2] for s in SYSTEMS] + [RAC2[0]])))
    n = len(db.scalars(select(AssetDataSource.source_code).where(
        AssetDataSource.source_code.in_([s[2] for s in SYSTEMS] + [RAC2[0]]))).all())
    print(json.dumps({"registered": report, "readback_sources": n}, ensure_ascii=False, indent=1))
finally:
    db.close()
