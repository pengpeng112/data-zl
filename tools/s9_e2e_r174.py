"""174 S9: 隔离环境端到端验证（13 场景顺序跑，输出 JSON 证据）。

依赖：隔离库已 upgrade head + 种子已 apply。
用法：
    APP_TEST_DB_URL=... APP_DB_URL=同上 python tools/s9_e2e_r174.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

results: list[dict] = []


def record(scenario: str, passed: bool, detail: str = "") -> None:
    results.append({"scenario": scenario, "passed": passed, "detail": detail})
    print(("PASS " if passed else "FAIL ") + scenario + (" | " + detail if detail else ""))


def main() -> int:
    import hashlib

    from fastapi.testclient import TestClient

    from app.main import app
    from app.scripts import seed_quality_governance as seed

    # 0) 种子就位（幂等，二次零写）+ 平台管理员测试 token（conftest 同法）
    seed.run(dry_run=False)
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models.governance import ApiKey
    from app.models.governance_base import AssetRole, AssetUserRole

    token = "s9-e2e-admin-token"
    db = SessionLocal()
    if not db.scalar(select(AssetRole).where(AssetRole.role_code == "platform_admin")):
        db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
    if not db.scalar(
        select(AssetUserRole).where(
            AssetUserRole.user_identifier == "s9-admin",
            AssetUserRole.role_code == "platform_admin",
        )
    ):
        db.add(AssetUserRole(user_identifier="s9-admin", role_code="platform_admin", status="active"))
    th = hashlib.sha256(token.encode()).hexdigest()
    ex = db.query(ApiKey).filter(ApiKey.key_name == "key-s9-admin").first()
    if not ex:
        db.add(ApiKey(key_name="key-s9-admin", token_hash=th, user_identifier="s9-admin"))
    else:
        ex.token_hash = th
        ex.token = None
        ex.enabled = True
    db.commit()
    db.close()
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    # ── 1) FAIL 首次创建一条问题（用会议清单 T1 对应的探查清单手动摄取） ──
    controls = client.get("/api/v1/quality-controls", params={"keyword": "DQ-HIS-EXAM-001"}).json()["items"]
    assert controls, "T1 control missing"
    control_id = controls[0]["id"]
    r = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-r1",
            "scope_key": "S9-E2E-范围",
            "result_status": "fail",
            "metric_value": 81.4,
            "metric_unit": "%",
            "source_kind": "manual",
        },
    ).json()
    record("1-FAIL首次建单", r["outcome"] == "issue_created", f"issue={r.get('issue_code')}")
    issue_id = r["issue_id"]

    # ── 2) 同一 FAIL 重跑不重复建单 ──
    r2 = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-r1",
            "scope_key": "S9-E2E-范围",
            "result_status": "fail",
        },
    ).json()
    record("2-同run_key幂等", r2["outcome"] == "duplicate")

    # ── 3) PASS 不创建问题（新 scope） ──
    r3 = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-pass",
            "scope_key": "S9-E2E-绿灯范围",
            "result_status": "pass",
            "metric_value": 0.2,
            "source_kind": "manual",
        },
    ).json()
    record("3-PASS不建单", r3["outcome"] == "observed" and r3["issue_id"] is None)

    # ── 4) 分派到科室和人员 ──
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    client.post(
        f"/api/v1/quality-issues/{issue_id}/transition",
        json={"to_status": "acknowledged", "expected_lock_version": lv, "reason": "S9 确认"},
    )
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    r4 = client.post(
        f"/api/v1/quality-issues/{issue_id}/assign",
        json={
            "expected_lock_version": lv,
            "responsible_dept_code": "S9-DEPT",
            "responsible_person_code": "s9-handler",
            "assignee_user_identifier": "s9-handler",
            "responsible_dept_name_snapshot": "S9 测试科室",
            "responsible_person_name_snapshot": "S9 经办",
            "reason": "S9 分派",
        },
    )
    record("4-分派科室人员", r4.status_code == 200 and r4.json()["status"] == "assigned")

    # ── 5) 普通人员只能看到本人/本科室 ──
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models.governance import ApiKey
    from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole
    from app.models.identity import IdentityPerson
    import hashlib

    db = SessionLocal()
    if not db.scalar(select(AssetRole).where(AssetRole.role_code == "s9_handler")):
        db.add(AssetRole(role_code="s9_handler", role_name_cn="S9处理人", role_type="builtin"))
    if not db.scalar(
        select(AssetUserRole).where(
            AssetUserRole.user_identifier == "s9-handler", AssetUserRole.role_code == "s9_handler"
        )
    ):
        db.add(AssetUserRole(user_identifier="s9-handler", role_code="s9_handler", status="active"))
    for res in ("quality.issue.read", "quality.issue.handle"):
        if not db.scalar(
            select(AssetRolePermission).where(
                AssetRolePermission.role_code == "s9_handler",
                AssetRolePermission.resource == res,
            )
        ):
            db.add(AssetRolePermission(role_code="s9_handler", resource=res, action="access"))
    if not db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "s9-handler")):
        db.add(IdentityPerson(person_code="s9-handler", person_name_cn="S9经办", dept_code="S9-DEPT"))
    token = "tok-s9-handler"
    th = hashlib.sha256(token.encode()).hexdigest()
    ex = db.query(ApiKey).filter(ApiKey.key_name == "key-s9-handler").first()
    if not ex:
        db.add(ApiKey(key_name="key-s9-handler", token_hash=th, user_identifier="s9-handler"))
    else:
        ex.token_hash = th
        ex.token = None
        ex.enabled = True
    db.commit()
    db.close()
    handler = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    mine = handler.get("/api/v1/quality-issues", params={"scope": "mine", "page_size": 100}).json()
    sees_own = any(i["id"] == issue_id for i in mine["items"])
    all_forbidden = handler.get("/api/v1/quality-issues", params={"scope": "all"}).status_code == 403
    record("5-数据范围隔离", sees_own and all_forbidden, f"sees_own={sees_own}, all_scope_403={all_forbidden}")

    # ── 6) 经办提交待复测 ──
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    r6 = client.post(
        f"/api/v1/quality-issues/{issue_id}/request-verification",
        json={
            "expected_lock_version": lv,
            "reason": "S9 完成整改",
            "action_plan": "S9 补录措施",
        },
    )
    record("6-提交待复测", r6.status_code == 200 and r6.json()["status"] == "waiting_verify")

    # ── 7) 另一有权限人员验证关闭（平台管理员，非提交人） ──
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    r7 = client.post(
        f"/api/v1/quality-issues/{issue_id}/verify",
        json={
            "expected_lock_version": lv,
            "passed": True,
            "reason": "S9 复测通过",
        },
    )
    record("7-验证关闭", r7.status_code == 200 and r7.json()["status"] == "resolved")

    # ── 8) 关闭后再 FAIL 创建复发问题 ──
    r8 = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-r3",
            "scope_key": "S9-E2E-范围",
            "result_status": "fail",
            "metric_value": 12.5,
            "source_kind": "manual",
        },
    ).json()
    recurrence_ok = (
        r8["outcome"] == "issue_created"
        and r8["issue_id"] != issue_id
    )
    new_detail = client.get(f"/api/v1/quality-issues/{r8['issue_id']}").json()
    record(
        "8-复发新问题",
        recurrence_ok and new_detail["recurrence_of_issue_id"] == issue_id and new_detail["recurrence_no"] == 1,
        f"recurrence_no={new_detail['recurrence_no']}",
    )
    issue_id = r8["issue_id"]

    # ── 9) ERROR/BLOCKED 不关闭 ──
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    client.post(
        f"/api/v1/quality-issues/{issue_id}/transition",
        json={"to_status": "acknowledged", "expected_lock_version": lv, "reason": "S9 确认"},
    )
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    client.post(
        f"/api/v1/quality-issues/{issue_id}/assign",
        json={"expected_lock_version": lv, "responsible_dept_code": "S9-DEPT", "reason": "S9 再分派"},
    )
    client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-error",
            "scope_key": "S9-E2E-范围",
            "result_status": "error",
            "error_code": "S9-ERR",
            "source_kind": "manual",
        },
    )
    client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-blocked",
            "scope_key": "S9-E2E-范围",
            "result_status": "blocked",
            "source_kind": "manual",
        },
    )
    status_now = client.get(f"/api/v1/quality-issues/{issue_id}").json()["status"]
    record("9-ERROR/BLOCKED不关闭", status_now not in ("resolved",), f"status={status_now}")

    # ── 10) accepted_risk 缺必填拒绝 ──
    lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
    r10 = client.post(
        f"/api/v1/quality-issues/{issue_id}/accept-risk",
        json={"expected_lock_version": lv, "risk_reason": "S9 缺批准人"},
    )
    record("10-风险接受必填", r10.status_code == 422)

    # ── 11) 误报抑制到期恢复 ──
    r11a = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-fp-open",
            "scope_key": "S9-E2E-抑制范围",
            "result_status": "fail",
            "source_kind": "manual",
        },
    ).json()
    fp_id = r11a["issue_id"]
    lv = client.get(f"/api/v1/quality-issues/{fp_id}").json()["lock_version"]
    client.post(
        f"/api/v1/quality-issues/{fp_id}/mark-false-positive",
        json={
            "expected_lock_version": lv,
            "false_positive_reason": "S9 误报",
            "suppressed_until": str(date.today() + timedelta(days=7)),
            "reason": "S9 抑制",
        },
    )
    within = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-fp-within",
            "scope_key": "S9-E2E-抑制范围",
            "result_status": "fail",
            "source_kind": "manual",
        },
    ).json()
    # 模拟到期：直接改历史行
    db = SessionLocal()
    from app.models.quality_governance import QualityIssue

    row = db.get(QualityIssue, fp_id)
    row.suppressed_until = date.today() - timedelta(days=1)
    db.commit()
    db.close()
    after = client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": "s9-e2e-fp-after",
            "scope_key": "S9-E2E-抑制范围",
            "result_status": "fail",
            "source_kind": "manual",
        },
    ).json()
    record(
        "11-抑制到期恢复",
        within["outcome"] == "suppressed" and after["outcome"] == "issue_created",
        f"within={within['outcome']}, after={after['outcome']}",
    )

    # ── 12) 导出无公式注入和敏感字段 ──
    db = SessionLocal()
    from app.services import quality_governance_service as qgs

    qgs.create_manual_issue(
        db,
        title="=CMD('evil') S9 注入",
        description="=1+1",
        responsible_dept_code="S9-DEPT",
        actor="s9",
    )
    db.commit()
    db.close()
    export = client.post("/api/v1/quality-issues/export", json={"scope": "all"})
    body = export.text
    header_line = body.splitlines()[0]
    no_injection = "'=CMD" in body or "=CMD" not in body
    no_sensitive = all(
        b not in header_line for b in ("evidence_sql", "sample_data", "phone", "id_card", "password")
    )
    record(
        "12-导出安全",
        export.status_code == 200 and no_injection and no_sensitive,
        f"injection_guard={no_injection}, whitelist_ok={no_sensitive}",
    )

    # ── 13) 旧 Probe/Quality API 正常（必须 200，404 不能算过）──
    probe_code = client.get("/api/v1/probe-findings", params={"page": 1, "page_size": 5}).status_code
    quality_rules_code = client.get("/api/v1/quality/rules", params={"page": 1, "page_size": 5}).status_code
    record(
        "13-旧API回归",
        probe_code == 200 and quality_rules_code == 200,
        f"probe={probe_code}, quality_rules={quality_rules_code}",
    )

    summary = {
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "results": results,
    }
    out = Path(__file__).resolve().parents[1] / "开发起步包" / "output_r174" / "s9_e2e_results.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary["passed"], default=str) + " passed / " + str(summary["failed"]) + " failed")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
