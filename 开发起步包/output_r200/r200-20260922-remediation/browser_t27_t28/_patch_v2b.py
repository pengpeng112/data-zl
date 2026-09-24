# -*- coding: utf-8 -*-
"""v2 第二轮修补：executor 二次加载前重置向导 + 真实 401 改用账号禁用路径。"""
from pathlib import Path

p = Path(r"F:\python\数据资产\开发起步包\output_r200\r200-20260922-remediation\browser_t27_t28\browser_t27_t28_v2.py")
src = p.read_text(encoding="utf-8")

# 1) executor：第二次 load 前重置（计划 ID 输入框在 step1，加载后消失）
old = """            btn_approve = page.locator("button:visible:has-text('审批计划并排队')").count() > 0
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
new = """            btn_approve = page.locator("button:visible:has-text('审批计划并排队')").count() > 0
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
"""
assert old in src, "executor block not found"
src = src.replace(old, new, 1)

# 2) T28-B：真实 401 = 账号禁用（产品内建服务端 401 语义）
old2 = """        # 产品语义：logout 撤销 refresh 会话；access JWT 短 TTL 不撤销（登出后
        # 仍 200 属正确行为）。真实服务端拒绝证据 = 篡改 JWT 被验签拒绝 401。
        login_ui(page, *USERS["maint"])
        page.wait_for_timeout(1500)
        tk_maint = api_login(*USERS["maint"])
        tampered = tk_maint[:-6] + ("AAAAAA" if not tk_maint.endswith("AAAAAA") else "BBBBBB")
        st_tampered = api_get_status("/api/v1/permissions/me", tampered)
        record("T28B-server-rejects-tampered-jwt", st_tampered == 401, f"status={st_tampered}")
"""
new2 = """        # 产品语义：logout 撤销 refresh 会话；access JWT 短 TTL 不撤销（登出后
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
"""
assert old2 in src, "T28B block1 not found"
src = src.replace(old2, new2, 1)

# 3) 浏览器层：禁用态请求 → 真实 401 → 回登录；结束后恢复账号
old3 = """        # 浏览器层：route 改写 Authorization 为篡改 token（请求真实发出、服务端
        # 真实返回 401）+ 清 refresh cookie → refresh 失败 → 回登录
        seen_401: list[str] = []
"""
new3 = """        # 浏览器层：账号已禁用 → 请求真实 401；清 refresh cookie → refresh 失败
        # → logOut 回登录（完整服务端拒绝链路）
        seen_401: list[str] = []
"""
assert old3 in src, "T28B block2 not found"
src = src.replace(old3, new3, 1)

old4 = """        def rewrite_auth(route):
            headers = {**route.request.headers, "Authorization": f"Bearer {tampered}"}
            route.continue_(headers=headers)

        page.route("**/api/v1/**", rewrite_auth)
        page.evaluate("() => { document.cookie.split(';').forEach(c => { document.cookie = c.split('=')[0].trim() + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/'; }); }")
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
"""
new4 = """        page.evaluate("() => { document.cookie.split(';').forEach(c => { document.cookie = c.split('=')[0].trim() + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/'; }); }")
        page.goto(f"{FRONT}/#/dict/medical", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
"""
assert old4 in src, "T28B block3 not found"
src = src.replace(old4, new4, 1)

old5 = """        page.unroute("**/api/v1/**")
        page.screenshot(path=str(SHOTS / "T28B_真实401回登录.png"), full_page=True)"""
new5 = """        page.screenshot(path=str(SHOTS / "T28B_真实401回登录.png"), full_page=True)
        # 恢复账号（隔离库种子还原），复核恢复成功
        st_reenabled = _patch_enabled(maint_id, True)
        st_after_reenable = api_get_status("/api/v1/permissions/me", tk_maint)
        record("T28B-account-reenabled", st_reenabled == 200 and st_after_reenable == 200,
               f"patch={st_reenabled} after={st_after_reenable}")"""
assert old5 in src, "T28B block4 not found"
src = src.replace(old5, new5, 1)

p.write_text(src, encoding="utf-8", newline="")
print("v2 patch2 applied")
