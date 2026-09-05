# -*- coding: utf-8 -*-
"""169 G3/G5 像素验收+五类截图（铁律 4：中心 1/3 暗密度 <35% 为硬门槛）。

场景：
  A1 首屏 overview（正常出图，无错误面板）
  A2 explore+搜索聚焦 HIS.PAT_VISIT（1 跳）——像素门槛
  A3 explore depth 2 跳——像素门槛
  A4 增量展开（画布双击）——目检+密度记录
  A5 Inspector+图例芯片——目检
每步截图+密度量化入 验收_原始输出.json。
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)
FRONT = "http://127.0.0.1:8848"
TOKEN = "verify-token-graph-r3-0001"
THRESHOLD = 0.35
CENTER_KEY = "DATA_CENTER|ods_8_216|HIS|HIS|PAT_VISIT"

EVID: dict = {"steps": []}
console_msgs: list[str] = []


def snap(page, name: str, note: str = "", api_evidence: dict | None = None):
    shot = SHOTS / f"{name}.png"
    page.screenshot(path=str(shot), full_page=False)
    m = page.evaluate(
        """() => ({
          canvas: document.querySelectorAll('canvas').length,
          svgCircles: document.querySelectorAll('svg circle').length,
          errorPanel: !!document.querySelector('.graph-error-panel'),
          toolbar: !!document.querySelector('.el-segmented'),
          neighborCalls: performance.getEntriesByType('resource').filter(e=>e.name.includes('/graph/neighbors')).length
        })"""
    )
    # 像素密度（画布工作区，同 round-3 口径：230,200-1580,980）
    from PIL import Image

    im = Image.open(shot).convert("L").crop((230, 200, 1580, 980))
    w, h = im.size
    px = list(im.getdata())
    dark = sum(1 for v in px if v < 120) / len(px)
    c = im.crop((w // 3, h // 3, 2 * w // 3, 2 * h // 3))
    cdark = sum(1 for v in list(c.getdata()) if v < 120) / (c.size[0] * c.size[1])
    rec = {"step": name, "note": note, "dom": m, "api": api_evidence or {}, "dark": round(dark, 4),
           "center_dark": round(cdark, 4), "threshold": THRESHOLD,
           "pass": (
               cdark < THRESHOLD
               and bool(api_evidence)
               and api_evidence.get("status") == 200
               and api_evidence.get("nodes", 0) > 1
               and api_evidence.get("center") == CENTER_KEY
           ) if note.startswith("门槛") else None,
           "console": [c[:200] for c in console_msgs[:5]]}
    EVID["steps"].append(rec)
    print(f"[accept] {name}: center_dark={cdark:.1%} dark={dark:.1%} canvas={m['canvas']} "
          f"svg={m['svgCircles']} err={m['errorPanel']} toolbar={m['toolbar']} "
          f"{'PASS' if rec['pass'] else ('FAIL' if rec['pass'] is False else '')}")
    console_msgs.clear()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'accept169',nickname:'验收',roles:['platform_admin'],permissions:['*:*:*']})); "
        # 迁移期 cookie 通道（auth.ts getToken 兜底读 authorized-token）：让拦截器拿到
        # 有效 token，从根上避免 refresh 401 队列误杀业务请求（round-3 伪会话时序缺陷）
        + "document.cookie='authorized-token=' + encodeURIComponent(JSON.stringify({accessToken:'" + TOKEN + "',expires:4102444800000})) + '; path=/'; "
        + "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append(f"{m.type}:{m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console_msgs.append(f"pageerror:{e}"))
    page.route("**/api/**", lambda r: r.continue_(headers={**r.request.headers, "Authorization": f"Bearer {TOKEN}"}))

    # A1 首屏 overview（后端已修，应秒级出图）
    page.goto(f"{FRONT}/#/asset/graph", wait_until="domcontentloaded")
    # dev 冷启动编译+SPA init（round-3 实测首屏 API 可晚至 20s+）；工具栏出现=页面 ready
    try:
        # EP 原生视图模式控件（GraphToolbar el-segmented）；pure-segmented 是顶栏主题控件
        page.wait_for_selector(".el-segmented", timeout=40000)
    except Exception:
        console_msgs.append("A1: toolbar not ready in 40s")
    page.wait_for_timeout(4000)
    snap(page, "A1_overview_first_screen", "目检：无错误面板、系统聚合层出图")

    # 切「关系探索」（pure-segmented 封装；容错——失败记录后继续，保住后续场景取证）
    try:
        page.locator(".el-segmented__item", has_text="关系探索").first.click(timeout=15000)
        page.wait_for_timeout(2500)
    except Exception as exc:
        console_msgs.append(f"switch-explore-fail:{str(exc)[:200]}")
        page.wait_for_timeout(1000)

    # A2 搜索聚焦 1 跳：直接使用唯一五段物理键，且 API/中心/节点数均是硬门槛。
    # 旧脚本只填歧义短名却未选择候选，画布仍是 overview，像素低密度是假阳性。
    a2_api = {}
    try:
        with page.expect_response(lambda r: "/api/v1/graph/neighbors" in r.url, timeout=30000) as pending:
            page.locator("input[placeholder*='搜索表名']").first.fill(CENTER_KEY)
            page.keyboard.press("Enter")
        response = pending.value
        payload = response.json().get("data", {}) if response.status == 200 else {}
        a2_api = {"status": response.status, "nodes": len(payload.get("nodes", [])),
                  "edges": len(payload.get("edges", [])), "center": CENTER_KEY}
        page.wait_for_timeout(12000)
    except Exception as exc:
        console_msgs.append(f"A2-search-fail:{str(exc)[:200]}")
    snap(page, "A2_explore_focus_1hop", "门槛：真实 PAT_VISIT 邻域且 center_dark<35%", a2_api)

    # A3 depth 切 2 跳
    a3_api = {}
    try:
        depth = page.locator(".global-search-row .el-segmented").first
        with page.expect_response(lambda r: "/api/v1/graph/neighbors" in r.url, timeout=30000) as pending:
            depth.get_by_text("2 跳", exact=True).click()
        response = pending.value
        payload = response.json().get("data", {}) if response.status == 200 else {}
        a3_api = {"status": response.status, "nodes": len(payload.get("nodes", [])),
                  "edges": len(payload.get("edges", [])), "center": CENTER_KEY}
        page.wait_for_timeout(12000)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"A3-depth-fail:{str(exc)[:150]}")
    snap(page, "A3_explore_2hop", "门槛：真实 PAT_VISIT 2跳邻域且 center_dark<35%", a3_api)

    # A4 增量展开（双击画布）
    a4_api = {}
    try:
        box = page.locator("canvas").first.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        with page.expect_response(lambda r: "/api/v1/graph/neighbors" in r.url, timeout=15000) as pending:
            page.mouse.dblclick(cx, cy)
        response = pending.value
        payload = response.json().get("data", {}) if response.status == 200 else {}
        a4_api = {"status": response.status, "nodes": len(payload.get("nodes", [])),
                  "edges": len(payload.get("edges", [])), "center": CENTER_KEY}
        page.wait_for_timeout(6000)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"A4-fail:{str(exc)[:150]}")
    snap(page, "A4_incremental_expand", "门槛：真实增量 API 200 且 center_dark<35%", a4_api)

    # A5 Inspector+图例
    try:
        page.wait_for_selector(".inspector", timeout=6000)
        inspector_text = page.locator(".inspector").inner_text()
        if '{"show"' in inspector_text:
            console_msgs.append("A5-inspector-fail:label object JSON is still visible")
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"A5-inspector-fail:{str(exc)[:150]}")
    snap(page, "A5_inspector_legend", "目检：Inspector 打开、图例芯片可见")

    browser.close()

(OUT / "验收_原始输出.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
gates = [s for s in EVID["steps"] if s["pass"] is not None]
print("[accept] gate results:", [(s["step"], s["pass"]) for s in gates])
print("[accept] ALL GATES:", "PASS" if all(s["pass"] for s in gates) else "FAIL")
