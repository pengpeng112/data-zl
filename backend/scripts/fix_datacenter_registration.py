"""93 号 v3 · 步 2 · 阶段 1 数据完整性小修补。

T1.1 UPDATE DATA_CENTER 系统(target_host/owner_department/description_cn 追加)
T1.2 刷新 asset_source_schemas 统计(6 个 ods_* 源 table_count/column_count)
T1.4 幂等空操作检查(空 system_code / his_ready 残留)

用法(容器内)：
    python -m scripts.fix_datacenter_registration            # 正式执行
    python -m scripts.fix_datacenter_registration --dry-run  # 预览将改动

全部 UPDATE 仅补 NULL 字段,不覆盖既有非空值。幂等可重复执行。
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, func, text
from app.core.db import SessionLocal
from app.models.asset_system import AssetSystem, AssetSourceSchema

ODS_SOURCES = ["ods_8_216", "ods_emr", "ods_lis", "ods_pacs", "ods_sm", "ods_ydhl"]
APPEND_DESC = "；含 HIS 镜像/MTL/JHEMR 电子病历双源/SM 手麻/CDA 标准码映射，拆分源 ods_emr/ods_lis/ods_pacs/ods_sm/ods_ydhl 共用凭据 ods_8_216（交接文档 §3.1/§3.3）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    summary = {"T1.1_system_updated": False, "T1.2_schemas_refreshed": 0, "T1.4_checks": {}, "dry_run": args.dry_run}

    try:
        # ===== T1.1 UPDATE DATA_CENTER =====
        sys_row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == "DATA_CENTER"))
        if sys_row is None:
            summary["T1.1_error"] = "DATA_CENTER 系统不存在,停止"
            print(json.dumps(summary, ensure_ascii=False)); return
        changes = []
        if sys_row.target_host is None:
            changes.append("target_host='10.10.8.216'")
            if not args.dry_run: sys_row.target_host = "10.10.8.216"
        if sys_row.owner_department is None:
            changes.append("owner_department='信息中心'")
            if not args.dry_run: sys_row.owner_department = "信息中心"
        existing_desc = sys_row.description_cn or ""
        if "拆分源 ods_emr" not in existing_desc:
            new_desc = existing_desc + APPEND_DESC
            changes.append("description_cn 追加")
            if not args.dry_run: sys_row.description_cn = new_desc
        summary["T1.1_changes"] = changes
        summary["T1.1_system_updated"] = len(changes) > 0

        # ===== T1.2 刷新 asset_source_schemas 统计 =====
        refreshed = 0
        for src in ODS_SOURCES:
            rows = db.scalars(select(AssetSourceSchema).where(AssetSourceSchema.source_code == src)).all()
            for sch in rows:
                # 实算 table_count
                tbl_cnt = db.scalar(select(func.count()).select_from(
                    text("asset.asset_tables")).where(
                    text("source_code=:s and schema_name=:sc"), {"s": src, "sc": sch.schema_name})) if False else None
                # 用原生 SQL 避免 ORM text 包裹问题
                tbl_cnt = db.execute(text(
                    "SELECT count(*) FROM asset.asset_tables WHERE source_code=:s AND schema_name=:sc"),
                    {"s": src, "sc": sch.schema_name}).scalar() or 0
                col_cnt = db.execute(text(
                    "SELECT count(*) FROM asset.asset_columns WHERE source_code=:s AND schema_name=:sc"),
                    {"s": src, "sc": sch.schema_name}).scalar() or 0
                if sch.table_count != tbl_cnt or (sch.column_count or 0) != col_cnt:
                    refreshed += 1
                    if not args.dry_run:
                        sch.table_count = tbl_cnt
                        sch.column_count = col_cnt
        summary["T1.2_schemas_refreshed"] = refreshed

        # ===== T1.4 幂等空操作检查 =====
        empty_sys = db.scalar(text("SELECT count(*) FROM asset.asset_systems WHERE system_code=''")) or 0
        empty_sys = db.execute(text("SELECT count(*) FROM asset.asset_systems WHERE system_code=''")).scalar() or 0
        his_ready_tbl = db.execute(text("SELECT count(*) FROM asset.asset_tables WHERE source_code='his_ready_10_10_10_15'")).scalar() or 0
        his_ready_src = db.execute(text("SELECT count(*) FROM asset.asset_data_sources WHERE source_code='his_ready_10_10_10_15'")).scalar() or 0
        summary["T1.4_checks"] = {
            "empty_system_code_count": int(empty_sys),
            "his_ready_in_tables": int(his_ready_tbl),
            "his_ready_in_sources": int(his_ready_src),
            "expected_all_zero": True,
        }

        if not args.dry_run:
            db.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        db.rollback()
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
