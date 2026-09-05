# -*- coding: utf-8 -*-
"""166 D6 后联调采集：真实后端（隔离库）+ 前端 dev server 截图 + throwaway 全流转。

顺序（附录 A.2：联调必须在 D6 全量回归之后）：
  1. 空态截图（全量回归后真实空库：/probe-findings、/value-domains）
  2. 造 throwaway 数据（表+值域+finding，全部带 throwaway 标记）
  3. UI 截图（F4 列表/详情/流转、F2 列表/冲突 Tab/抽屉、F1 表详情值域区块）
  4. API 全流转 12 条迁移（throwaway finding，逐条记录+审计验证）
  5. 导出 CSV 采样（两处，核验六约束头部证据）
  6. 删除全部 throwaway 行（findings/值域/表/角色/ApiKey/审计留档不删——审计是证据）
凭据：throwaway ApiKey + platform_admin 绑定（隔离库，测后删除）。
"""
from __future__ import annotations

import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[2] / "backend"))

import csv
import hashlib
import io
import json
import time
from datetime import date
from pathlib import Path

import httpx as requests

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)

DB_URL = "postgresql+psycopg://postgres@127.0.0.1:15432/data_asset_test"
BACKEND = "http://127.0.0.1:8000"
FRONT = "http://127.0.0.1:8848"
TOKEN = "throwaway-token-r166-lianTiao-0001"
USER = "throwaway-admin-r166"

EVIDENCE: dict = {"stages": []}


def log(stage: str, **kw):
    EVIDENCE["stages"].append({"stage": stage, **kw})
    print(f"[r166] {stage}: {json.dumps(kw, ensure_ascii=False)[:300]}")


def seed_throwaway():
    from app.core.db import SessionLocal
    from app.models.governance import ApiKey
    from app.models.governance_base import AssetRole, AssetUserRole
    from app.models.asset import AssetTable, AssetColumn
    from app.services.probe_service import register_run, upsert_finding
    from sqlalchemy import select

    db = SessionLocal()
    try:
        # throwaway 登录身份（platform_admin 直通）
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == "platform_admin")):
            db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
        if not db.scalar(select(AssetUserRole).where(
            AssetUserRole.user_identifier == USER, AssetUserRole.role_code == "platform_admin"
        )):
            db.add(AssetUserRole(user_identifier=USER, role_code="platform_admin", status="active"))
        existing = db.query(ApiKey).filter(ApiKey.key_name == "throwaway-r166").first()
        token_hash = hashlib.sha256(TOKEN.encode("utf-8")).hexdigest()
        if not existing:
            db.add(ApiKey(key_name="throwaway-r166", token_hash=token_hash, user_identifier=USER))
        else:
            existing.token_hash = token_hash
            existing.user_identifier = USER
            existing.enabled = True

        # throwaway 表 + 字段（F1 展示 + 值域挂靠）
        if not db.scalar(select(AssetTable).where(AssetTable.table_name == "R166_THROWAWAY")):
            db.add(AssetTable(
                schema_name="R166", table_name="R166_THROWAWAY", namespace_name=None,
                source_code="ods_8_216", system_code="DATA_CENTER", column_count=2, domain="test",
            ))
        if not db.scalar(select(AssetColumn).where(AssetColumn.table_name == "R166_THROWAWAY")):
            db.add(AssetColumn(
                system_code="DATA_CENTER", source_code="ods_8_216", namespace_name=None,
                schema_name="R166", table_name="R166_THROWAWAY", column_id=1,
                column_name="DISCHARGE_DISPOSITION", data_type="VARCHAR2", nullable="Y",
                review_status="throwaway_r166",
            ))
            db.add(AssetColumn(
                system_code="DATA_CENTER", source_code="ods_8_216", namespace_name=None,
                schema_name="R166", table_name="R166_THROWAWAY", column_id=2,
                column_name="NO_DOMAIN_COL", data_type="VARCHAR2", nullable="Y",
                review_status="throwaway_r166",
            ))

        # throwaway finding（全流转对象）
        register_run(db, run_id="probe-t-r166throwaway", status="done", created_by=USER)
        upsert_finding(
            db, run_id="probe-t-r166throwaway", probe_type="R-XSYS", system_pair="HIS↔JHEMR",
            object_desc="[throwaway-r166] 联调用对象：全流转演示", metric_name="throwaway_metric",
            metric_value=42.5, metric_unit="%", threshold=1.0,
            window_start=date(2026, 7, 1), window_end=date(2026, 7, 31), severity="P2",
            evidence_sql="SELECT COUNT(*) FROM DUAL WHERE D >= :START_DATE AND D < :END_DATE",
            note="[throwaway-r166]",
        )
        db.commit()
        log("seed_throwaway", ok=True)
    finally:
        db.close()


