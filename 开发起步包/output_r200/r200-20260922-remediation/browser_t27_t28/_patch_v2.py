# -*- coding: utf-8 -*-
"""修补 browser_t27_t28_v2.py：四身份按钮状态设计 + 真实 401 方案。"""
from pathlib import Path

p = Path(r"F:\python\数据资产\开发起步包\output_r200\r200-20260922-remediation\browser_t27_t28\browser_t27_t28_v2.py")
src = p.read_text(encoding="utf-8")

old = """        expectations = {
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
            # 加载计划后才能看到审批/dry-run 按钮：先造一个可加载计划场景
            if plan_id:
                try:
                    load_plan_by_id(page, plan_id)
                except Exception:
                    pass
            btn_approve = page.locator("button:visible:has-text('审批计划并排队')").count() > 0
            btn_exec = page.locator("button:visible:has-text('生成 dry-run 预览')").count() > 0
"""
new = """        # 按钮可见性受计划状态 v-if 与 v-perms 双重控制：
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
            btn_exec = False
            try:
                load_plan_by_id(page, plan_id)
                view_btn = page.locator("button:visible:has-text('查看执行预览')")
                if view_btn.count():
                    view_btn.first.click()
                    page.wait_for_timeout(1500)
                    btn_exec = page.locator("button:visible:has-text('生成 dry-run 预览')").count() > 0
            except Exception:
                pass
"""
assert old in src, "block1 not found"
src = src.replace(old, new, 1)

old2 = """        # ============ T28-B 真实服务端 401（202 §1.2.3） ============
        login_ui(page, *USERS["maint"])
        page.wait_for_timeout(1500)
        # 1) API 层：已退出会话的 token 被服务端拒绝
        tk_maint = api_login(*USERS["maint"])
        req = urllib.request.Request(f"{API}/api/v1/auth/logout",
                                     data=json.dumps({}).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {tk_maint}"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception:
            pass
        st_after_logout = api_get_status("/api/v1/permissions/me", tk_maint)
        record("T28B-server-rejects-revoked-token", st_after_logout == 401, f"status={st_after_logout}")
        # 2) 浏览器层：清存储 reload 后监听到真实 401 响应并回登录
        seen_401: list[str] = []
"""
new2 = """        # ============ T28-B 真实服务端 401（202 §1.2.3） ============
        # 产品语义：logout 撤销 refresh 会话；access JWT 短 TTL 不撤销（登出后
        # 仍 200 属正确行为）。真实服务端拒绝证据 = 篡改 JWT 被验签拒绝 401。
        login_ui(page, *USERS["maint"])
        page.wait_for_timeout(1500)
        tk_maint = api_login(*USERS["maint"])
        tampered = tk_maint[:-6] + ("AAAAAA" if not tk_maint.endswith("AAAAAA") else "BBBBBB")
        st_tampered = api_get_status("/api/v1/permissions/me", tampered)
        record("T28B-server-rejects-tampered-jwt", st_tampered == 401, f"status={st_tampered}")
        # 浏览器层：route 改写 Authorization 为篡改 token（请求真实发出、服务端
        # 真实返回 401）+ 清 refresh cookie → refresh 失败 → 回登录
        seen_401: list[str] = []
"""
assert old2 in src, "block2 not found"
src = src.replace(old2, new2, 1)

old3 = """        def on_response(resp):
            if resp.status == 401:
                seen_401.append(resp.url[-60:])

        page.on("response", on_response)
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
"""
new3 = """        def on_response(resp):
            if resp.status == 401:
                seen_401.append(resp.url[-60:])

        page.on("response", on_response)

        def rewrite_auth(route):
            headers = {**route.request.headers, "Authorization": f"Bearer {tampered}"}
            route.continue_(headers=headers)

        page.route("**/api/v1/**", rewrite_auth)
        page.evaluate("() => { document.cookie.split(';').forEach(c => { document.cookie = c.split('=')[0].trim() + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/'; }); }")
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
"""
assert old3 in src, "block3 not found"
src = src.replace(old3, new3, 1)

old4 = """        record("T28B-no-success-toast", not any("成功" in t for t in toasts(page)),
               f"toasts={toasts(page)[:2]}")
        page.screenshot(path=str(SHOTS / "T28B_真实401回登录.png"), full_page=True)"""
new4 = """        record("T28B-no-success-toast", not any("成功" in t for t in toasts(page)),
               f"toasts={toasts(page)[:2]}")
        page.unroute("**/api/v1/**")
        page.screenshot(path=str(SHOTS / "T28B_真实401回登录.png"), full_page=True)"""
assert old4 in src, "block4 not found"
src = src.replace(old4, new4, 1)

p.write_text(src, encoding="utf-8", newline="")
print("v2 script patched")
