"""163 R3-2/3: ECG metadata import (isolated-DB rehearsal) + production dry-run report.

档一边界（163 §5 R3）：仅隔离测试库 apply；生产平台库只允许 --dry-run（只读 diff，
零写入）；生产 apply = W2 等待域（用户放行后带完整门禁链执行）。

复用 139 底座 upsert_tables/upsert_columns（幂等键 (source_code, schema, table[/column])，
include_status 默认 candidate），写一条 GovernAuditLog 汇总。--url 显式覆盖目标库
（供生产 dry-run），绝不写入 --url 指向的生产库（dry-run 分支无任何 db.add/commit）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from app.models.governance_base import GovernAuditLog  # noqa: E402
from app.services.asset_import_upsert import upsert_columns, upsert_tables  # noqa: E402

PACKAGE = _BACKEND_ROOT / "_r163_work" / "ecg_import_package"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_import(package_dir: Path, dry_run: bool, url: str) -> dict:
    """自建 engine/session：目标 URL 显式传入，不经 app.core.db 的全局 engine
    （后者在模块导入时已按 .env 绑定，--url 覆盖对它无效）。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if not url:
        raise SystemExit("target URL is required (--url or APP_TEST_DB_URL)")
    engine = create_engine(url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    objects = _read_csv(package_dir / "objects.csv")
    columns = _read_csv(package_dir / "columns.csv")

    db = Session()
    try:
        table_stats: dict[str, int] = {}
        col_stats: dict[str, int] = {}
        for source_code in sorted({row["source_code"] for row in objects}):
            src_tables = [r for r in objects if r["source_code"] == source_code]
            src_cols = [r for r in columns if r["source_code"] == source_code]
            table_stats[source_code] = upsert_tables(
                db, system_code="ECG", source_code=source_code, tables=src_tables
            )
            col_stats[source_code] = upsert_columns(
                db, system_code="ECG", source_code=source_code, columns=src_cols
            )

        summary = {
            "package": manifest["package"],
            "objects": len(objects),
            "columns": len(columns),
            "expected": manifest["expected"],
            "tables_upsert": table_stats,
            "columns_upsert": col_stats,
            "dry_run": bool(dry_run),
        }
        if dry_run:
            db.rollback()
            return summary

        db.add(GovernAuditLog(
            module="asset_import",
            entity_type="asset_table",
            entity_ref="import:ecg:163R3",
            action="metadata_import",
            after_data={k: v for k, v in summary.items() if k != "expected"},
            operator="ecg_import_163r3",
            reason="163 R3 ECG 收口档一：隔离库演练导入（include_status=candidate，关系候选仅清单文件）",
        ))
        db.commit()
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="163 R3：ECG 元数据导入（隔离库 apply / 生产只读 dry-run）")
    parser.add_argument("--package", default=str(PACKAGE))
    parser.add_argument("--dry-run", action="store_true", help="只读预演：不写库（任何目标库）")
    parser.add_argument("--url", default=os.environ.get("APP_TEST_DB_URL", ""),
                        help="目标库 URL（默认取 APP_TEST_DB_URL；生产 dry-run 显式传入生产 URL）")
    args = parser.parse_args()

    summary = run_import(Path(args.package), dry_run=args.dry_run, url=args.url)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
