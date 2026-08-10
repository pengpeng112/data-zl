"""Readonly H7 nightly observation snapshot (plan 125).

Run inside production API container after each 02:00 window:
  docker exec data-asset-api python /app/scripts/ro_identity_nightly_observe.py

Prints only statuses, counts, error classes (masked), watermark times.
Never prints emp nos, names, tokens, or signature bytes.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def main() -> int:
    url = os.environ["APP_DB_URL"]
    if "data_asset_test" in url:
        print(json.dumps({"status": "refused", "error": "refuse_test_db"}))
        return 2
    engine = create_engine(url)
    out: dict = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "provider_env": os.environ.get("APP_IDENTITY_SCHEDULER_PROVIDER"),
        "nightly_env": os.environ.get("APP_IDENTITY_NIGHTLY_ENABLED"),
    }
    with engine.connect() as c:
        runs = c.execute(
            text(
                """
                select run_id, status, last_error_class,
                       left(coalesce(error_message,''), 160) as em,
                       started_at, finished_at
                from asset.asset_identity_scheduler_runs
                order by id desc limit 5
                """
            )
        ).mappings().all()
        out["recent_runs"] = [
            {
                "run_id": (r["run_id"] or "")[:32],
                "status": r["status"],
                "last_error_class": r["last_error_class"],
                "error_prefix": (r["em"] or "").replace("\n", " ")[:160],
                "started_at": str(r["started_at"])[:19] if r["started_at"] else None,
                "has_typeerror": "TypeError" in (r["em"] or "")
                or "offset-naive" in (r["em"] or ""),
            }
            for r in runs
        ]
        subs = c.execute(
            text(
                """
                select run_id, subtask_code, status, planned_count, succeeded_count,
                       failed_count, skipped_count
                from asset.asset_identity_sync_subtasks
                order by id desc limit 10
                """
            )
        ).mappings().all()
        out["recent_subtasks"] = [
            {
                "run_id": (s["run_id"] or "")[:32],
                "subtask_code": s["subtask_code"],
                "status": s["status"],
                "planned": s["planned_count"],
                "ok": s["succeeded_count"],
                "fail": s["failed_count"],
                "skip": s["skipped_count"],
            }
            for s in subs
        ]
        out["alerts_3d"] = c.execute(
            text(
                "select count(*) from asset.asset_identity_sync_alerts "
                "where created_at > now() - interval '3 days'"
            )
        ).scalar()
        wms = c.execute(
            text(
                "select watermark_key, watermark_status, last_run_at "
                "from asset.asset_identity_sync_watermarks order by 1"
            )
        ).mappings().all()
        out["watermarks"] = [
            {
                "key": w["watermark_key"],
                "status": w["watermark_status"],
                "last_run_at": str(w["last_run_at"])[:19] if w["last_run_at"] else None,
            }
            for w in wms
        ]
        # Post-fix windows: count 02:00-ish runs after signature125 publish day
        out["post_fix_night_runs"] = c.execute(
            text(
                """
                select count(*) from asset.asset_identity_scheduler_runs
                where started_at >= timestamptz '2026-08-11 00:00:00+08'
                  and triggered_by is distinct from 'unused'
                  and (run_id like 'RUN-%' or triggered_by like '%cron%' or run_id like 'NTL%')
                """
            )
        ).scalar()
    # import gate
    try:
        from PIL import Image  # noqa: F401
        from app.services.identity_time import is_after_modified_watermark
        from datetime import datetime as dt

        out["runtime"] = {
            "pillow": True,
            "tz_compare_ok": bool(
                is_after_modified_watermark(
                    dt(2026, 8, 10, 2, 0),
                    dt(2026, 8, 9, 18, 0, tzinfo=timezone.utc),
                    "B",
                    "A",
                )
            ),
        }
    except Exception as exc:
        out["runtime"] = {"error": type(exc).__name__}

    latest = out["recent_runs"][0] if out["recent_runs"] else {}
    out["h7_gates"] = {
        "no_typeerror_on_latest": not bool(latest.get("has_typeerror")),
        "pillow_present": bool((out.get("runtime") or {}).get("pillow")),
        "tz_helper_ok": bool((out.get("runtime") or {}).get("tz_compare_ok")),
        "post_fix_night_runs": out.get("post_fix_night_runs"),
        "need_three_nights": int(out.get("post_fix_night_runs") or 0) >= 3,
    }
    print(json.dumps(out, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
