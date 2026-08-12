#!/usr/bin/env python3
"""CLI: import 48-item core metrics (dry-run by default).

  python tools/import_core_48_metrics.py
  python tools/import_core_48_metrics.py --apply
  python tools/import_core_48_metrics.py --apply --only 3 4 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write platform DB (needs APP_DB_URL)")
    p.add_argument("--only", nargs="*", type=int, help="metric numbers e.g. 3 4 5")
    p.add_argument("--system-code", default="DATA_CENTER")
    p.add_argument("--source-code", default="ods_8_216")
    args = p.parse_args()

    from app.core.db import SessionLocal
    from app.services.core_metric_import import import_core_metrics

    db = SessionLocal()
    try:
        result = import_core_metrics(
            db,
            dry_run=not args.apply,
            system_code=args.system_code,
            source_code=args.source_code,
            only_numbers=set(args.only) if args.only else None,
            created_by="import_core_48_cli",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
