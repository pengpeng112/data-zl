"""r172: CDMS 无纸化下乡人员权限补齐（走平台 identity 同步管线代码路径）。

名单来源：开发起步包/172 号核对（2026-09-01，cdms_xiaxiang_check.json）+
用户 2026-09-02 指令「根据每天同步的任务处理，之前导入过但角色和科室没成功」。

根因：27 人 classification=legacy_unmanaged（入职早于 LEGACY_CUTOFF 存量线），
夜间 MODIFIEDTIME 增量管线永不认领；CDMS 账号为早期人工建户，无 AUTHMAPPING
权限行（角色 FTYPE=0 / 科室 FTYPE=2 / 人员 100005 / 基础 A00001、10）。

处理：与 run_identity_modified_nightly.py 完全同一代码路径
（_process_single_candidate + reconcile_existing=True → executor bridge →
align_existing_user 幂等补缺 / apply_single_user 新建户），同一门禁 env、
同一凭据、同一审计（batches/actions/managed_relations/scheduler_runs）。

用法：python /tmp/r172_reconcile_xiaxiang.py dry|apply
赵慧工号存疑（名单 001172 无 CDMS 户，库内同名 000110 已在补齐名单）——
001172 不在本脚本处理范围，留人工确认（172 号裁决维持）。
"""
import json
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

# 24 人：CDMS 在户但无任何权限行（172 实测）→ align 补齐
ALIGN = {
    "000852": "刘婷婷", "001163": "宋肖", "001270": "沈淑文", "001306": "张双双",
    "001407": "刘君", "001542": "陈慧", "001670": "王茹", "001838": "李琪",
    "001974": "杨帆", "002076": "赵岩", "002106": "王娜娜", "002137": "乔永静",
    "002154": "齐熠颖", "002214": "李小芹", "002236": "刘治超", "002340": "于鹏",
    "002541": "史雪娇", "002542": "吴玖旭", "002546": "陈晓", "002590": "樊琳琳",
    "002633": "户颖慧", "002751": "张成印", "002978": "王成", "000110": "赵慧(000110)",
}
# 3 人：从未建户（172 实测）→ apply_single_user 建户+全权限
CREATE = {
    "001324": "李进叶", "003176": "安鹏", "002124": "李威",
}
# 全员按医师处理（平台证据：JOB=医生/临床/中医临床/影像诊断，职称=主治/副主任医师；
# CDMS 角色映射 doctor → a1c9192f...（医疗质控），与 172 模板一致）
CLASSIFICATION = "doctor"


def build_candidates(db):
    rows = []
    for emp, name in sorted({**ALIGN, **CREATE}.items()):
        primary, additional = _get_person_depts(db, emp, CLASSIFICATION)
        rows.append({
            "emp_no": emp,
            "name": name,
            "mode": "align" if emp in ALIGN else "create",
            "primary_dept": primary,
            "dept_codes": [primary] + (additional or []),
        })
    return rows


def dry_run(candidates):
    """只读：平台科室 + CDMS/JHEMR 目标侧现状与计划补齐行。"""
    from app.core.config import settings
    from app.services.cdms_identity_adapter import CdmsIdentityAdapter

    print("== r172 dry-run（只读）==")
    no_dept = [c for c in candidates if not c["primary_dept"]]
    if no_dept:
        print(f"!! {len(no_dept)} 人平台主档无主科室，将被管线跳过：", [c["emp_no"] for c in no_dept])

    plan = []
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
            existing = {(str(r.get("ftype")), str(r.get("fauthorityid"))) for r in (auth or [])}
            if user is None:
                expect = "CREATE 户+5+ 行权限"
            else:
                need = [("0", "a1c9192fbe31423fab2dce6f81791b88")]
                need += [("2", d) for d in c["dept_codes"] if d]
                need += [("3", "100005"), ("5", "A00001"), ("10", "1")]
                missing = [p for p in need if p not in existing]
                expect = f"ALIGN 补 {len(missing)} 行 {missing[:6]}"
                cur_dept = (user or {}).get("fdept")
                if cur_dept != c["primary_dept"]:
                    expect += f" + FDEPT {cur_dept}->{c['primary_dept']}"
            plan.append({"emp_no": c["emp_no"], "name": c["name"], "mode": c["mode"],
                         "dept_codes": c["dept_codes"], "cdms_now": "in_db" if user else "absent",
                         "auth_rows": len(auth or []), "plan": expect})
            print(f"  {c['emp_no']} {c['name']:<10} dept={c['dept_codes']} cdms={'在户' if user else '无户'} auth={len(auth or [])}行 → {expect}")
    finally:
        cdms.close()
    print("dry-run 完成：", len(plan), "人")
    return plan


def apply(candidates):
    print("== r172 apply（走夜间任务同代码路径）==")
    db = SessionLocal()
    run_id = f"RUN-{uuid.uuid4().hex[:12]}"
    run = IdentitySchedulerRun(
        run_id=run_id,
        triggered_by="r172_xiaxiang_reconcile",
        status="running",
        started_at=_now(),
        provider_code="host_cron",
    )
    db.add(run)
    db.commit()
    ok = fail = 0
    results = []
    for c in candidates:
        if not c["primary_dept"]:
            results.append({"emp_no": c["emp_no"], "status": "skipped_no_primary_dept"})
            print(f"  {c['emp_no']} {c['name']:<10} SKIP 无主科室")
            continue
        cand = {
            "emp_no": c["emp_no"],
            "emp_no_masked": _mask_emp_no(c["emp_no"]),
            "classification": CLASSIFICATION,
            "primary_dept": c["primary_dept"],
            "dept_codes": c["dept_codes"],
            "create_date": None,
            "modified_time": None,
        }
        r = _process_single_candidate(db, cand, run_id, reconcile_existing=True)
        results.append({"emp_no": c["emp_no"], "name": c["name"], **{k: v for k, v in r.items() if k in ("status", "note", "reason", "error")}})
        flag = r.get("status")
        print(f"  {c['emp_no']} {c['name']:<10} -> {flag} {r.get('note') or r.get('reason') or r.get('error') or ''}")
        if flag == "success":
            ok += 1
        else:
            fail += 1
        db.commit()
    run.status = "success" if fail == 0 else "partial"
    run.success_count = ok
    run.failed_count = fail
    run.finished_at = _now()
    run.report_summary = {"scope": "cdms_xiaxiang_r172", "ok": ok, "failed": fail}
    db.commit()
    db.close()
    print(f"apply 完成：success={ok} failed={fail} run_id={run_id}")
    return results


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    db = SessionLocal()
    try:
        candidates = build_candidates(db)
    finally:
        db.close()
    print(f"candidates={len(candidates)} classification={CLASSIFICATION}")
    if mode == "dry":
        dry_run(candidates)
    else:
        apply(candidates)


if __name__ == "__main__":
    main()
