# -*- coding: utf-8 -*-
# 171 T3② 根因探针：捕获 requestfailed/非200/console，定位 explore 模式错误面板来源。
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"F:\python\数据资产\开发起步包\output_r171")
FRONT = "http://127.0.0.1:8848"
TOKEN = "verify-token-graph-r3-0001"
CENTER_KEY = "DATA_CENTER|ods_8_216|HIS|HIS|PAT_VISIT"

log: dict = {"failed": [], "non200": [], "console": [], "panel": []}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'probe171f',nickname:'验收',roles:['platform_admin'],permissions:['*:*:*']})); "
        "document.cookie='authorized-token=' + encodeURIComponent(JSON.stringify({accessToken:'" + TOKEN + "',expires:4102444800000})) + '; path=/'; "
        + "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    page.on("requestfailed", lambda r: log["failed"].append({"url": r.url[-90:], "method": r.method, "failure": r.failure}))
    page.on("response", lambda r: log["non200"].append({"url": r.url[-90:], "status": r.status}) if r.status >= 300 else None)
    page.on("console", lambda m: log["console"].append(f"{m.type}:{m.text[:180]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: log["console"].append(f"pageerror:{str(e)[:180]}"))
    page.route("**/api/**", lambda r: r.continue_(headers={**r.request.headers, "Authorization": f"Bearer {TOKEN}"}))

    def panel_state(tag):
        info = page.evaluate(
            "() => { const ep = document.querySelector('.graph-error-panel');"
            " return {exists: !!ep, visible: !!ep && !!(ep.offsetParent||ep.getClientRects().length),"
            " text: ep ? ep.innerText.slice(0,60) : ''}; }")
        log["panel"].append({"tag": tag, **info})
        print("[repro]", tag, info)

    page.goto(f"{FRONT}/#/asset/graph", wait_until="domcontentloaded")
    page.wait_for_selector(".el-segmented", timeout=40000)
    page.wait_for_timeout(4000)
    panel_state("after_overview_load")

    page.locator(".el-segmented__item", has_text="关系探索").first.click(timeout=15000)
    page.wait_for_timeout(3000)
    panel_state("after_mode_switch")

    page.locator("input[placeholder*='搜索表名']").first.fill(CENTER_KEY)
    page.keyboard.press("Enter")
    page.wait_for_timeout(8000)
    panel_state("after_search_focus")

    browser.close()

(OUT / "t3_repro_panel.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
print("failed:", json.dumps(log["failed"], ensure_ascii=False)[:600])
print("non200:", json.dumps(log["non200"], ensure_ascii=False)[:400])
print("console:", json.dumps(log["console"][:6], ensure_ascii=False)[:500])
