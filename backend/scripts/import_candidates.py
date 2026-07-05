r"""Import view dependencies and candidate join edges from CSV into application database.

Location: F:\python\数据资产\开发起步包\数据资产_关系图谱\

Usage:
    cd backend
    python -m scripts.import_candidates
"""

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal
from app.models.lineage import AssetViewDependency
from app.models.candidate import AssetCandidateRelation

CSV_DIR = Path(r"F:\python\数据资产\开发起步包\数据资产_关系图谱")

DEPS_CSV = CSV_DIR / "ods_view_dependencies.csv"
JOIN_CSV = CSV_DIR / "ods_view_join_edges.csv"


def import_view_dependencies():
    if not DEPS_CSV.exists():
        print(f"[SKIP] file not found: {DEPS_CSV}")
        return 0
    rows: list[AssetViewDependency] = []
    with open(DEPS_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                AssetViewDependency(
                    view_name=(r.get("view") or "").strip(),
                    referenced_schema=(r.get("schema") or r.get("referenced_schema") or "").strip(),
                    referenced_table=(r.get("table") or r.get("referenced_table") or "").strip(),
                    alias=(r.get("alias") or "").strip(),
                    source_file="ods_view_dependencies.csv",
                )
            )
    db = SessionLocal()
    try:
        db.add_all(rows)
        db.commit()
    finally:
        db.close()
    return len(rows)


def import_candidate_relations():
    if not JOIN_CSV.exists():
        print(f"[SKIP] file not found: {JOIN_CSV}")
        return 0
    rows: list[AssetCandidateRelation] = []
    with open(JOIN_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                AssetCandidateRelation(
                    from_table=(r.get("from_table") or "").strip(),
                    from_columns=(r.get("from_column") or "").strip(),
                    to_table=(r.get("to_table") or "").strip(),
                    to_columns=(r.get("to_column") or "").strip(),
                    join_condition=(r.get("condition") or "").strip(),
                    source_view=(r.get("view") or "").strip(),
                    source_file="ods_view_join_edges.csv",
                    confidence=(r.get("confidence") or "static").strip(),
                )
            )
    db = SessionLocal()
    try:
        db.add_all(rows)
        db.commit()
    finally:
        db.close()
    return len(rows)


def main():
    deps_count = import_view_dependencies()
    cand_count = import_candidate_relations()
    print(f"[DONE] view dependencies: {deps_count}, candidate relations: {cand_count}")


if __name__ == "__main__":
    main()
