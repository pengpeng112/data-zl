# -*- coding: utf-8 -*-
"""171 T5：生产实拍（经 SSH 隧道 127.0.0.1:18432 → 生产 nginx）。
graph 首屏 + system-map 两页，1920x1080；throwaway token 用后由外部删除。
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"F:\python\数据资产\开发起步包\output_r171")
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)
BASE = "http://127.0.0.1:18432"
TOKEN = "verify-t5-r171-prod"
EVID: dict = {}

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

    def snap(url_hash: str, name: str, wait_sel: str, settle: int):
        page.goto(f"{BASE}/#{url_hash}", wait_until="domcontentloaded")
        try:
            page.wait_for_selector(wait_sel, timeout=45000)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"{name}:no-selector({wait_sel}):{str(exc)[:120]}")
        page.wait_for_timeout(settle)
        page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
        m = page.evaluate(
            """() => ({
              statCards: document.querySelectorAll('.re-stat-card').length,
              errPanel: !!document.querySelector('.graph-error-panel'),
              canvas: document.querySelectorAll('canvas').length,
              hasMenu: document.body.textContent.includes('数据资产系统图'),
              sample: (document.body.textContent.match(/12,?702/)||[''])[0]
            })"""
        )
        EVID[name] = {"dom": m, "errors": errs[-3:]}
        print(f"[t5] {name}: {json.dumps(m, ensure_ascii=False)}")

    # ① 生产 system-map（r171 前端新页面）
    snap("asset/system-map", "T5_prod_system-map", ".re-stat-card", 2500)
    # ② 生产图谱首屏（169 修复在产）
    snap("asset/graph", "T5_prod_graph_first_screen", ".el-segmented", 9000)

    browser.close()

(OUT / "t5_prod_实拍.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
print("[t5] saved ->", SHOTS)
