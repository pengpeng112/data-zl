# -*- coding: utf-8 -*-
"""188 night-window sequential driver (runs inside 8.83 container).

Single global queue: one source at a time, wall-clock window guard,
per-night caps (<=3 physical DBs or 2h wall). Reads per-source config JSONs,
invokes harvest_r188_lowload.main via subprocess with env-injected credential
file path (never on argv). Driver-level checkpoint after each source.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))  # Asia/Shanghai


def now_str():
    return datetime.now(TZ).isoformat(timespec="seconds")


def in_window(win):
    if not win:
        return True
    cur = datetime.now(TZ)
    start = datetime.fromisoformat(win["start"]).replace(tzinfo=TZ)
    end = datetime.fromisoformat(win["end"]).replace(tzinfo=TZ)
    return start <= cur <= end


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", required=True, type=Path, help="queue JSON: sources in order")
    ap.add_argument("--evidence-dir", required=True, type=Path)
    ap.add_argument("--script", required=True, type=Path,
                    help="harvest_r188_lowload.py path")
    args = ap.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    ev = args.evidence_dir
    for sub in ("configs", "snapshots", "checkpoints", "logs"):
        (ev / sub).mkdir(parents=True, exist_ok=True)
    drv_ckpt_path = ev / "checkpoints" / "driver.json"
    drv = {"schema_version": "r188-driver/1.0",
           "night": queue.get("night"),
           "window": queue.get("window"),
           "physical_db_done": [], "results": [], "started_at": now_str()}
    if drv_ckpt_path.exists():
        prev = json.loads(drv_ckpt_path.read_text(encoding="utf-8"))
        if prev.get("night") == queue.get("night"):
            drv = prev  # resume same night

    max_physical = int(queue.get("max_physical_dbs_per_night", 3))
    wall_cap_s = float(queue.get("max_wall_seconds_per_night", 7200))
    t0 = time.monotonic()

    for item in queue["sources"]:
        code = item["source_code"]
        if any(r["source_code"] == code for r in drv["results"]):
            continue  # already done this night
        # cross-night dedup: source fully harvested on a previous night stays done
        # (does NOT consume tonight's physical-DB budget: no load is applied)
        prev_ckpt = ev / "checkpoints" / f"{code}.ckpt.json"
        if prev_ckpt.exists():
            try:
                pv = json.loads(prev_ckpt.read_text(encoding="utf-8"))
                if pv.get("status") == "done":
                    drv["results"].append({"source_code": code, "rc": 0,
                                           "skipped": "done_previous_night",
                                           "at": now_str()})
                    continue
                if pv.get("status") == "stopped_circuit":
                    # circuit-frozen physical instance stays frozen tonight
                    drv.setdefault("frozen_physical", [])
                    if item.get("physical_db_key", code) not in drv["frozen_physical"]:
                        drv["frozen_physical"].append(item.get("physical_db_key", code))
            except Exception:
                pass
        phys = item.get("physical_db_key", code)
        if len(set(drv["physical_db_done"])) >= max_physical:
            drv["stopped_reason"] = f"max_physical_dbs={max_physical}"
            break
        if time.monotonic() - t0 >= wall_cap_s:
            drv["stopped_reason"] = "night_wall_cap"
            break
        if not in_window(queue.get("window")):
            drv["stopped_reason"] = "outside_window"
            break

        cfg_path = ev / "configs" / f"{code}.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cred_file = item["credential_file"]  # /etc/data-asset/credentials/<name>
        snap = ev / "snapshots" / f"{code}.snapshot.json"
        ckpt = ev / "checkpoints" / f"{code}.ckpt.json"
        logs = ev / "logs" / f"{code}.log.jsonl"

        cmd = [sys.executable, str(args.script),
               "--config", str(cfg_path), "--checkpoint", str(ckpt),
               "--output", str(snap), "--logs", str(logs),
               "--credential-file", cred_file]
        t1 = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        rec = {"source_code": code, "physical_db_key": phys,
               "rc": proc.returncode, "stdout_tail": proc.stdout.strip()[-400:],
               "stderr_tail": proc.stderr.strip()[-400:] if proc.returncode else "",
               "wall": round(time.monotonic() - t1, 1), "at": now_str()}
        drv["results"].append(rec)
        if phys not in drv["physical_db_done"]:
            drv["physical_db_done"].append(phys)
        # circuit break -> freeze that physical instance queue for tonight
        try:
            ck = json.loads(ckpt.read_text(encoding="utf-8"))
            if ck.get("status") == "stopped_circuit":
                drv["frozen_physical"] = sorted(set(drv.get("frozen_physical", []) + [phys]))
        except Exception:
            pass
        drv["updated_at"] = now_str()
        drv_ckpt_path.write_text(json.dumps(drv, ensure_ascii=False, indent=1), encoding="utf-8")
        if phys in drv.get("frozen_physical", []):
            break
        # small breather between physical sources
        time.sleep(10)

    drv["finished_at"] = now_str()
    drv_ckpt_path.write_text(json.dumps(drv, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"sources_done": len(drv["results"]),
                      "stopped_reason": drv.get("stopped_reason"),
                      "physical_dbs": sorted(set(drv["physical_db_done"]))},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
