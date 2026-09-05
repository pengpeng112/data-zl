# -*- coding: utf-8 -*-
"""170：数据资产系统图页面截图（1920x1080，登录态直达）。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"F:\python\数据资产\开发起步包\output_r170")
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)
TOKEN = "verify-token-graph-r3-0001"

result = {"steps": []}

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,"
        "refreshToken:'',username:'verify-graph-r3',nickname:'数据资产平台',roles:['platform_admin'],"
        "permissions:['*:*:*']})); "
        "document.cookie='authorized-token=' + encodeURIComponent(JSON.stringify({accessToken:'" + TOKEN + "',expires:4102444800000})) + '; path=/'; "
        "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:300]))
    page.route("**/api/**", lambda r: r.continue_(
        headers={**r.request.headers, "Authorization": f"Bearer {TOKEN}"}))

    page.goto("http://127.0.0.1:8848/#/asset/system-map", wait_until="domcontentloaded")
    # 等页面骨架 + 真实数字渲染（dev 冷启动 + SPA init）
    try:
        page.wait_for_selector(".re-stat-card", timeout=60000)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"no-stat-card:{exc}")
    try:
        page.wait_for_function("() => document.body.textContent.includes('12,702')", timeout=30000)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"no-kpi-text:{exc}")
    page.wait_for_timeout(2500)
    shot = SHOTS / "system-map.png"
    page.screenshot(path=str(shot), full_page=False)

    dom = page.evaluate(
        """() => ({
          statCards: document.querySelectorAll('.re-stat-card').length,
          steps: Array.from(document.querySelectorAll('.step-name')).map(e=>e.textContent.trim()),
          errPanel: !!document.querySelector('.graph-error-panel'),
          alert: (document.querySelector('.el-alert__title')||{}).textContent || '',
          has12702: document.body.textContent.includes('12,702'),
          has1329: document.body.textContent.includes('1,329'),
        })"""
    )
    result["system_map"] = {"dom": dom, "errors": errors[:8], "shot": str(shot)}
    print("[170] system-map:", json.dumps(dom, ensure_ascii=False), "errors:", errors[:3])

    # 附带：关系图谱页（force 修复后）同框对比截图
    page.goto("http://127.0.0.1:8848/#/asset/graph", wait_until="domcontentloaded")
    try:
        page.wait_for_selector(".el-segmented", timeout=60000)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"no-toolbar:{exc}")
    page.wait_for_timeout(6000)
    page.screenshot(path=str(SHOTS / "graph_overview.png"), full_page=False)
    result["graph_overview"] = {"errors": errors[-3:]}

    browser.close()

(OUT / "screenshot170_输出.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("[170] done ->", SHOTS / "system-map.png")
