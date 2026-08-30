"""165 §4: run_probe.py —— 探查执行器（夜间窗口使用）。

拓扑（165 §1.5）：源侧一律经 sjzc 同款 8.83 容器受控连接器（本机只调
~/.zcode/skills/sjzc/scripts/sjzc_query.py live 子进程，凭据不出服务器、
本机零直连业务库）；写侧=平台隔离库 SQLAlchemy。

铁律：单模板超时 120s、整轮墙钟 60 分钟；evidence_sql 只存模板文本
（无 ID 字面量，T9 键集仅内存流转）；error_summary 过 sanitize_text；
执行器身份 probe:<run_id>；每 run 一条 GovernAuditLog 汇总。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))


def _preset_write_db() -> None:
    """导入 app.core.db 之前预置 APP_DB_URL：engine 在 import 时即创建，
    main() 里再设环境变量不生效（E3 UndefinedTable 事故根因，2026-08-30 修复）。"""
    import os
    for i, a in enumerate(sys.argv):
        if a == "--write-db" and i + 1 < len(sys.argv):
            os.environ["APP_DB_URL"] = sys.argv[i + 1]
            return
        if a.startswith("--write-db="):
            os.environ["APP_DB_URL"] = a.split("=", 1)[1]
            return


_preset_write_db()

from app.core.db import SessionLocal  # noqa: E402
from app.models.governance_base import GovernAuditLog  # noqa: E402
from app.services import probe_service as ps  # noqa: E402
from app.services.data_masking import sanitize_text  # noqa: E402

SJZC = Path.home() / ".zcode" / "skills" / "sjzc" / "scripts" / "sjzc_query.py"
TEMPLATES_DIR = _BACKEND_ROOT / "scripts" / "probe_templates"
SINGLE_TIMEOUT_S = 120
WHOLE_RUN_S = 60 * 60
PY = sys.executable


def month_window(today_cut: bool) -> tuple[date, date]:
    """last-full-month（默认）；--today-cut 时 end=今天（当前月部分窗）。"""
    now = datetime.now()
    if today_cut:
        end = date(now.year, now.month, now.day)
    else:
        first_this = date(now.year, now.month, 1)
        end = first_this - timedelta(days=1)
    first_end = date(end.year, end.month, 1)
    start = (first_end - timedelta(days=1)).replace(day=1)
    return start, end


def sjzc_live(source_code: str, sql: str, max_rows: int = 10000) -> dict:
    """经 sjzc 受控连接器执行只读 SQL，返回 JSON dict。"""
    proc = subprocess.run(
        [PY, str(SJZC), "live", source_code, "--sql", sql, "--max-rows", str(max_rows)],
        capture_output=True, text=True, timeout=SINGLE_TIMEOUT_S, encoding="utf-8",
    )
    out = (proc.stdout or "").strip().splitlines()
    payload = None
    for line in reversed(out):
        line = line.strip()
        if line.startswith("{") and '"ok"' in line:
            payload = json.loads(line)
            break
    if payload is None:
        raise RuntimeError(f"sjzc live 无 JSON 输出: {(proc.stderr or proc.stdout or '')[-300:]}")
    if not payload.get("ok"):
        raise RuntimeError(f"sjzc live 失败: {json.dumps(payload)[:300]}")
    return payload


def render_params(sql: str, start: date, end: date, dialect: str) -> str:
    """运行时把 :START_DATE/:END_DATE 渲染为各方言安全字面量（执行器生成，
    非用户输入；模板存储文本保持参数占位符=入库 evidence_sql）。"""
    s, e = start.isoformat(), end.isoformat()
    if dialect == "oracle":
        return sql.replace(":START_DATE", f"'{s}'").replace(":END_DATE", f"'{e}'")
    if dialect == "vastbase":
        return sql.replace(":START_DATE", f"'{s}'").replace(":END_DATE", f"'{e}'")
    return sql.replace(":START_DATE", f"'{s}'").replace(":END_DATE", f"'{e}'")


def evaluate_trigger(value: float, trig: dict) -> bool:
    op, th = trig["op"], float(trig["threshold"])
    return {"gt": value > th, "ge": value >= th, "lt": value < th, "le": value <= th}[op]


def _rows(payload: dict) -> list[dict]:
    return [{k.upper(): v for k, v in r.items()} for r in payload.get("rows", [])]


def run_single_source(db, tpl: dict, start: date, end: date, run_id: str) -> dict:
    side = tpl["sides"][0]
    sql = render_params(side["sql"], start, end, side["dialect"])
    payload = sjzc_live(side["source_code"], sql)
    rows = _rows(payload)
    derive = tpl["derive"]
    r0 = rows[0] if rows else {}
    total = float(r0.get("TOTAL") or r0.get("APPLIED") or 0)
    miss = float(r0.get("MISS") or 0)
    reported = float(r0.get("REPORTED") or 0)
    if derive["metric"].endswith("missing_rate"):
        value = miss / total * 100 if total else 0.0
    elif derive["metric"].endswith("name_mismatch_rate"):
        mismatch = float(r0.get("MISMATCH") or 0)
        nonnull = float(r0.get("NONNULL") or 0)
        value = mismatch / nonnull * 100 if nonnull else 0.0
    elif derive["metric"] == "exam_report_writeback_rate":
        value = reported / total * 100 if total else 0.0
    elif derive["metric"].endswith("out_of_domain_rate"):
        allowed = set(derive["allowed"])
        tot = sum(float(r.get("CNT") or 0) for r in rows)
        out = sum(float(r.get("CNT") or 0) for r in rows if str(r.get("CODE")) not in allowed)
        value = out / tot * 100 if tot else 0.0
    else:
        value = 0.0
    return {"rows": rows, "value": round(value, 4), "extra": {k: r0.get(k) for k in derive.get("extra_metrics", [])}}


def run_dual_source(tpl: dict, start: date, end: date) -> dict:
    sa, sb = tpl["sides"][0], tpl["sides"][1]
    if sb.get("mode") == "blocked" or tpl.get("blocked"):
        raise RuntimeError(f"side-b BLOCKED: {sb.get('reason', 'blocked')}")
    ra = _rows(sjzc_live(sa["source_code"], render_params(sa["sql"], start, end, sa["dialect"])))
    if sb.get("mode") == "key_lookup":
        keys = [(r.get("PATIENT_ID"), r.get("VISIT_ID")) for r in ra]
        if not keys:
            return {"value": 100.0, "detail": {"sampled": 0, "matched": 0}, "unmapped": []}
        pairs = ", ".join(f"('{p}','{v}')" for p, v in keys[:1000])
        sql = sb["sql"].replace("__KEYS__", pairs)
        rb = _rows(sjzc_live(sb["source_code"], sql, max_rows=1000))
        hit = {(r.get("PATIENT_ID"), r.get("VISIT_ID")) for r in rb}
        matched = sum(1 for k in keys if k in hit)
        return {"value": round(matched / len(keys) * 100, 4), "detail": {"sampled": len(keys), "matched": matched}, "unmapped": []}
    rb = _rows(sjzc_live(sb["source_code"], render_params(sb["sql"], start, end, sb["dialect"])))
    mapping = tpl["derive"].get("mapping") or {}
    if mapping:
        conv = {}
        for r in rb:
            code = mapping.get(str(r.get("CODE")), str(r.get("CODE")))
            conv[code] = conv.get(code, 0) + float(r.get("CNT") or 0)
        rb = [{"CODE": k, "CNT": v} for k, v in conv.items()]
    da = {str(r.get("CODE")): float(r.get("CNT") or 0) for r in ra}
    dbk = {str(r.get("CODE")): float(r.get("CNT") or 0) for r in rb}
    unmapped = sorted(set(da) - set(dbk)) if not mapping else sorted(k for k in da if k not in dbk)
    tot_a, tot_b = sum(da.values()), sum(dbk.values())
    if tpl["derive"].get("compare") == "by_month_key":
        base = max(da.values()) if da else 1
        value = max(abs(da.get(k, 0) - dbk.get(k, 0)) for k in (set(da) | set(dbk))) / base * 100
    else:
        diff = sum(abs(da.get(k, 0) - dbk.get(k, 0)) for k in set(da) | set(dbk))
        denom = max(tot_a, tot_b, 1)
        value = diff / denom * 100
    return {"value": round(value, 4), "detail": {"a": da, "b": dbk}, "unmapped": unmapped}


def run_probe(tpl: dict, db, start: date, end: date, run_id: str) -> dict:
    """执行单模板：源侧取数→trigger→（越阈）upsert。返回执行记录。"""
    t0 = time.monotonic()
    rec = {"code": tpl["code"], "status": "ok", "triggered": False}
    try:
        if tpl.get("blocked"):
            raise RuntimeError(f"BLOCKED: {tpl['sides'][1].get('reason') if len(tpl['sides']) > 1 else 'blocked'}")
        if len(tpl["sides"]) == 1:
            res = run_single_source(db, tpl, start, end, run_id)
        else:
            res = run_dual_source(tpl, start, end)
        rec["metric_value"] = res["value"]
        rec["metrics"] = res.get("detail", res.get("extra", {}))
        rec["unmapped"] = res.get("unmapped", [])
        trig = tpl["trigger"]
        rec["triggered"] = evaluate_trigger(res["value"], trig)
        if rec["triggered"]:
            side_sqls = [s["sql"] for s in tpl["sides"]]
            if tpl["derive"].get("finding_per_value"):
                rows = res.get("rows") or []
                allowed = set(tpl["derive"]["allowed"])
                tot = sum(float(r.get("CNT") or 0) for r in rows) or 1
                n = 0
                for r in rows:
                    code = str(r.get("CODE"))
                    if code in allowed or n >= tpl["derive"].get("max_findings", 50):
                        continue
                    outv = float(r.get("CNT") or 0) / tot * 100
                    up = ps.upsert_finding(
                        db, run_id=run_id, probe_type=tpl["probe_type"],
                        system_pair="HIS(单库)",
                        object_desc=f"{tpl['object_desc_tpl']}：非法值 {code!r}",
                        metric_name=tpl["derive"]["metric"], metric_value=outv,
                        metric_unit="%", threshold=0.0, window_start=start, window_end=end,
                        severity=tpl["severity_default"], evidence_sql=side_sqls[0],
                        note=f"非法值 {code!r} 占比（R-DOM 只产 finding，不写值域库）",
                    )
                    n += 1
                    rec.setdefault("finding_outcomes", []).append(up["outcome"])
            else:
                pair = ("HIS↔JHEMR" if any(s["source_code"].startswith("jhemr") for s in tpl["sides"])
                        else ("HIS↔LIS" if any(s["source_code"].startswith("lis") for s in tpl["sides"]) else "HIS(单库)"))
                up = ps.upsert_finding(
                    db, run_id=run_id, probe_type=tpl["probe_type"], system_pair=pair,
                    object_desc=tpl["object_desc_tpl"], metric_name=tpl["derive"]["metric"],
                    metric_value=res["value"], metric_unit=tpl["derive"]["unit"],
                    threshold=float(trig["threshold"]), window_start=start, window_end=end,
                    severity=tpl["severity_default"], evidence_sql="\n--SIDE-B--\n".join(side_sqls),
                )
                rec["finding_outcomes"] = [up["outcome"]]
                rec["relapse"] = up.get("relapse", False)
    except subprocess.TimeoutExpired:
        rec["status"] = "timeout"
        rec["error"] = f"single-template timeout {SINGLE_TIMEOUT_S}s"
    except Exception as exc:  # 单模板失败=partial 继续
        rec["status"] = "error"
        rec["error"] = sanitize_text(str(exc))
    rec["elapsed_s"] = round(time.monotonic() - t0, 1)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="165 E3: 探查执行器（夜间）")
    ap.add_argument("--window", default="last-full-month", choices=["last-full-month"])
    ap.add_argument("--today-cut", action="store_true")
    ap.add_argument("--write-db", required=True, help="目标库 URL（隔离库）")
    ap.add_argument("--out", required=True, help="run JSON 输出目录")
    ap.add_argument("--only", default="", help="仅执行指定模板 code（逗号分隔，调试用）")
    args = ap.parse_args()

    import os
    os.environ["APP_DB_URL"] = args.write_db

    from sqlalchemy.engine import make_url
    want, got = SessionLocal.kw["bind"].url, make_url(args.write_db)
    if (want.host, want.port, want.database) != (got.host, got.port, got.database):
        raise SystemExit(
            f"FATAL: SessionLocal 实际指向 {want.host}:{want.port}/{want.database}，"
            f"与 --write-db {got.host}:{got.port}/{got.database} 不一致，拒绝执行"
        )

    templates = sorted(TEMPLATES_DIR.glob("T*.json"))
    if args.only:
        keep = {c.strip() for c in args.only.split(",")}
        templates = [p for p in templates if p.stem in keep]
    start, end = month_window(args.today_cut)
    run_id = f"probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    wall0 = time.monotonic()

    db = SessionLocal()
    summary: dict[str, dict] = {}
    new = updated = relapses = 0
    status = "done"
    try:
        ps.register_run(db, run_id=run_id)
        db.commit()
        for path in templates:
            if time.monotonic() - wall0 > WHOLE_RUN_S:
                status = "partial"
                summary[path.stem] = {"status": "skipped", "error": "whole-run wall clock exceeded"}
                continue
            tpl = json.loads(path.read_text(encoding="utf-8"))
            rec = run_probe(tpl, db, start, end, run_id)
            db.commit()
            summary[path.stem] = rec
            for o in rec.get("finding_outcomes", []):
                if o == "created":
                    new += 1
                elif o in ("same_window_updated", "new_window_updated"):
                    updated += 1
            if rec.get("relapse"):
                relapses += 1
            if rec["status"] in ("error", "timeout"):
                status = "partial"
        errs = "; ".join(f"{k}:{v.get('error')}" for k, v in summary.items() if v.get("error"))
        ps.update_run(
            db, run_id=run_id, status=status, probe_count=len(templates),
            finding_new=new, finding_updated=updated, relapse_count=relapses,
            metrics_summary=summary, error_summary=sanitize_text(errs) if errs else None,
        )
        db.add(GovernAuditLog(
            module="probe", entity_type="probe_run", entity_ref=run_id, action="run",
            after_data={"templates": len(templates), "finding_new": new,
                        "finding_updated": updated, "relapse_count": relapses, "status": status},
            operator=f"probe:{run_id}", reason="165 E3 夜间探查（执行器只写 open/观测/relapse）",
        ))
        db.commit()
    finally:
        db.close()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, "status": status, "window": [start.isoformat(), end.isoformat()],
               "probe_count": len(templates), "finding_new": new, "finding_updated": updated,
               "relapse_count": relapses, "summary": summary,
               "generated_at": datetime.now(timezone.utc).isoformat()}
    (out_dir / f"{run_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("run_id", "status", "probe_count", "finding_new", "finding_updated", "relapse_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