def api_headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def seed_value_domain_via_api():
    r = requests.post(f"{BACKEND}/api/v1/value-domains", headers=api_headers(), json={
        "system_code": "DATA_CENTER", "source_code": "ods_8_216",
        "schema_name": "R166", "table_name": "R166_THROWAWAY",
        "column_name": "DISCHARGE_DISPOSITION", "code": "4",
        "meaning": "[throwaway-r166] 非医嘱离院", "domain_kind": "enum",
        "evidences": [{"source_type": "manual", "snippet_ref": "166 联调", "method": "throwaway"}],
    }, timeout=15)
    log("value_domain_submit", status=r.status_code)
    # 冲突行（第二个 code，制造 conflicted 供冲突 Tab 展示）
    r2 = requests.post(f"{BACKEND}/api/v1/value-domains", headers=api_headers(), json={
        "system_code": "DATA_CENTER", "source_code": "ods_8_216",
        "schema_name": "R166", "table_name": "R166_THROWAWAY",
        "column_name": "DISCHARGE_DISPOSITION", "code": "5",
        "meaning": "[throwaway-r166] 死亡", "domain_kind": "enum",
        "evidences": [{"source_type": "manual", "snippet_ref": "166 联调", "method": "throwaway"}],
    }, timeout=15)
    r3 = requests.post(f"{BACKEND}/api/v1/value-domains", headers=api_headers(), json={
        "system_code": "DATA_CENTER", "source_code": "ods_8_216",
        "schema_name": "R166", "table_name": "R166_THROWAWAY",
        "column_name": "DISCHARGE_DISPOSITION", "code": "5",
        "meaning": "[throwaway-r166] 死亡（冲突口径B）", "domain_kind": "enum",
        "evidences": [{"source_type": "cross_system", "source_system": "JHEMR",
                       "observed_meaning": "[throwaway-r166] 死亡（冲突口径B）",
                       "snippet_ref": "166 联调", "method": "throwaway"}],
    }, timeout=15)
    log("value_domain_conflict", submit=r2.status_code, clash=r3.status_code,
        expect_clash_409=(r3.status_code == 409))


def run_full_transitions():
    """全 12 条合法迁移逐条跑（throwaway finding；API+审计验证）。"""
    fid = requests.get(
        f"{BACKEND}/api/v1/probe-findings?probe_type=R-XSYS", headers=api_headers(), timeout=15
    ).json()["items"][0]["id"]
    from app.api.v1.permissions import ROLE_DEFAULT_PERMISSIONS  # noqa: F401  (确保模块加载口径一致)
    statuses = ["open", "confirmed", "false_positive", "resolved"]
    transitions = [(f, t) for f in statuses for t in statuses if f != t]
    results = []
    for frm, to in transitions:
        if frm != "open":  # 直改库构造 from 态（夹具口径；服务层无终态写入）
            from app.core.db import SessionLocal
            from sqlalchemy import text as _t
            db = SessionLocal()
            try:
                db.execute(_t(f"UPDATE asset.asset_probe_findings SET status='{frm}', "
                              f"resolved_by=NULL, resolved_at=NULL WHERE id={fid}"))
                db.commit()
            finally:
                db.close()
        r = requests.post(
            f"{BACKEND}/api/v1/probe-findings/{fid}/transition", headers=api_headers(),
            json={"action": "reclassify", "to_status": to, "reason": f"[throwaway-r166] {frm}->{to}"},
            timeout=15,
        )
        row_status = requests.get(
            f"{BACKEND}/api/v1/probe-findings/{fid}", headers=api_headers(), timeout=15
        ).json()["status"]
        results.append({"from": frm, "to": to, "http": r.status_code, "after": row_status,
                        "ok": r.status_code == 200 and row_status == to})
    # 双拒绝路径
    db_rejects = []
    r_same = requests.post(
        f"{BACKEND}/api/v1/probe-findings/{fid}/transition", headers=api_headers(),
        json={"action": "reclassify", "to_status": "resolved", "reason": "x"}, timeout=15)
    # （当前态=resolved，同态 → 422）
    r_bad = requests.post(
        f"{BACKEND}/api/v1/probe-findings/{fid}/transition", headers=api_headers(),
        json={"action": "reclassify", "to_status": "closed", "reason": "x"}, timeout=15)
    r_noreason = requests.post(
        f"{BACKEND}/api/v1/probe-findings/{fid}/transition", headers=api_headers(),
        json={"action": "reopen"}, timeout=15)
    db_rejects = [
        {"case": "same_status", "http": r_same.status_code},
        {"case": "invalid_value", "http": r_bad.status_code},
        {"case": "reason_missing", "http": r_noreason.status_code},
    ]
    # 审计行计数
    from app.core.db import SessionLocal
    from app.models.governance_base import GovernAuditLog
    from sqlalchemy import select, func
    db = SessionLocal()
    try:
        audit_count = db.scalar(
            select(func.count()).select_from(GovernAuditLog).where(
                GovernAuditLog.module == "probe",
                GovernAuditLog.action == "transition",
                GovernAuditLog.entity_ref == str(fid),
            )
        )
    finally:
        db.close()
    log("full_transitions",
        legal=[t for t in results if t["ok"]], legal_ok=sum(1 for t in results if t["ok"]),
        legal_total=len(results), rejects=db_rejects, audit_rows=audit_count)
    return fid


