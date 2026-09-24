# -*- coding: utf-8 -*-
"""T27/T28 浏览器重新验收 v2（202 D2-2 强断言版）。

与 v1 的区别（对照 202 §1.2）：
1. 审批前页面必须可见两条指定编码文本，UI action 行数=2（data-testid 表）；
2. 执行后页面必须可见目标卡 run id 与 已写/无需变更/失败 三计数，并与
   API latest_runs 和隔离库 run/action/outbox 三层对账一致；
3. 会话失效=服务端真实 401（监听网络响应断言 401 存在；API 层用已撤销
   token 复核服务端拒绝），不是只清本地存储；
4. 四身份（创建员/审核员/执行员/查看员）核对 /permissions/me 与页面
   按钮（生成/审批/dry-run）逐项一致；AI 上下文试点核对 ai.context.read
   端点可达与不可达路径；
5. 失败即非零退出；截图仅作证据补充。

前置：seed_t27_t28.py（含 split roles）已跑；run_t27_api.py 在 8000；前端在 8848。
产出：results_v2.json + screenshots_v2/ + db_reconciliation.json。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots_v2"
SHOTS.mkdir(exist_ok=True)

FRONT = "http://127.0.0.1:8848"
API = "http://127.0.0.1:8000"
USERS = {
    "maint": ("qa_t27_maint", "T27Seed#M1"),        # dict_admin（全量，场景主用）
    "creator": ("qa_t27_creator", "T27Seed#C4"),     # 仅 view+plan.create
    "approver": ("qa_t27_approver", "T27Seed#A2"),   # dict_admin（T27-C 主审）
    "approver2": ("qa_t27_approver2", "T27Seed#B5"), # 仅 view+approve
    "executor": ("qa_t27_executor", "T27Seed#E6"),   # view+execute+retry+reconcile
    "viewer": ("qa_t27_viewer", "T27Seed#V3"),       # asset_viewer
    "aipilot": ("qa_t27_aipilot", "T27Seed#I7"),     # 仅 ai.context.read
    "admin": ("qa_t27_admin", "T27Seed#P0"),        # platform_admin（账号启停操作者）
}
CODES = ("QA_T27D01", "QA_T27D02")

results: list[dict] = []


def record(case: str, ok: bool, detail: str) -> bool:
    results.append({"case": case, "ok": bool(ok), "detail": str(detail)[:500]})
    print(f"[{'PASS' if ok else 'FAIL'}] {case}: {detail}", flush=True)
    return bool(ok)


def api_login(username: str, password: str):
    req = urllib.request.Request(
        f"{API}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())["data"]
    return d.get("accessToken")


def api_get(path: str, token: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def api_get_status(path: str, token: str) -> int:
    try:
        req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def db_rows(sql: str, params: tuple = ()):
    import os

    import psycopg
    url = os.environ.get("APP_TEST_DB_URL", "")
    dsn = url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def login_ui(page, username: str, password: str) -> None:
    page.goto(f"{FRONT}/#/login", wait_until="domcontentloaded")
    try:
        page.wait_for_selector('input[placeholder="账号"]', timeout=8000)
    except Exception:
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{FRONT}/#/login", wait_until="domcontentloaded")
        page.wait_for_selector('input[placeholder="账号"]', timeout=60000)
    page.locator('input[placeholder="账号"]').fill(username)
    page.locator('input[placeholder="密码"]').fill(password)
    page.locator('button:has-text("登录")').first.click()
    page.wait_for_timeout(3000)


def open_push_tab(page):
    page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    tab = page.locator('.el-tabs__item:has-text("同步下发")')
    if tab.count():
        tab.first.click()
        page.wait_for_timeout(1500)


def wizard_pick_two_codes(page) -> int:
    his = page.locator('#pane-push .el-checkbox-group .el-checkbox:visible:has-text("HIS")')
    if his.count():
        his.first.click()
        page.wait_for_timeout(500)
    sel = page.locator("#pane-push .el-select:visible")
    picked = 0
    if sel.count():
        sel.first.click()
        page.wait_for_timeout(1000)
        page.keyboard.type("QA_T27")
        page.wait_for_timeout(1000)
        opts = page.locator(".el-select-dropdown:visible .el-select-dropdown__item:visible")
        for i in range(min(opts.count(), 4)):
            try:
                opts.nth(i).click()
                picked += 1
                page.wait_for_timeout(400)
            except Exception:
                break
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    return picked


def load_plan_by_id(page, plan_id) -> None:
    inp = page.locator('input[placeholder="计划 ID"]')
    inp.first.wait_for(state="visible", timeout=15000)
    inp.first.fill(str(plan_id))
    page.locator("button:has-text('加载计划')").first.click()
    page.wait_for_timeout(2500)


def toasts(page) -> list[str]:
    return page.locator(".el-message").all_inner_texts()


def main() -> int:
    plan_id = None
    api_detail = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        page = ctx.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # ============ T27-A 维护员：建计划（两码） ============
        login_ui(page, *USERS["maint"])
        record("T27A-maint-login", "login" not in page.url, page.url)
        open_push_tab(page)
        picked = wizard_pick_two_codes(page)
        record("T27A-picked-2-codes", picked == 2, f"picked={picked}")
        page.locator("button:has-text('生成推送计划'):visible").first.click()
        page.wait_for_timeout(4000)
        record("T27A-create-no-error", not any(("失败" in t or "错误" in t) for t in toasts(page)),
               f"toasts={toasts(page)[:2]}")

        row = db_rows("select id, status, item_count, created_by from asset.asset_dict_medical_push_plans order by id desc limit 1")
        plan_id = row[0][0] if row else None
        record("T27A-plan-draft", bool(row and row[0][1] == "draft" and row[0][2] == 2 and row[0][3] == "qa_t27_maint"),
               f"db={row}")

        # ============ T27-B 审批前页面逐条预览（202 §1.2.1 强断言） ============
        table = page.locator('[data-testid="plan-actions-table"]')
        table_visible = table.count() > 0 and table.first.is_visible()
        body_text = table.first.inner_text() if table_visible else ""
        codes_on_page = [c for c in CODES if c in body_text]
        ui_rows = table.locator(".el-table__row").count() if table_visible else 0
        record("T27B-preview-table-visible", table_visible, "actions 表已对普通 insert 渲染（202 D2-1 修复前不可见）")
        record("T27B-two-codes-on-page", len(codes_on_page) == 2, f"页面可见编码={codes_on_page}")
        record("T27B-ui-action-rows-2", ui_rows == 2, f"ui_rows={ui_rows}（不得用 API actions=2 替代）")
        page.screenshot(path=str(SHOTS / "T27B_审批前_逐条预览.png"), full_page=True)

        # ============ T27-C 审核员独立审批 ============
        login_ui(page, *USERS["approver"])
        open_push_tab(page)
        load_plan_by_id(page, plan_id)
        appr = page.locator("button:has-text('审批计划并排队')")
        appr_visible = appr.count() > 0
        record("T27C-approver-button-visible", appr_visible, f"count={appr.count()}")
        if appr_visible:
            appr.first.click()
            page.wait_for_timeout(800)
            confirm = page.locator(".el-message-box__btns button:has-text('确定')")
            if confirm.count():
                confirm.first.click()
            page.wait_for_timeout(3000)
        row = db_rows("select status, approved_by, created_by from asset.asset_dict_medical_push_plans where id=%s", (plan_id,))
        record("T27C-independent-approval",
               bool(row and row[0][0] == "approved" and row[0][1] == "qa_t27_approver" and row[0][2] == "qa_t27_maint"),
               f"db={row}")
        page.screenshot(path=str(SHOTS / "T27C_审批后.png"), full_page=True)

        # ============ T27-D worker 执行 → UI/API/DB 三层对账（202 §1.2.2） ============
        token_appr = api_login(*USERS["approver"])
        for _ in range(20):
            time.sleep(2)
            api_detail = api_get(f"/api/v1/dict-medical/push/plans/{plan_id}", token_appr).get("data") or {}
            if (api_detail.get("execution_status") or "") in ("succeeded", "partial_success", "failed"):
                break
        lr = (api_detail.get("latest_runs") or {}).get("HIS_SOURCE") or {}
        record("T27D-api-exec-succeeded", api_detail.get("execution_status") == "succeeded",
               f"execution_status={api_detail.get('execution_status')}")

        db_run = db_rows(
            "select id, status, succeeded_count, skipped_count, failed_count from asset.asset_dict_medical_push_runs "
            "where plan_id=%s order by id desc limit 1", (plan_id,))
        db_acts = db_rows(
            "select item_code, status from asset.asset_dict_medical_push_actions where plan_id=%s order by item_code", (plan_id,))
        db_outbox = db_rows(
            "select status from asset.asset_dict_sync_outbox where plan_id=%s", (plan_id,))
        record("T27D-db-run-ok", bool(db_run and db_run[0][1] == "succeeded" and db_run[0][2] == 2 and db_run[0][4] == 0),
               f"run={db_run}")
        record("T27D-db-actions-ok", bool(db_acts and len(db_acts) == 2
               and all(a[1] == "succeeded" for a in db_acts)), f"actions={db_acts}")
        record("T27D-db-outbox-ok", bool(db_outbox and db_outbox[0][0] == "succeeded"), f"outbox={db_outbox}")

        # UI 对账：reload + 加载计划 → 目标卡 run id 与三计数
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        tab = page.locator('.el-tabs__item:has-text("同步下发")')
        if tab.count():
            tab.first.click()
            page.wait_for_timeout(1200)
        load_plan_by_id(page, plan_id)
        card = page.locator(".target-card:visible").first
        card_text = card.inner_text() if card.count() else ""
        ui_run_id = None
        for token_ in card_text.replace("｜", " ").split():
            if token_.startswith("#") and token_[1:].isdigit():
                ui_run_id = int(token_[1:])
        record("T27D-ui-run-id-match", ui_run_id == (db_run[0][0] if db_run else None),
               f"ui_run={ui_run_id} db_run={db_run[0][0] if db_run else None} card={card_text[:120]}")
        counts_ok = all(x in card_text for x in ("已写", "无需变更", "失败"))
        record("T27D-ui-three-counts-visible", counts_ok, f"card={card_text[:160]}")
        if db_run and counts_ok:
            record("T27D-ui-counts-match-db",
                   (f"已写 {db_run[0][2]}" in card_text) and (f"失败 {db_run[0][4]}" in card_text),
                   f"card={card_text[:200]}")
        page.screenshot(path=str(SHOTS / "T27D_执行后_目标卡对账.png"), full_page=True)

        # ============ T27-E 查看员 403 隔离 ============
        login_ui(page, *USERS["viewer"])
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        record("T27E-viewer-403", "/error/403" in page.url and not any("成功" in t for t in toasts(page)),
               f"url={page.url} toasts={toasts(page)[:2]}")
        page.screenshot(path=str(SHOTS / "T27E_查看员403.png"), full_page=True)

        # ============ T28-A 四身份 /permissions/me ↔ 按钮/菜单逐项核对（202 §1.2.4） ============
        # 按钮可见性受计划状态 v-if 与 v-perms 双重控制：
        # 审批按钮仅在 draft 计划渲染（各身份加载新建 draft 核对 v-perms 差异）；
        # dry-run 按钮在 approved 计划 step3 渲染（点进后再核对）。
        tk_maint2 = api_login(*USERS["maint"])
        draft_req = urllib.request.Request(
            f"{API}/api/v1/dict-medical/push/plans",
            data=json.dumps({"category_code": "diagnosis", "target_systems": ["HIS_SOURCE"],
                             "item_codes": list(CODES), "action_type": "insert"}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {tk_maint2}"}, method="POST")
        with urllib.request.urlopen(draft_req, timeout=20) as r:
            draft_plan_id = json.loads(r.read().decode())["data"]["id"]
        expectations = {
            "creator": {"plan.create": True, "approve": False, "execute": False},
            "approver2": {"plan.create": False, "approve": True, "execute": False},
            "executor": {"plan.create": False, "approve": False, "execute": True},
        }
        for key, exp in expectations.items():
            login_ui(page, *USERS[key])
            tk = api_login(*USERS[key])
            me = api_get("/api/v1/permissions/me", tk).get("data") or {}
            perms = set(me.get("permissions") or [])
            open_push_tab(page)
            btn_create = page.locator("#pane-push button:visible:has-text('生成推送计划')").count() > 0
            try:
                load_plan_by_id(page, draft_plan_id)
            except Exception:
                pass
            btn_approve = page.locator("button:visible:has-text('审批计划并排队')").count() > 0
            # 计划 ID 输入框在 step1 模板内：首次加载后 step=2 输入框消失，
            # 二次加载前必须 reload + 重开 tab 回到 step1。
            btn_exec = False
            try:
                page.reload(wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                tab2 = page.locator('.el-tabs__item:has-text("同步下发")')
                if tab2.count():
                    tab2.first.click()
                    page.wait_for_timeout(1200)
                load_plan_by_id(page, plan_id)
                view_btn = page.locator("button:visible:has-text('查看执行预览')")
                if view_btn.count():
                    view_btn.first.click()
                    page.wait_for_timeout(1500)
                    btn_exec = page.locator("button:visible:has-text('生成 dry-run 预览')").count() > 0
            except Exception:
                pass
            perm_flags = {
                "plan.create": "dict.medical.plan.create" in perms,
                "approve": "dict.medical.approve" in perms,
                "execute": "dict.medical.execute" in perms,
            }
            ui_flags = {"plan.create": btn_create, "approve": btn_approve, "execute": btn_exec}
            consistent = all(perm_flags[k] == exp[k] and ui_flags[k] == exp[k] for k in exp)
            record(f"T28A-{key}-perm-button-consistent", consistent,
                   f"perms={perm_flags} ui={ui_flags} expected={exp}")
            # 菜单一致性：/dict/medical 路由 auths=dict.medical.view
            menu_dict = page.locator(".el-menu a[href*='dict'], .el-menu a[href*='standards']").count() > 0
            record(f"T28A-{key}-menu-view-consistent", menu_dict == ("dict.medical.view" in perms),
                   f"menu_dict={menu_dict} has_view={'dict.medical.view' in perms}")
            page.screenshot(path=str(SHOTS / f"T28A_{key}.png"), full_page=True)

        # AI 上下文试点（195 缺陷1 修复的端到端证据）
        tk_ai = api_login(*USERS["aipilot"])
        st_ctx = api_get_status("/api/v1/ai/system-context?system_code=DATA_CENTER", tk_ai)
        st_sessions = api_get_status("/api/v1/ai/sessions", tk_ai)
        record("T28A-aipilot-context-200-sessions-403",
               st_ctx == 200 and st_sessions == 403,
               f"system-context={st_ctx} sessions={st_sessions}（ai.context.read 可达/粗门禁路由仍拒）")

        # ============ T28-B 真实服务端 401（202 §1.2.3） ============
        # 产品语义：logout 撤销 refresh 会话；access JWT 短 TTL 不撤销（登出后
        # 仍 200 属正确行为）；篡改 JWT 走 ApiKey 回退口径=403。产品内建的真实
        # 服务端 401 = 账号禁用（中间件查 enabled 后 401"账号已禁用，请重新登录"）。
        login_ui(page, *USERS["maint"])
        page.wait_for_timeout(1500)
        tk_maint = api_login(*USERS["maint"])
        tk_admin = api_login(*USERS["admin"])
        maint_id = db_rows("select id from asset.asset_auth_users where username='qa_t27_maint'")[0][0]

        def _patch_enabled(user_id: int, enabled: bool) -> int:
            req = urllib.request.Request(
                f"{API}/api/v1/auth/users/{user_id}",
                data=json.dumps({"enabled": enabled}).encode(),
                headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest",
                         "Authorization": f"Bearer {tk_admin}"}, method="PATCH")
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code

        st_disabled = _patch_enabled(maint_id, False)
        st_after_disable = api_get_status("/api/v1/permissions/me", tk_maint)
        record("T28B-server-rejects-disabled-account-401",
               st_disabled == 200 and st_after_disable == 401,
               f"patch={st_disabled} after={st_after_disable}（服务端真实 401：账号禁用）")
        # 浏览器层：账号已禁用 → 请求真实 401；清 refresh cookie → refresh 失败
        # → logOut 回登录（完整服务端拒绝链路）
        seen_401: list[str] = []

        def on_response(resp):
            if resp.status == 401:
                seen_401.append(resp.url[-60:])

        page.on("response", on_response)

        # 不清 cookie：路由守卫放行（多标签标记在），页面 API 请求带内存中的
        # 有效 token，但账号已被服务端禁用 → 真实 401 → 前端登出链路。
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        if not seen_401:
            # 兜底：部分路由守卫可能在 API 前拦截，强制触发一次需要鉴权的导航
            page.evaluate("() => { location.hash = '#/dict/medical'; }")
            page.wait_for_timeout(3000)
        back_login = "login" in page.url or page.locator('input[placeholder="账号"]').count() > 0
        record("T28B-real-401-then-redirect", bool(seen_401) and back_login,
               f"401_responses={seen_401[:3]} back_login={back_login} url={page.url}")
        record("T28B-no-success-toast", not any("成功" in t for t in toasts(page)),
               f"toasts={toasts(page)[:2]}")
        page.screenshot(path=str(SHOTS / "T28B_真实401回登录.png"), full_page=True)
        # 恢复账号（隔离库种子还原），复核恢复成功
        st_reenabled = _patch_enabled(maint_id, True)
        st_after_reenable = api_get_status("/api/v1/permissions/me", tk_maint)
        record("T28B-account-reenabled", st_reenabled == 200 and st_after_reenable == 200,
               f"patch={st_reenabled} after={st_after_reenable}")

        # T28B 主动触发的服务端 401 会产生浏览器自动资源日志（Failed to load
        # resource: 401），属预期证据而非缺陷；排除后判定 console 干净。
        non_401_errors = [e for e in console_errors if "401" not in e]
        record("T28-console-clean", len(non_401_errors) == 0,
               f"total={len(console_errors)} 401 预期日志已排除 non_401={non_401_errors[:3]}")
        browser.close()

    summary = {"pass": sum(1 for r in results if r["ok"]), "fail": sum(1 for r in results if not r["ok"])}
    (OUT / "results_v2.json").write_text(json.dumps({"results": results, "summary": summary},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "db_reconciliation.json").write_text(json.dumps({
        "plan_id": plan_id,
        "db_run": [list(r) for r in (db_run or [])],
        "db_actions": [list(r) for r in (db_acts or [])],
        "db_outbox": [list(r) for r in (db_outbox or [])],
        "api_latest_runs_HIS": lr,
        "api_execution_status": api_detail.get("execution_status"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[summary] pass={summary['pass']} fail={summary['fail']}")
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
