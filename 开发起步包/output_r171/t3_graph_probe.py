# -*- coding: utf-8 -*-
# 171 T3② 聚焦复验：错误面板可见性 / 搜索聚焦 1 跳 / depth 1→2 切换真实请求 / 画布中心双击增量 / Inspector。
# 背景：169 工装复跑 A3 超时（点按已选中的 2 跳不触发 change）、A4 双击返回 nodes=1；本探针逐项隔离复验。
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"F:\python\数据资产\开发起步包\output_r171")
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True, parents=True)
FRONT = "http://127.0.0.1:8848"
TOKEN = "verify-token-graph-r3-0001"
CENTER_KEY = "DATA_CENTER|ods_8_216|HIS|HIS|PAT_VISIT"

EVID: dict = {"steps": []}
console_errors: list[str] = []


def density(shot: Path, x0=230, y0=200, x1=1580, y1=980) -> tuple[float, float]:
    from PIL import Image

    im = Image.open(shot).convert("L").crop((x0, y0, x1, y1))
    w, h = im.size
    px = list(im.getdata())
    dark = sum(1 for v in px if v < 120) / len(px)
    c = im.crop((w // 3, h // 3, 2 * w // 3, 2 * h // 3))
    cdark = sum(1 for v in list(c.getdata()) if v < 120) / (c.size[0] * c.size[1])
    return dark, cdark


def snap(page, name, note, api=None):
    shot = SHOTS / f"{name}.png"
    page.screenshot(path=str(shot), full_page=False)
    dark, cdark = density(shot)
    m = page.evaluate(
        "() => { const ep = document.querySelector('.graph-error-panel');"
        " return {panel_exists: !!ep, panel_visible: !!ep && !!(ep.offsetParent||ep.getClientRects().length),"
        " panel_text: ep ? ep.innerText.slice(0,120) : '', canvas: document.querySelectorAll('canvas').length} }")
    rec = {"step": name, "note": note, "api": api or {}, "dark": round(dark, 4),
           "center_dark": round(cdark, 4), **m, "console": console_errors[:5]}
    EVID["steps"].append(rec)
    print(f"[probe] {name}: cdark={cdark:.1%} panel={m['panel_exists']}/{m['panel_visible']} "
          f"api={api} console={console_errors[:2]}")
    console_errors.clear()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'probe171',nickname:'验收',roles:['platform_admin'],permissions:['*:*:*']})); "
        "document.cookie='authorized-token=' + encodeURIComponent(JSON.stringify({accessToken:'" + TOKEN + "',expires:4102444800000})) + '; path=/'; "
        + "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    page.on("console", lambda m: console_errors.append(f"{m.type}:{m.text[:150]}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(f"pageerror:{str(e)[:150]}"))
    page.route("**/api/**", lambda r: r.continue_(headers={**r.request.headers, "Authorization": f"Bearer {TOKEN}"}))

    page.goto(f"{FRONT}/#/asset/graph", wait_until="domcontentloaded")
    page.wait_for_selector(".el-segmented", timeout=40000)
    page.wait_for_timeout(4000)
    snap(page, "B0_overview", "首屏 overview（复验 T3② 出图+面板）")

    # 切关系探索
    page.locator(".el-segmented__item", has_text="关系探索").first.click(timeout=15000)
    page.wait_for_timeout(2500)

    def neighbors_capture(action, timeout=30000):
        try:
            with page.expect_response(lambda r: "/api/v1/graph/neighbors" in r.url, timeout=timeout) as pending:
                action()
            resp = pending.value
            payload = resp.json().get("data", {}) if resp.status == 200 else {}
            return {"status": resp.status, "nodes": len(payload.get("nodes", [])),
                    "edges": len(payload.get("edges", []))}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)[:120]}

    # B1 搜索聚焦（当前默认档位）
    api1 = neighbors_capture(lambda: (page.locator("input[placeholder*='搜索表名']").first.fill(CENTER_KEY),
                                      page.keyboard.press("Enter")))
    page.wait_for_timeout(10000)
    snap(page, "B1_search_focus", "搜索聚焦 HIS.PAT_VISIT（默认档）", api1)

    # B2 depth 切到 1 跳（从默认档先降档，保证后续 1→2 有真实 change）
    seg = page.locator(".global-search-row .el-segmented").first
    api2 = neighbors_capture(lambda: seg.get_by_text("1 跳", exact=True).click(), timeout=20000)
    page.wait_for_timeout(8000)
    snap(page, "B2_depth_1hop", "depth 切 1 跳（真实 change 请求）", api2)

    # B3 depth 1→2（关键：真实切换并出图）
    api3 = neighbors_capture(lambda: seg.get_by_text("2 跳", exact=True).click(), timeout=30000)
    page.wait_for_timeout(12000)
    snap(page, "B3_depth_2hop", "depth 1→2 跳（A3 复验）", api3)

    # B4 增量展开：双击画布几何中心（A4 复验；同时记录返回）
    box = page.locator("canvas").first.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    api4 = neighbors_capture(lambda: page.mouse.dblclick(cx, cy), timeout=20000)
    page.wait_for_timeout(8000)
    snap(page, "B4_incremental", "画布中心双击增量展开（A4 复验）", api4)

    # B5 Inspector 中文名（displayName 链路活体验证）
    insp = {}
    try:
        page.wait_for_selector(".inspector", timeout=6000)
        # 双击中心已聚焦节点；Inspector 应已开
        txt = page.locator(".inspector").inner_text(timeout=5000)
        insp = {"has_json_dump": '{"show"' in txt or '"formatter"' in txt,
                "snippet": txt[:160].replace("\n", " | ")}
    except Exception as exc:  # noqa: BLE001
        insp = {"error": str(exc)[:120]}
    snap(page, "B5_inspector", "Inspector 中文名兜底链（活体）", insp)

    browser.close()

(OUT / "t3_probe_输出.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
gates = [s for s in EVID["steps"] if s["step"].startswith(("B1", "B3", "B4"))]
print("[probe] summary:", [(s["step"], s["center_dark"], s["api"]) for s in EVID["steps"]])
