"""r198: 身份同步 pending_reconcile 积压补齐窗口（2026-09-22）。

积压来源：2026-09-19 起夜间任务认领 004076/001491 后被 186 号 disable_only
运行模式+夜间 env 缺两道开关软阻断，CDMS/JHEMR 各 2 条 account 登记挂起。
用户 2026-09-22 授权按方案 1 人工窗口补齐（同 r172 模式）：
_process_single_candidate(reconcile_existing=True) → executor bridge →
apply_single_user 新建户（CDMS T_MSS_EMP_DICT+AUTHMAPPING / JHEMR 6 表单事务），
同一凭据、同一审计（scheduler_runs/batches/actions/managed_relations）。

用法：python r198_reconcile_pending.py dry|apply
apply 必须带 full 门禁 env（见 198 号文档 §2）。
"""
import sys
import uuid

from app.core.db import SessionLocal
from app.models.identity_sync import IdentitySchedulerRun
from app.services.identity_sync_orchestrator import (
    _get_person_depts,
    _mask_emp_no,
    _now,
    _process_single_candidate,
)

# pending_reconcile 积压实测（2026-09-22）：2 人 × 2 系统
PEOPLE = {
    "004076": ("田洋洋", "doctor"),
    "001491": ("石士园", "nurse"),
}


def build_candidates(db):
    rows = []
    for emp, (name, cls) in sorted(PEOPLE.items()):
        primary, additional = _get_person_depts(db, emp, cls)
        rows.append({
            "emp_no": emp,
            "name": name,
            "classification": cls,
            "primary_dept": primary,
            "dept_codes": [primary] + (additional or []),
        })
    return rows


def dry_run(candidates):
    """只读：平台科室 + CDMS/JHEMR 目标侧现状与计划。"""
    from app.core.config import settings
    from app.services.cdms_identity_adapter import CdmsIdentityAdapter
    from app.services.identity_sync_action_gate import read_target_account_state

    print("== r198 dry-run（只读）==")
    no_dept = [c for c in candidates if not c["primary_dept"]]
    if no_dept:
        print(f"!! {len(no_dept)} 人平台主档无主科室，将被管线跳过：", [c["emp_no"] for c in no_dept])

    cdms = CdmsIdentityAdapter(
        credential_ref=settings.identity_sync_cdms_credential_ref,
        cdms_host=settings.identity_sync_cdms_host,
        cdms_port=settings.identity_sync_cdms_port,
        cdms_service=settings.identity_sync_cdms_service,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
    )
    try:
        cdms.connect()
        for c in candidates:
            if not c["primary_dept"]:
                continue
            user = cdms.snapshot_user(c["emp_no"])
            auth = cdms.snapshot_auth(c["emp_no"])
            jh = read_target_account_state("JHEMR", c["emp_no"])
            if user is None:
                expect = "CREATE 户+角色+科室+基础权限（FFREE3 已根修自动带）"
            else:
                expect = "ALIGN 幂等补缺"
            print(f"  {c['emp_no']} {c['name']:<6} cls={c['classification']} "
                  f"dept={c['dept_codes']} | CDMS={'在户' if user else '无户'} "
                  f"auth={len(auth or [])}行 | JHEMR={'有账号' if jh else '无/读失败'} -> {expect}")
    finally:
        cdms.close()
    print("dry-run 完成：", len(candidates), "人")


def apply(candidates):
    print("== r198 apply（走夜间任务同代码路径，full 门禁 env）==")
    db = SessionLocal()
    run_id = f"RUN-{uuid.uuid4().hex[:12]}"
    run = IdentitySchedulerRun(
        run_id=run_id,
        triggered_by="r198_pending_reconcile_window",
        status="running",
        started_at=_now(),
        provider_code="host_cron",
    )
    db.add(run)
    db.commit()
    ok = fail = 0
    for c in candidates:
        if not c["primary_dept"]:
            print(f"  {c['emp_no']} {c['name']:<6} SKIP 无主科室")
            fail += 1
            continue
        cand = {
            "emp_no": c["emp_no"],
            "emp_no_masked": _mask_emp_no(c["emp_no"]),
            "classification": c["classification"],
            "primary_dept": c["primary_dept"],
            "dept_codes": c["dept_codes"],
            "create_date": None,
            "modified_time": None,
        }
        r = _process_single_candidate(db, cand, run_id, reconcile_existing=True)
        flag = r.get("status")
        print(f"  {c['emp_no']} {c['name']:<6} -> {flag} {r.get('note') or r.get('reason') or r.get('error') or ''}")
        if flag == "success" and not str(r.get("note")).startswith("pending"):
            ok += 1
        else:
            fail += 1
        db.commit()
    run.status = "success" if fail == 0 else "partial"
    run.success_count = ok
    run.failed_count = fail
    run.finished_at = _now()
    run.report_summary = {"scope": "r198_pending_reconcile_window", "ok": ok, "failed": fail}
    db.commit()
    db.close()
    print(f"apply 完成：success={ok} failed={fail} run_id={run_id}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    db = SessionLocal()
    try:
        candidates = build_candidates(db)
    finally:
        db.close()
    print(f"candidates={len(candidates)}")
    if mode == "dry":
        dry_run(candidates)
    else:
        apply(candidates)


if __name__ == "__main__":
    main()
