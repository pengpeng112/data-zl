# -*- coding: utf-8 -*-
"""170：把生产展示数据重灌隔离库（data_asset_test）+ 重建验收 token。
先清目标表（pytest 夹具清库后的重建），再批量插入。
"""
import json
from pathlib import Path

from sqlalchemy import text

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.asset_system import AssetDataSource, AssetSystem
from app.models.value_domain import AssetColumnValueDomain
from app.models.governance_base import GovernAuditLog

BASE = Path(r"F:\python\数据资产")
OUT = BASE / "开发起步包" / "output_r170"

with open(OUT / "export170.json", encoding="utf-8") as f:
    data = json.load(f)
with open(BASE / "verify" / "round-3" / "graph_data_export.json", encoding="utf-8") as f:
    graph = json.load(f)

db = SessionLocal()

# 清空（重新灌入；顺序无关——asset schema 无硬外键）
for t in [
    "asset_govern_audit_logs", "asset_column_value_domain_evidences",
    "asset_column_value_domain_versions", "asset_column_value_domains",
    "asset_quality_rules", "asset_relations", "asset_columns", "asset_tables",
    "asset_data_sources", "asset_systems",
]:
    try:
        db.execute(text(f"DELETE FROM asset.{t}"))
    except Exception as exc:  # noqa: BLE001
        print("skip-clear", t, str(exc)[:80])
db.commit()


def insert(model, rows):
    objs = [model(**r) for r in rows]
    for i in range(0, len(objs), 5000):
        db.add_all(objs[i:i + 5000])
        db.commit()
    return len(objs)


n_sys = insert(AssetSystem, data["systems"])
n_src = insert(AssetDataSource, data["sources"])
n_tbl = insert(AssetTable, graph["tables"])
n_rel = insert(AssetRelation, graph["relations"])
n_col = insert(AssetColumn, data["columns"])
n_vd = insert(AssetColumnValueDomain, data["value_domains"])
n_audit = insert(GovernAuditLog, data["audit"])

# 质量规则（模型名与隔离库端一致；失败不阻断）
n_qr = 0
try:
    import importlib
    qm_name = data.get("_quality_model", "")
    import app.models.quality as qm
    if qm_name and qm_name not in ("NOT_FOUND",) and not qm_name.startswith("ERR"):
        rule_model = getattr(qm, qm_name)
        n_qr = insert(rule_model, data["quality_rules"])
except Exception as exc:  # noqa: BLE001
    print("quality import ERR", str(exc)[:120])

# 验收 token + platform_admin 绑定
import hashlib

from sqlalchemy import select

from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetUserRole

TOKEN = "verify-token-graph-r3-0001"
USER = "verify-graph-r3"
if not db.scalar(select(AssetRole).where(AssetRole.role_code == "platform_admin")):
    db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
if not db.scalar(select(AssetUserRole).where(
    AssetUserRole.user_identifier == USER, AssetUserRole.role_code == "platform_admin"
)):
    db.add(AssetUserRole(user_identifier=USER, role_code="platform_admin", status="active"))
th = hashlib.sha256(TOKEN.encode()).hexdigest()
ex = db.query(ApiKey).filter(ApiKey.key_name == "verify-graph-r3").first()
if not ex:
    db.add(ApiKey(key_name="verify-graph-r3", token_hash=th, user_identifier=USER))
else:
    ex.token_hash = th
    ex.user_identifier = USER
    ex.enabled = True
db.commit()

# 重灌带显式 id 插行但序列仍停在旧值：末尾对 asset schema 全部自增列
# setval(seq, max(id), true)，否则后续写审计端点全部撞主键 500（173 P1-1）。
# setval 后立即对账 last_value >= max(id)，不齐则 RAISE 让重灌整体失败。
db.execute(text("""
    DO $$
    DECLARE
        r record;
        v_max bigint;
        v_last bigint;
        v_seq text;
        v_done boolean;
    BEGIN
        FOR r IN
            SELECT format('%I.%I', table_schema, table_name) AS tbl, column_name
            FROM information_schema.columns
            WHERE table_schema = 'asset'
              AND (column_default LIKE 'nextval(%' OR is_identity = 'YES')
        LOOP
            v_done := false;
            BEGIN
                v_seq := pg_get_serial_sequence(r.tbl, r.column_name);
                IF v_seq IS NOT NULL THEN
                    EXECUTE format('SELECT greatest(coalesce(max(%I), 0), 1) FROM %s',
                                   r.column_name, r.tbl) INTO v_max;
                    EXECUTE format('SELECT setval(%L, %s, true)', v_seq, v_max);
                    v_done := true;
                END IF;
            EXCEPTION WHEN others THEN
                RAISE NOTICE 'skip sequence reset %.%', r.tbl, r.column_name;
            END;
            IF v_done THEN
                EXECUTE format('SELECT last_value FROM %s', v_seq) INTO v_last;
                IF v_last < v_max THEN
                    RAISE EXCEPTION 'sequence behind after reset: % %', r.tbl, r.column_name;
                END IF;
            END IF;
        END LOOP;
    END $$;
"""))
db.commit()
n_seq = db.execute(text("""
    SELECT count(*) FROM information_schema.columns
    WHERE table_schema = 'asset'
      AND (column_default LIKE 'nextval(%' OR is_identity = 'YES')
""")).scalar()
db.close()

print(f"imported: systems={n_sys} sources={n_src} tables={n_tbl} relations={n_rel} "
      f"columns={n_col} value_domains={n_vd} audit={n_audit} quality_rules={n_qr} | "
      f"sequences_reset={n_seq} | token ready")
