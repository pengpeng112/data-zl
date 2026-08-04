"""Run one controlled dictionary-sync outbox worker pass.

This entry point is intentionally separate from FastAPI request handling. It
does not enable a write switch; the service and executor gates remain the
authoritative fail-closed boundary.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal  # noqa: E402
from app.services.dict_sync_worker import dispatch_dict_event, run_worker_once  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    holder = f"dict-sync-{socket.gethostname()}-{os.getpid()}"
    db = SessionLocal()
    try:
        result = run_worker_once(db, holder, lambda event: dispatch_dict_event(db, event), batch_size=args.batch_size)
        print(result)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
