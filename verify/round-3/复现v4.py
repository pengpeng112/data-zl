# -*- coding: utf-8 -*-
"""multi-verify v4 诊断+取证：不再猜选择器，先 dump DOM 再交互。"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "复现截图"
FRONT = "http://127.0.0.1:8848"
TOKEN = "verify-token-graph-r3-0001"
EVID: dict = {"steps": []}
console_msgs: list[str] = []


def snap(page, name: str):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
    m = page.evaluate(
        """() => ({
          canvas: document.querySelectorAll('canvas').length,
          svg: document.querySelectorAll('svg').length,
          svgCircles: document.querySelectorAll('svg circle').length,
          graphWrapExists: !!document.querySelector('.graph-wrap'),
          g6Containers: Array.from(document.querySelectorAll('[class*=graph]')).slice(0,6).map(e=>e.className.toString().slice(0,60)),
          neighborCalls: performance.getEntriesByType('resource').filter(e=>e.name.includes('/graph/neighbors')).length,
          graphCalls: performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/v1/graph')).length
        })"""
    )
    EVID["steps"].append({"step": name, "measure": m, "console": [c[:180] for c in console_msgs[:4]]})
    print(f"[v4] {name}: {json.dumps(m, ensure_ascii=False)}")
    console_msgs.clear()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    ctx.add_init_script(
        "localStorage.setItem('user-info', JSON.stringify({accessToken:'',expires:4102444800000,refreshToken:'',"
        "username:'v4',nickname:'v4',roles:['platform_admin'],permissions:['*:*:*']})); "
        "document.cookie='multiple-tabs=true; path=/';")
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append(f"{m.type}:{m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console_msgs.append(f"pageerror:{e}"))
    page.route("**/api/**", lambda r: r.continue_(headers={**r.request.headers, "Authorization": f"Bearer {TOKEN}"}))

    page.goto(f"{FRONT}/#/asset/graph", wait_until="domcontentloaded")
    page.wait_for_timeout(45000)  # overview ~24s + 渲染余量
    snap(page, "V4_D0_overview_settled")

    # dump 工具栏真实结构（找模式切换控件）
    struct = page.evaluate(
        """() => {
          const seg = document.querySelector('.el-segmented');
          const segItems = Array.from(document.querySelectorAll('.el-segmented__item, .el-segmented .el-segmented__item')).map(e=>e.textContent.trim());
          const radios = Array.from(document.querySelectorAll('.el-radio-button__inner, [role=radio], .el-tabs__item')).map(e=>e.textContent.trim()).slice(0,12);
          const toolbarText = (document.querySelector('.graph-toolbar, form, .toolbar')?.textContent || '').slice(0, 200);
          return {hasSegmented: !!seg, segItems, radios, toolbarText};
        }"""
    )
    print("[v4] toolbar struct:", json.dumps(struct, ensure_ascii=False))
    EVID["steps"].append({"step": "toolbar_struct", "struct": struct})

    # 用 label 文本点击模式项（segmented 项内是 label 文本）
    try:
        clicked = False
        for sel in ['.el-segmented__item', '.el-segmented-item', 'label.el-segmented__item']:
            items = page.locator(sel)
            if items.count() > 0:
                for i in range(items.count()):
                    t = (items.nth(i).inner_text() or "").strip()
                    if "关系探索" in t or "探索" in t:
                        items.nth(i).click()
                        clicked = True
                        break
            if clicked:
                break
        if not clicked:
            # 兜底：直接点包含文字的任意元素
            page.get_by_text("关系探索", exact=True).first.click(timeout=8000)
            clicked = True
        page.wait_for_timeout(3000)
        # 全局搜索聚焦
        inp = page.locator("input[placeholder*='搜索表名']").first
        inp.fill("HIS.PAT_VISIT")
        page.keyboard.press("Enter")
        page.wait_for_timeout(10000)
        snap(page, "V4_E1_explore_focus")
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"V4E1-fail:{str(exc)[:250]}")
        snap(page, "V4_E1_fail")

    # E2 双击画布展开
    try:
        cvs = page.locator("canvas").first
        if cvs.count() > 0:
            box = cvs.bounding_box()
            cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            for dx, dy in [(0, 0), (-120, -80), (120, 80)]:
                page.mouse.dblclick(cx + dx, cy + dy)
                page.wait_for_timeout(2200)
        else:
            console_msgs.append("no-canvas-for-E2")
    except Exception as exc:  # noqa: BLE001
        console_msgs.append(f"V4E2-fail:{str(exc)[:250]}")
    snap(page, "V4_E2_dblclick_expand")

    browser.close()

(OUT / "复现v4_原始输出.json").write_text(json.dumps(EVID, ensure_ascii=False, indent=2), encoding="utf-8")
print("[v4] saved")

from PIL import Image  # noqa: E402

BOX = (230, 200, 1580, 980)
for name in ["V4_D0_overview_settled", "V4_E1_explore_focus", "V4_E2_dblclick_expand"]:
    fp = SHOTS / f"{name}.png"
    if not fp.exists():
        continue
    im = Image.open(fp).convert("L").crop(BOX)
    px = list(im.getdata())
    dark = sum(1 for v in px if v < 120) / len(px)
    w, h = im.size
    c = im.crop((w // 3, h // 3, 2 * w // 3, 2 * h // 3))
    cdark = sum(1 for v in list(c.getdata()) if v < 120) / (c.size[0] * c.size[1])
    print(f"[pixel] {name}: dark={dark:.1%} center_dark={cdark:.1%}")
