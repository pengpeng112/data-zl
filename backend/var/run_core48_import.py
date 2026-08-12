from pathlib import Path
from app.core.db import SessionLocal
from app.services.core_metric_import import import_core_metrics

db = SessionLocal()
try:
    r = import_core_metrics(
        db,
        sql_dir=Path("/app/var/core48_sql"),
        dry_run=False,
        created_by="prod_import_core48",
    )
    print("count", r["count"])
    print("active_m", sum(1 for i in r["items"] if i.get("metric", {}).get("status") == "active"))
    print("active_q", sum(1 for i in r["items"] if i.get("query", {}).get("status") == "active"))
    print("sample", [(i["metric_code"], i["title"]) for i in r["items"][:5]])
finally:
    db.close()
