"""Readonly H7 nightly observation snapshot (plan 125).

Run inside production API container after each 02:00 window:
  docker exec data-asset-api python /app/scripts/ro_identity_nightly_observe.py

Prints only statuses, counts, error classes (masked), watermark times.
Never prints emp nos, names, tokens, or signature bytes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

DEFAULT_OBSERVE_SINCE = "2026-08-11T00:00:00+08:00"


def parse_observation_since(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--since must include an explicit timezone offset")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only identity nightly H7 observation")
    parser.add_argument(
        "--since",
        default=os.environ.get("APP_H7_OBSERVE_SINCE", DEFAULT_OBSERVE_SINCE),
        help="ISO-8601 start of the post-fix observation window, including timezone",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        observe_since = parse_observation_since(args.since)
    except ValueError as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}))
        return 2

    url = os.environ["APP_DB_URL"]
    database_name = (make_url(url).database or "").lower()
    if database_name != "data_asset":
        print(json.dumps({"status": "refused", "error": "refuse_non_production_db"}))
        return 2
    engine = create_engine(url)
    out: dict = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "observation_since": observe_since.isoformat(),
        "provider_env": os.environ.get("APP_IDENTITY_SCHEDULER_PROVIDER"),
        "nightly_env": os.environ.get("APP_IDENTITY_NIGHTLY_ENABLED"),
    }
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
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
                "has_error": bool(r["em"]),
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
        # Count runs and successful calendar nights in the explicit observation
        # window. The date is evaluated in the hospital timezone so multiple
        # retries in one night cannot be misreported as multiple observed nights.
        night_counts = c.execute(
            text(
                """
                select count(*) as run_count,
                       count(distinct (started_at at time zone 'Asia/Shanghai')::date)
                           filter (where status = 'success') as success_nights
                from asset.asset_identity_scheduler_runs
                where started_at >= :observe_since
                  and triggered_by is distinct from 'unused'
                  and (run_id like 'RUN-%' or triggered_by like '%cron%' or run_id like 'NTL%')
                """
            ),
            {"observe_since": observe_since},
        ).mappings().one()
        out["post_fix_night_runs"] = int(night_counts["run_count"] or 0)
        out["post_fix_success_nights"] = int(night_counts["success_nights"] or 0)
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
        "post_fix_success_nights": out.get("post_fix_success_nights"),
        "need_three_nights": int(out.get("post_fix_success_nights") or 0) >= 3,
    }
    print(json.dumps(out, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