def sample_exports(fid: int):
    r1 = requests.post(f"{BACKEND}/api/v1/probe-findings/export", headers=api_headers(),
                       json={"status": "open"}, timeout=30)
    r2 = requests.get(f"{BACKEND}/api/v1/value-domains/export?status=pending", headers=api_headers(),
                      timeout=30)
    def summarize(resp):
        rows = list(csv.reader(io.StringIO(resp.text)))
        return {
            "http": resp.status_code,
            "content_disposition": resp.headers.get("content-disposition", ""),
            "header": rows[0] if rows else [],
            "data_rows": max(0, len(rows) - 1),
        }
    log("export_findings", **summarize(r1))
    log("export_value_domains", **summarize(r2))
    (OUT / "export_probe_findings_sample.csv").write_text(r1.text, encoding="utf-8")
    (OUT / "export_value_domains_sample.csv").write_text(r2.text, encoding="utf-8")


def cleanup_throwaway():
    from app.core.db import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM asset.asset_probe_findings WHERE note LIKE '%throwaway-r166%' "
                        "OR object_desc LIKE '%throwaway-r166%'"))
        db.execute(text("DELETE FROM asset.asset_probe_runs WHERE run_id='probe-t-r166throwaway'"))
        # 值域三表按 key 前缀清（meaning/审计按设计保留——审计是证据链）
        ids = db.execute(text(
            "SELECT id FROM asset.asset_column_value_domains WHERE table_name='R166_THROWAWAY'"
        )).scalars().all()
        for did in ids:
            db.execute(text(f"DELETE FROM asset.asset_column_value_domain_evidences WHERE domain_id={did}"))
            db.execute(text(f"DELETE FROM asset.asset_column_value_domain_versions WHERE domain_id={did}"))
            db.execute(text(f"DELETE FROM asset.asset_column_value_domains WHERE id={did}"))
        db.execute(text("DELETE FROM asset.asset_columns WHERE table_name='R166_THROWAWAY'"))
        db.execute(text("DELETE FROM asset.asset_tables WHERE table_name='R166_THROWAWAY'"))
        db.execute(text("DELETE FROM asset.asset_api_keys WHERE key_name='throwaway-r166'"))
        db.execute(text("DELETE FROM asset.asset_user_roles WHERE user_identifier='throwaway-admin-r166'"))
        db.commit()
        # 复验清零
        left = db.execute(text(
            "SELECT (SELECT count(*) FROM asset.asset_probe_findings WHERE object_desc LIKE '%throwaway-r166%') "
            "AS f, (SELECT count(*) FROM asset.asset_column_value_domains WHERE table_name='R166_THROWAWAY') AS v, "
            "(SELECT count(*) FROM asset.asset_tables WHERE table_name='R166_THROWAWAY') AS t"
        )).first()
        log("cleanup", findings_left=left[0], value_domains_left=left[1], tables_left=left[2])
    finally:
        db.close()


