# -*- coding: utf-8 -*-
# 171 T3 补充检查：③value-domains ④quality/admin 旧页 ⑤未授权 401/403 ⑥菜单可见性。
# 依赖：uvicorn(8000 隔离库)+vite dev(8848) 已起，隔离库已重灌。
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

OUT = Path(r"F:\python\数据资产\开发起步包\output_r171")
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True, parents=True)
FRONT = "http://127.0.0.1:8848"
BACK = "http://127.0.0.1:8000"
TOKEN = "verify-token-graph-r3-0001"

EVID: dict = {"steps": []}


def rec(name, data):
    data["step"] = name
    EVID["steps"].append(data)
    print(f"[t3x] {name}: {json.dumps({k: v for k, v in data.items() if k != 'shot'}, ensure_ascii=False)[:400]}")


def api(path, token=None):
    req = Request(BACK + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(req, timeout=15) as r:
            return r.status
    except Exception as exc:  # noqa: BLE001
        return getattr(exc, "code", str(exc)[:60])


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'verify-graph-r3',nickname:'数据资产平台',roles:['platform_admin'],permissions:['*:*:*']})); "
        "document.cookie='authorized-token=' + encodeURIComponent(JSON.stringify({accessToken:'" + TOKEN + "',expires:4102444800000})) + '; path=/'; "
        "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    page.route("**/api/**", lambda r: r.continue_(headers={**r.request.headers, "Authorization": f"Bearer {TOKEN}"}))

    # ⑥ 菜单可见性：platform_admin 登录态左侧菜单含「数据资产系统图」
    page.goto(f"{FRONT}/#/asset/system-map", wait_until="domcontentloaded")
    try:
        page.wait_for_selector(".re-stat-card", timeout=60000)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"no-stat-card:{str(exc)[:120]}")
    page.wait_for_timeout(2500)
    menu_txt = page.locator(".el-menu, aside, .sidebar-container").first.inner_text(timeout=10000) \
        if page.locator(".el-menu, aside, .sidebar-container").count() else ""
    has_menu = "数据资产系统图" in menu_txt
    shot6 = SHOTS / "t3_6_menu_visibility.png"
    page.screenshot(path=str(shot6), full_page=False)
    rec("t3_6_menu_visibility", {"platform_admin_sees_menu": has_menu, "shot": str(shot6)})

    # ① system-map 六步卡片点击跳转（抽 2 个代表路由实际进入）
    dom0 = page.evaluate(
        "() => ({statCards: document.querySelectorAll('.re-stat-card').length,"
        " steps: document.querySelectorAll('.step-name').length})")
    for label, route in [("图谱", "/#/asset/graph"), ("值域", "/#/value-domains")]:
        try:
            page.locator(".step", has_text=label).first.click(timeout=8000)
            page.wait_for_timeout(3500)
            cur = page.url
            rec(f"t3_1_step_jump_{label}", {"url_contains": route in cur, "url": cur[-60:]})
            page.goto(f"{FRONT}/#/asset/system-map", wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
        except Exception as exc:  # noqa: BLE001
            rec(f"t3_1_step_jump_{label}", {"error": str(exc)[:150]})
    rec("t3_1_systemmap_dom", dict(dom0))

    # ③ value-domains 列表+冲突 Tab（166 无回归）
    page.goto(f"{FRONT}/#/value-domains", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    vd = page.evaluate("() => ({rows: document.querySelectorAll('.el-table__row').length,"
                       " tabs: Array.from(document.querySelectorAll('.el-tabs__item')).map(e=>e.textContent.trim()),"
                       " errPanel: !!document.querySelector('.graph-error-panel')})")
    shot3 = SHOTS / "t3_3_value_domains.png"
    page.screenshot(path=str(shot3), full_page=False)
    try:
        page.locator(".el-tabs__item", has_text="冲突").first.click(timeout=8000)
        page.wait_for_timeout(2500)
        conflict_rows = page.evaluate("() => document.querySelectorAll('.el-table__row').length")
    except Exception as exc:  # noqa: BLE001
        conflict_rows = f"err:{str(exc)[:80]}"
    rec("t3_3_value_domains", {**vd, "conflict_tab_rows": conflict_rows, "shot": str(shot3)})

    # ④ quality / admin 旧页无回归
    for name, route in [("quality", "/#/asset/quality"), ("admin", "/#/asset/admin")]:
        page.goto(f"{FRONT}{route}", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        d = page.evaluate("() => ({errPanel: !!document.querySelector('.graph-error-panel'),"
                          " bodyLen: document.body.innerText.length})")
        shot = SHOTS / f"t3_4_{name}.png"
        page.screenshot(path=str(shot), full_page=False)
        rec(f"t3_4_{name}", {**d, "shot": str(shot)})

    browser.close()

# ⑤ 未授权冒烟（直连后端，无 token → 401；无效 token → 401/403）
code_no_token_overview = api("/api/v1/graph/overview?level=system&limit=50")
code_no_token_systemctx = api("/api/v1/ai/system-context?system_code=DATA_CENTER")
code_bad_token = api("/api/v1/graph/overview?level=system&limit=50", token="invalid-token-r171")
code_health = api("/health")
rec("t3_5_auth_smoke", {
    "graph_overview_no_token": code_no_token_overview,
    "ai_system_context_no_token": code_no_token_systemctx,
    "graph_overview_bad_token": code_bad_token,
    "health": code_health,
})

rec("page_errors", {"errors": errors[:10]})
(OUT / "t3_extra_输出.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
print("[t3x] done ->", OUT / "t3_extra_输出.json")
