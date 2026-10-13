"""207 A2: 质量执行 worker——领取持久运行单并受控执行。

部署形态：平台容器/服务器内常驻进程（ops-runbook）；本机不直连业务源库，
源访问一律经 quality_sql_runner 的受控连接器。租约+心跳+围栏见服务层。

用法（隔离/演示）：
  python scripts/quality_worker_207.py --once            # 领取并执行一批后退出
  python scripts/quality_worker_207.py --interval 30     # 常驻循环
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.db import SessionLocal  # noqa: E402
from app.services import quality_execution_service as qes  # noqa: E402


def run_once(worker_id: str, max_runs: int = 20) -> list[dict]:
    db = SessionLocal()
    executed: list[dict] = []
    try:
        # 先做崩溃恢复式归并：终态子单但父单未归并的（迟到回写后重算）
        qes.promote_waiting_runs(db)
        db.commit()
        for _ in range(max_runs):
            run = qes.claim_next_run(db, worker_id)
            if run is None:
                break
            executed.append(qes.execute_claimed_run(db, run, worker_id=worker_id))
            db.commit()
    finally:
        db.close()
    return executed


def main() -> int:
    ap = argparse.ArgumentParser(description="207 质量执行 worker")
    ap.add_argument("--once", action="store_true", help="执行一批后退出")
    ap.add_argument("--interval", type=int, default=30, help="轮询间隔秒（常驻模式）")
    ap.add_argument("--max-runs", type=int, default=20, help="单轮最大执行数")
    ap.add_argument("--worker-id", default=None)
    args = ap.parse_args()
    worker_id = args.worker_id or f"worker-{uuid.uuid4().hex[:8]}"

    if args.once:
        results = run_once(worker_id, args.max_runs)
        print({"worker": worker_id, "executed": len(results), "results": results})
        return 0
    print({"worker": worker_id, "mode": "loop", "interval": args.interval}, flush=True)
    while True:
        try:
            results = run_once(worker_id, args.max_runs)
            if results:
                print({"worker": worker_id, "executed": len(results)}, flush=True)
        except Exception as exc:  # noqa: BLE001 - 常驻进程不因单轮失败退出
            print(f"[worker] round failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
