# -*- coding: utf-8 -*-
"""multi-verify B 模式复现 v3：explore 主链路精准取证。

E1 切「关系探索」+搜索聚焦 HIS.PAT_VISIT（1 跳邻域）
E2 depth 切 2 跳
E3 画布内双击展开 3 个节点（增量合并）
每步：截图 + 画布暗密度量化（PIL 事后统一算）+ graph API 计数。
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


def snap(page, name: str):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
    m = page.evaluate(
        """() => ({
          canvas: document.querySelectorAll('canvas').length,
          svgCircles: document.querySelectorAll('svg circle').length,
          svgTexts: document.querySelectorAll('svg text').length,
          graphApiCount: performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/v1/graph')).length,
          neighborCalls: performance.getEntriesByType('resource').filter(e=>e.name.includes('/graph/neighbors')).length,
          slowApis: performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/v1/graph')&&e.duration>1500)
            .map(e=>({api:e.name.split('/api/v1')[1].split('?')[0], ms:Math.round(e.duration)})).slice(0,5)
        })"""
    )
    EVID["steps"].append({"step": name, "measure": m, "console": [c[:200] for c in console_msgs[:5]]})
    print(f"[v3] {name}: {json.dumps(m, ensure_ascii=False)}")
    console_msgs.clear()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'verify-graph-r3',nickname:'核查',roles:['platform_admin'],permissions:['*:*:*']})); "
        "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append(f"{m.type}:{m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console_msgs.append(f"pageerror:{e}"))

    def auth(route):
        route.continue_(headers={**route.request.headers, "Authorization": f"Bearer {TOKEN}"})
    page.route("**/api/**", auth)

    page.goto(f"{FRONT}/#/asset/graph", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    # E1：切「关系探索」+ 搜索聚焦
    try:
        page.locator(".el-segmented__item", has_text="关系探索").first.click(timeout=10000)
        page.wait_for_timeout(2500)
        inp = page.locator("input[placeholder*='搜索表名']").first
        inp.fill("HIS.PAT_VISIT")
        page.get_by_role("button", name="搜索并聚焦").click()
        page.wait_for_timeout(9000)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"E1-fail:{str(exc)[:250]}")
    snap(page, "E1_explore_focus_1hop")

    # E2：depth 切 2 跳（segmented 第二项）
    try:
        segs = page.locator(".el-segmented__item")
        # depth 控件在搜索行内，选项形如 1/2/3 或 一跳/两跳——点第二个选项
        depth_labels = segs.all_inner_texts()
        console_msgs.append(f"segments={depth_labels[:8]}")
        for lbl in depth_labels:
            if lbl.strip() in ("2", "2 跳", "两跳", "2跳"):
                page.locator(".el-segmented__item", has_text=lbl.strip()).last.click()
                break
        page.wait_for_timeout(10000)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"E2-fail:{str(exc)[:250]}")
    snap(page, "E2_explore_2hop")

    # E3：画布双击展开
    try:
        cvs = page.locator("canvas").first
        box = cvs.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for dx, dy in [(0, 0), (-120, -80), (120, 80)]:
            page.mouse.dblclick(cx + dx, cy + dy)
            page.wait_for_timeout(2200)
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"E3-fail:{str(exc)[:250]}")
    snap(page, "E3_explore_dblclick_expand")

    browser.close()

(OUT / "复现v3_原始输出.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
print("[v3] saved")

# 事后像素量化
from PIL import Image  # noqa: E402

BOX = (230, 200, 1580, 980)
for name in ["E1_explore_focus_1hop", "E2_explore_2hop", "E3_explore_dblclick_expand"]:
    fp = SHOTS / f"{name}.png"
    if not fp.exists():
        continue
    im = Image.open(fp).convert("L").crop(BOX)
    px = list(im.getdata())
    dark = sum(1 for v in px if v < 120) / len(px)
    w, h = im.size
    c = Image.open(fp).convert("L").crop((230 + w // 3, 200 + h // 3, 230 + 2 * w // 3, 200 + 2 * h // 3))
    cdark = sum(1 for v in list(c.getdata()) if v < 120) / (c.size[0] * c.size[1])
    print(f"[pixel] {name}: dark={dark:.1%} center_dark={cdark:.1%}")
