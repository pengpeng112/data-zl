# -*- coding: utf-8 -*-
"""multi-verify B 模式复现脚本 v2：单页会话（避免二次 goto 触发 refresh 登出）。

步骤（同一 page 内）：
  S1 overview 默认页（等 overview API 完成，实测 ~24s）
  S2 工具栏切「关系探索」explore，选中心 HIS.PAT_VISIT，2 跳展开
  S3 画布内连续双击展开节点（用户主诉"进去后内容叠加"）
  S4 全局搜索聚焦 LAB_RESULT
每步：截图 + 节点/标签重叠度量 + console 错误 + API 耗时（performance 条目）。
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "复现截图"
SHOTS.mkdir(exist_ok=True)
FRONT = "http://127.0.0.1:8848"
TOKEN = "verify-token-graph-r3-0001"

EVID: dict = {"steps": []}
console_msgs: list[str] = []


def measure(page) -> dict:
    return page.evaluate(
        """() => {
          const circles = Array.from(document.querySelectorAll('svg circle'));
          const labels = Array.from(document.querySelectorAll('svg text'));
          let nodeOverlap = 0, pairs = [];
          const cinfo = circles.map(c => { const b = c.getBBox(); return {x: b.x+b.width/2, y: b.y+b.height/2, r: Math.max(b.width,b.height)/2}; });
          for (let i=0;i<cinfo.length;i++) for (let j=i+1;j<cinfo.length;j++) {
            const a=cinfo[i], b=cinfo[j]; const d=Math.hypot(a.x-b.x,a.y-b.y);
            if (d < (a.r+b.r)*0.8) { nodeOverlap++; if(pairs.length<8) pairs.push([Math.round(a.x),Math.round(a.y),Math.round(b.x),Math.round(b.y),Math.round(d)]); }
          }
          let labelOverlap = 0;
          const linfo = labels.map(t=>{const b=t.getBBox();return {x:b.x,y:b.y,w:b.width,h:b.height};});
          for (let i=0;i<linfo.length;i++) for (let j=i+1;j<linfo.length;j++) {
            const a=linfo[i],b=linfo[j];
            if (a.x<b.x+b.w && b.x<a.x+a.w && a.y<b.y+b.h && b.y<a.y+a.h) labelOverlap++;
          }
          return {svgCircles: circles.length, nodeOverlap, labelTotal: labels.length, labelOverlap,
                  samplePairs: pairs, hasCanvas: document.querySelectorAll('canvas').length,
                  engineText: (Array.from(document.querySelectorAll('.el-tag,.engine-reason')).map(e=>e.textContent.trim())
                    .filter(t=>t&&(t.includes('引擎')||t.includes('降级')||t.includes('SVG')||t.includes('G6'))).join(' | ') || '')};
        }"""
    )


def api_times(page) -> list:
    return page.evaluate(
        """() => performance.getEntriesByType('resource')
             .filter(e => e.name.includes('/api/v1/graph'))
             .map(e => ({api: e.name.split('/api/v1')[1].split('?')[0], ms: Math.round(e.duration)}))
             .filter(e => e.ms > 800).sort((a,b)=>b.ms-a.ms).slice(0,6)"""
    )


def snap(page, name: str):
    shot = SHOTS / f"{name}.png"
    page.screenshot(path=str(shot), full_page=False)
    m = measure(page)
    rec = {"step": name, "measure": m, "slow_graph_apis": api_times(page),
           "console_errors": [c[:300] for c in console_msgs if "Failed to resolve component" not in c][:8]}
    EVID["steps"].append(rec)
    print(f"[repro] {name}: svgCircles={m['svgCircles']} nodeOverlap={m['nodeOverlap']} "
          f"labels={m['labelTotal']} labelOverlap={m['labelOverlap']} canvas={m['hasCanvas']} "
          f"engine='{m['engineText']}' slowAPIs={rec['slow_graph_apis'][:3]}")
    console_msgs.clear()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'verify-graph-r3',nickname:'核查(隔离库)',roles:['platform_admin'],permissions:['*:*:*']})); "
        "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    page.on("console", lambda msg: console_msgs.append(f"{msg.type}:{msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda err: console_msgs.append(f"pageerror:{err}"))

    def auth(route):
        headers = {**route.request.headers, "Authorization": f"Bearer {TOKEN}"}
        route.continue_(headers=headers)
    page.route("**/api/**", auth)

    # S1：默认 overview（overview API 实测 ~24s，总等 40s）
    page.goto(f"{FRONT}/#/asset/graph", wait_until="domcontentloaded")
    page.wait_for_timeout(40000)
    snap(page, "S1_overview_default")

    # S2：切「关系探索」
    try:
        page.get_by_text("关系探索", exact=False).first.click(timeout=8000)
        page.wait_for_timeout(3000)
        sel = page.locator("input[placeholder*='中心'], input[placeholder*='表']").first
        sel.click(timeout=8000)
        page.keyboard.type("HIS.PAT_VISIT", delay=40)
        page.wait_for_timeout(1500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(8000)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"S2-interact-fail:{str(exc)[:200]}")
    snap(page, "S2_explore_center")

    # S3：画布内连点双击展开
    def expand_clicks(p_):
        target = p_.locator("canvas").first
        if target.count() == 0:
            target = p_.locator("svg").first
        box = target.bounding_box()
        if not box:
            return
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for dx, dy in [(0, 0), (-150, -70), (150, 70), (-70, 140), (70, -140), (0, 0), (-220, 0), (220, 0), (0, 90)]:
            p_.mouse.dblclick(cx + dx, cy + dy)
            p_.wait_for_timeout(1600)
    try:
        expand_clicks(page)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"S3-fail:{str(exc)[:200]}")
    snap(page, "S3_explore_expand_multi")

    # S4：全局搜索
    try:
        inp = page.locator("input[placeholder*='搜索']").first
        inp.fill("LAB_RESULT")
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"S4-fail:{str(exc)[:200]}")
    snap(page, "S4_search_focus")

    browser.close()

(OUT / "复现_原始输出.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
print("[repro] evidence saved")