def screenshots():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
        context = browser.new_context(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
        context.add_init_script(
            "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,"
            "refreshToken:'',username:'throwaway-admin-r166',nickname:'联调(隔离库)',roles:['platform_admin'],"
            "permissions:['*:*:*']})); document.cookie='multiple-tabs=true; path=/';")
        page = context.new_page()
        # 真实后端：仅注入 Authorization 头，不伪造响应
        def inject(route):
            headers = {**route.request.headers, "Authorization": f"Bearer {TOKEN}"}
            route.continue_(headers=headers)
        page.route("**/api/**", inject)

        def snap(url, name, wait=1200):
            page.goto(f"{FRONT}/#{url}", wait_until="networkidle")
            page.wait_for_timeout(wait)
            page.screenshot(path=str(SHOTS / name), full_page=True)
            print(f"[r166] shot {name}")

        snap("/probe-findings", "f4-empty-state.png")
        snap("/value-domains", "f2-empty-state.png")
        browser.close()


def screenshots_with_data(fid: int):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
        context = browser.new_context(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
        context.add_init_script(
            "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,"
            "refreshToken:'',username:'throwaway-admin-r166',nickname:'联调(隔离库)',roles:['platform_admin'],"
            "permissions:['*:*:*']})); document.cookie='multiple-tabs=true; path=/';")

        console_errors: list[str] = []

        def fresh_page():
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(f"pageerror: {err}"))

            def inject(route):
                headers = {**route.request.headers, "Authorization": f"Bearer {TOKEN}"}
                route.continue_(headers=headers)

            page.route("**/api/**", inject)
            return page

        # ① F4 列表
        page = fresh_page()
        page.goto(f"{FRONT}/#/probe-findings", wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.screenshot(path=str(SHOTS / "f4-list-throwaway.png"), full_page=True)
        print(f"[r166] shot f4-list-throwaway.png rows={page.locator('.el-table__row').count()}")
        # ② F4 详情抽屉（证据 SQL 脱敏代码块）
        try:
            page.locator(".el-table__row").first.click(timeout=15000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / "f4-detail-evidence.png"), full_page=True)
            print("[r166] shot f4-detail-evidence.png")
            # ③ F5 流转弹窗
            page.get_by_role("button", name="解决").first.click(timeout=10000)
            page.wait_for_timeout(900)
            page.screenshot(path=str(SHOTS / "f5-transition-dialog.png"), full_page=True)
            print("[r166] shot f5-transition-dialog.png")
        except Exception as exc:  # noqa: BLE001
            log("screenshot_f4_interactive", error=str(exc)[:300])
        page.close()

        # ④ F2 列表 + 冲突 Tab
        page = fresh_page()
        page.goto(f"{FRONT}/#/value-domains", wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.screenshot(path=str(SHOTS / "f2-list-throwaway.png"), full_page=True)
        print(f"[r166] shot f2-list-throwaway.png rows={page.locator('.el-table__row').count()}")
        try:
            page.locator(".el-tabs__item", has_text="冲突").click(timeout=10000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / "f2-conflict-tab.png"), full_page=True)
            print("[r166] shot f2-conflict-tab.png")
        except Exception as exc:  # noqa: BLE001
            log("screenshot_f2_conflict", error=str(exc)[:300])
        page.close()

        # ⑤ F1 表详情值域区块
        page = fresh_page()
        page.goto(f"{FRONT}/#/asset/tables/R166/R166_THROWAWAY", wait_until="networkidle")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "f1-table-detail-value-domains.png"), full_page=True)
        print("[r166] shot f1-table-detail-value-domains.png")
        page.close()

        log("console_errors", errors=console_errors[:20])
        browser.close()


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: capture_r166.py <empty|with_data|transitions|exports|cleanup>")
    step = sys.argv[1]
    if step == "empty":
        screenshots()
    elif step == "seed":
        seed_throwaway()
        seed_value_domain_via_api()
    elif step == "with_data":
        fid = requests.get(
            f"{BACKEND}/api/v1/probe-findings?probe_type=R-XSYS", headers=api_headers(), timeout=15
        ).json()["items"][0]["id"]
        screenshots_with_data(fid)
    elif step == "transitions":
        fid = run_full_transitions()
        sample_exports(fid)
    elif step == "cleanup":
        cleanup_throwaway()
    # 按 stage 合并写回（覆写会吞掉前序步骤证据——166 执行期实测教训）
    ev_path = OUT / "lianTiao_evidence.json"
    merged: dict = {"stages": []}
    if ev_path.exists():
        try:
            merged = json.loads(ev_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            merged = {"stages": []}
    seen = {s.get("stage") for s in merged.get("stages", [])}
    for entry in EVIDENCE["stages"]:
        if entry["stage"] in seen:
            merged["stages"] = [s for s in merged["stages"] if s.get("stage") != entry["stage"]]
        merged["stages"].append(entry)
    ev_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
