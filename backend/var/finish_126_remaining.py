"""Post-deploy finish: stubs, CSV results, publish data products, seed schedules."""
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.query_asset import AssetQueryDefinition, AssetQueryVersion
from app.models.query_schedule import AssetQuerySchedule
from app.services.data_product_service import publish_core_products
from app.services.metric_result_import import import_all_result_csvs
from app.services.metric_stub_import import import_missing_metric_stubs

# Prefer /app/取数 (docker cp) then monorepo roots.
REPO_CANDIDATES = [Path("/app"), Path("/opt/data-asset")]
_here = Path(__file__).resolve()
if len(_here.parents) >= 3:
    REPO_CANDIDATES.append(_here.parents[2])

db = SessionLocal()
try:
    stubs = import_missing_metric_stubs(db, dry_run=False, created_by="finish_126", refresh_titles=True)
    print("stubs", stubs["count"], "sample", stubs["items"][:3])
except Exception as exc:
    db.rollback()
    print("stubs_err", type(exc).__name__, exc)

try:
    root = next((p for p in REPO_CANDIDATES if (p / "取数").is_dir()), Path("/app"))
    res = import_all_result_csvs(db, dry_run=False, created_by="finish_126", repo_root=root)
    print("results", {"repo_root": str(root), **{k: res[k] for k in ("file_count", "total_inserted", "dry_run")}})
    for it in res.get("items") or []:
        print("  csv", Path(it["csv"]).name, "inserted", it["inserted"], "skipped", it["skipped"])
except Exception as exc:
    db.rollback()
    print("results_err", type(exc).__name__, exc)

try:
    pub = publish_core_products(db, created_by="finish_126")
    db.commit()
    print("products", pub["count"])
except Exception as exc:
    db.rollback()
    print("products_err", type(exc).__name__, exc)

try:
    # seed CORE schedules disabled
    qrows = db.scalars(
        select(AssetQueryVersion).where(
            AssetQueryVersion.is_active.is_(True),
            AssetQueryVersion.query_code.like("QRY_CORE_%"),
        )
    ).all()
    created = 0
    for q in qrows:
        row = db.scalar(select(AssetQuerySchedule).where(AssetQuerySchedule.query_code == q.query_code))
        if not row:
            d = db.scalar(select(AssetQueryDefinition).where(AssetQueryDefinition.query_code == q.query_code))
            row = AssetQuerySchedule(
                query_code=q.query_code,
                source_code=d.source_code if d else None,
                schedule_cron="0 3 * * *",
                enabled=False,
                result_storage="none",
                created_by="finish_126",
            )
            db.add(row)
            created += 1
    db.commit()
    print(
        "schedules_seeded",
        created,
        "global_flag",
        bool(settings.query_schedule_enabled),
    )
except Exception as exc:
    db.rollback()
    print("schedules_err", type(exc).__name__, exc)
finally:
    db.close()
