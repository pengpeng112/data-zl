# -*- coding: utf-8 -*-
"""171 X2：生产探查发现页实拍（隧道 127.0.0.1:18432 → 生产 nginx，throwaway token）。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"F:\python\数据资产\开发起步包\output_r171")
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)
BASE = "http://127.0.0.1:18432"
TOKEN = "verify-t5-r171-prod"

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,"
        "refreshToken:'',username:'verify-t5-r171',nickname:'生产验收',roles:['platform_admin'],"
        "permissions:['*:*:*']})); "
        "document.cookie='authorized-token=' + encodeURIComponent(JSON.stringify({accessToken:'" + TOKEN + "',expires:4102444800000})) + '; path=/'; "
        "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    errs: list[str] = []
    page.on("pageerror", lambda e: errs.append(str(e)[:200]))
    page.goto(f"{BASE}/#/probe-findings", wait_until="domcontentloaded")
    try:
        page.wait_for_selector(".el-table__row", timeout=45000)
    except Exception as exc:  # noqa: BLE001
        errs.append(f"no-table-row:{str(exc)[:120]}")
    page.wait_for_timeout(2500)
    page.screenshot(path=str(SHOTS / "X2_prod_probe-findings.png"), full_page=False)
    m = page.evaluate(
        """() => ({
          rows: document.querySelectorAll('.el-table__row').length,
          hasRunId: !!document.body.textContent.includes('probe-20260901-191051'),
          hasOpen: !!document.body.textContent.includes('待处理') || !!document.body.textContent.includes('open'),
          hasMenu: !!document.body.textContent.includes('探查') || !!document.body.textContent.includes('数据问题'),
          errPanel: !!document.querySelector('.graph-error-panel')
        })"""
    )
    print("[x2]", json.dumps(m, ensure_ascii=False), "errors:", errs[-3:])
    browser.close()
    (OUT / "x2_prod" / "x2_findings_实拍.json").write_text(
        json.dumps({"dom": m, "errors": errs[-3:]}, ensure_ascii=False, indent=2), encoding="utf-8")
