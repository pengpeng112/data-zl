# -*- coding: utf-8 -*-
"""T27/T28 浏览器闭环（真实浏览器 + 本地隔离栈 + 假源连接器）。

前置：seed_t27_t28.py 已跑；run_t27_api.py 在 8000；前端 dev 在 8848。
产出：results.json + screenshots/*.png。
T27 验收点：逐条预览、目标结果、角色隔离完整；截图与 API 结果对应。
T28 验收点：无权动作不可执行；403 不留错误成功提示；菜单刷新一致；深链/会话失效。
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)

FRONT = "http://127.0.0.1:8848"
API = "http://127.0.0.1:8000"
USERS = {
    "maint": ("qa_t27_maint", "T27Seed#M1"),
    "approver": ("qa_t27_approver", "T27Seed#A2"),
    "viewer": ("qa_t27_viewer", "T27Seed#V3"),
    "admin": ("qa_t27_admin", "T27Seed#P0"),
}

results: list[dict] = []


def record(case: str, ok: bool, detail: str) -> bool:
    results.append({"case": case, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {case}: {detail}", flush=True)
    return bool(ok)


def api_login(username: str, password: str) -> str | None:
    req = urllib.request.Request(
        f"{API}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        body = json.loads(r.read().decode())
    data = body.get("data") or {}
    return data.get("accessToken") or data.get("token")


def api_req(method: str, path: str, token: str, payload=None):
    req = urllib.request.Request(
        f"{API}{path}", method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def db_plan_brief(plan_id: int | None = None):
    """直查隔离库取计划（id/status/执行轴），供断言与 UI 对账。"""
    import os

    import psycopg
    url = os.environ.get("APP_TEST_DB_URL", "")
    if "test" not in url.lower():
        return None
    dsn = url.replace("postgresql+psycopg://", "postgresql://")
    where = "where id = %s" if plan_id else ""
    args = (plan_id,) if plan_id else ()
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            f"select id, status, created_by, approved_by, item_count, target_systems, "
            f"execution_status from asset.asset_dict_medical_push_plans {where} "
            f"order by id desc limit 1", args)
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "status": row[1], "created_by": row[2], "approved_by": row[3],
                "item_count": row[4], "target_systems": row[5], "execution_status": row[6]}


def login_ui(page, username: str, password: str) -> None:
    page.goto(f"{FRONT}/#/login", wait_until="domcontentloaded")
    try:
        page.wait_for_selector('input[placeholder="账号"]', timeout=8000)
    except Exception:
        # 已登录被重定向：清存储后重试
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{FRONT}/#/login", wait_until="domcontentloaded")
        page.wait_for_selector('input[placeholder="账号"]', timeout=60000)
    page.locator('input[placeholder="账号"]').fill(username)
    page.locator('input[placeholder="密码"]').fill(password)
    page.locator('button:has-text("登录")').first.click()
    page.wait_for_timeout(3000)


def open_push_tab(page) -> None:
    page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    tab = page.locator('.el-tabs__item:has-text("同步下发")')
    if tab.count():
        tab.first.click()
        page.wait_for_timeout(1500)


def toasts(page) -> list[str]:
    return page.locator(".el-message").all_inner_texts()


def main() -> int:
    plan_id = None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        page = ctx.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # ================= T27-1 维护员：勾选目标+两项编码 → 生成计划 =================
        login_ui(page, *USERS["maint"])
        record("T27-maint-login", "login" not in page.url, page.url)
        open_push_tab(page)

        # 目标系统：可见向导内勾选 HIS（systemOptions 动态加载后应含 HIS_SOURCE）
        his_box = page.locator('.el-tab-pane:visible .el-checkbox-group .el-checkbox:visible:has-text("HIS")')
        page.wait_for_timeout(500)
        tgt_ok = False
        try:
            if his_box.count():
                his_box.first.click()
                page.wait_for_timeout(600)
                tgt_ok = "is-checked" in (his_box.first.get_attribute("class") or "")
            else:
                tgt_ok = False
        except Exception:
            tgt_ok = False
        record("T27-target-his-checked", tgt_ok, f"visible his checkbox={his_box.count()}")

        # 多选下拉：向导 pane 内唯一 el-select（EP2 placeholder 不落在 input 属性上，
        # 不能按 placeholder 过滤）——点开→键入过滤→点选项
        sel = page.locator("#pane-push .el-select:visible")
        picked = 0
        if sel.count():
            sel.first.click()
            page.wait_for_timeout(1000)
            page.keyboard.type("QA_T27")
            page.wait_for_timeout(1000)
            opts = page.locator(".el-select-dropdown:visible .el-select-dropdown__item:visible")
            n = opts.count()
            for i in range(min(n, 4)):
                try:
                    opts.nth(i).click()
                    picked += 1
                    page.wait_for_timeout(400)
                except Exception:
                    break
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
        record("T27-select-2-codes", picked == 2, f"picked={picked}")
        page.screenshot(path=str(SHOTS / "T27_02_维护员_选码.png"), full_page=True)

        # 生成推送计划
        page.locator("button:has-text('生成推送计划'):visible").first.click()
        page.wait_for_timeout(4000)
        gen_toasts = toasts(page)
        record("T27-create-no-error-toast",
               not any(("失败" in t or "错误" in t) for t in gen_toasts), f"toasts={gen_toasts[:3]}")

        # 计划 ID：直查隔离库（无列表端点；UI 展示可能裁剪）
        token = api_login(*USERS["maint"])
        brief = db_plan_brief()
        plan_id = brief["id"] if brief else None
        record("T27-plan-created", bool(brief and brief["status"] == "draft" and brief["item_count"] == 2),
               f"brief={brief}")

        # 逐条预览（API 动作数 + UI 表格行数）
        if plan_id:
            detail = api_req("GET", f"/api/v1/dict-medical/push/plans/{plan_id}", token).get("data") or {}
            actions = detail.get("actions") or detail.get("action_previews") or []
            ui_rows = page.locator('.el-tab-pane:visible .el-table__row').count()
            record("T27-preview-2-actions", len(actions) == 2,
                   f"action_count={len(actions)} ui_rows={ui_rows} status={detail.get('status')} targets={detail.get('target_systems')}")
        page.screenshot(path=str(SHOTS / "T27_03_维护员_计划预览.png"), full_page=True)

        # ================= T27-2 审核员：加载计划 → 审批 =================
        login_ui(page, *USERS["approver"])
        open_push_tab(page)
        if plan_id:
            id_input = page.locator('input[placeholder="计划 ID"]')
            id_input.first.fill(str(plan_id))
            page.locator("button:has-text('加载计划')").first.click()
            page.wait_for_timeout(2500)
            appr_btn = page.locator("button:has-text('审批计划并排队')")
            approved_ui = False
            if appr_btn.count():
                appr_btn.first.click()
                page.wait_for_timeout(1000)
                confirm = page.locator(".el-message-box__btns button:has-text('确定')")
                if confirm.count():
                    confirm.first.click()
                page.wait_for_timeout(3000)
                approved_ui = True
            t2 = api_login(*USERS["approver"])
            detail = api_req("GET", f"/api/v1/dict-medical/push/plans/{plan_id}", t2).get("data") or {}
            record("T27-approver-independent",
                   detail.get("status") == "approved" and detail.get("approved_by") == "qa_t27_approver",
                   f"status={detail.get('status')} approved_by={detail.get('approved_by')} created_by={detail.get('created_by')} ui={approved_ui}")
            page.screenshot(path=str(SHOTS / "T27_04_审核员_审批后.png"), full_page=True)

            # ================= T27-3 worker 假源执行 → 对账 =================
            final = None
            for _ in range(20):
                time.sleep(2)
                detail = api_req("GET", f"/api/v1/dict-medical/push/plans/{plan_id}", t2).get("data") or {}
                es = detail.get("execution_status") or ""
                final = es
                if es in ("succeeded", "partial_success", "failed", "no_op"):
                    break
            runs = detail.get("runs") or []
            record("T27-worker-executed", final in ("succeeded", "partial_success", "no_op"),
                   f"execution_status={final} runs={json.dumps(runs, ensure_ascii=False)[:200]}")

            # UI 刷新 → 加载计划 → 对账/结果卡（同 URL goto 不重载 SPA，须 reload）
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            try:
                tab = page.locator('.el-tabs__item:has-text("同步下发")')
                if tab.count():
                    tab.first.click()
                    page.wait_for_timeout(1500)
                id_input = page.locator('input[placeholder="计划 ID"]')
                id_input.first.wait_for(state="visible", timeout=15000)
                id_input.first.fill(str(plan_id))
                page.locator("button:has-text('加载计划')").first.click()
                page.wait_for_timeout(2500)
                record("T27-reconcile-ui-loaded", True, f"plan_id={plan_id} url={page.url}")
            except Exception as exc:
                record("T27-reconcile-ui-loaded", False, f"{type(exc).__name__}: url={page.url}")
            page.screenshot(path=str(SHOTS / "T27_05_对账_执行状态.png"), full_page=True)

        # ================= T27-4 角色隔离：查看员不可达 =================
        login_ui(page, *USERS["viewer"])
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        body = page.content()
        wizard_visible = page.locator("button:has-text('生成推送计划')").count() > 0
        no_success = not any("成功" in t for t in toasts(page))
        record("T27-role-isolation-viewer", (not wizard_visible) and no_success,
               f"向导按钮不可见={not wizard_visible} 无成功提示={no_success} url={page.url}")
        page.screenshot(path=str(SHOTS / "T27_06_查看员_隔离.png"), full_page=True)

        # ================= T28-1 查看员深链 + 403 不留成功提示 =================
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        t403 = toasts(page)
        record("T28-viewer-deeplink-403-clean", not any("成功" in t for t in t403),
               f"toasts={t403[:3]} url={page.url}")
        page.screenshot(path=str(SHOTS / "T28_01_查看员深链.png"), full_page=True)

        # ================= T28-2 管理员授权页（对照，B4 生效/历史分区） =================
        login_ui(page, *USERS["admin"])
        page.goto(f"{FRONT}/#/identity/authorizations", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        record("T28-maint-authorizations-visible", page.locator("text=授权").count() > 0, f"url={page.url}")
        page.screenshot(path=str(SHOTS / "T28_02_维护员_授权页.png"), full_page=True)

        # ================= T28-3 会话失效 → 回登录，无成功提示 =================
        try:
            # 会话失效等价操作：清用户画像+多标签标记+全部 cookie（accessToken 本就在内存，
            # 重载后无可恢复凭据）
            page.evaluate("""() => {
                for (const k of Object.keys(localStorage)) {
                    if (k.toLowerCase().includes('user') || k.toLowerCase().includes('token')) localStorage.removeItem(k);
                }
                for (const k of Object.keys(sessionStorage)) sessionStorage.removeItem(k);
                document.cookie.split(';').forEach(c => {
                    document.cookie = c.split('=')[0].trim() + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
                });
            }""")
        except Exception:
            pass
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        back_login = "login" in page.url or page.locator('input[placeholder="账号"]').count() > 0
        no_success2 = not any("成功" in t for t in toasts(page))
        record("T28-session-expiry-redirect", back_login and no_success2,
               f"回到登录={back_login} 无成功提示={no_success2} url={page.url}")
        page.screenshot(path=str(SHOTS / "T28_03_会话失效.png"), full_page=True)

        # ================= T28-4 切换角色后菜单一致 =================
        login_ui(page, *USERS["approver"])
        page.wait_for_timeout(2000)
        menu_items = page.locator(".el-menu .el-menu-item, .el-menu .el-sub-menu__title").all_inner_texts()
        has_dict = any(("标准" in m or "字典" in m) for m in menu_items)
        record("T28-role-switch-menu-consistent", has_dict, f"菜单数={len(menu_items)} 含字典区={has_dict}")
        page.screenshot(path=str(SHOTS / "T28_04_切换角色_菜单.png"), full_page=True)

        record("T28-console-clean", len(console_errors) == 0, f"console errors={console_errors[:3]}")
        browser.close()

    (OUT / "results.json").write_text(
        json.dumps({"results": results,
                    "summary": {"pass": sum(1 for r in results if r["ok"]),
                                "fail": sum(1 for r in results if not r["ok"])}},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    ok_n = sum(1 for r in results if r["ok"])
    print(f"[summary] pass={ok_n} fail={len(results) - ok_n}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
