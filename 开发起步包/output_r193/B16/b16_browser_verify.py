# -*- coding: utf-8 -*-
"""193 B16：数据集目录页浏览器验收（真实隔离 API，无 mock）。

断言：页面渲染数据集行（DS_B16 published/已授权）、批次检查点查询真实返回、
console 零错误；顺带回归 /#/asset/tables 路由未受新路由影响。
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots"
SHOTS.mkdir(exist_ok=True)
FRONT = "http://127.0.0.1:8848"

results = []


def record(case, ok, detail):
    results.append({"case": case, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {case}: {detail}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{FRONT}/#/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-card", timeout=20000)
        page.locator(".login-form input").nth(0).fill("r194_admin")
        page.locator(".login-form input").nth(1).fill("R194Seed#A1N9x")
        page.locator(".login-button").first.click()
        page.wait_for_timeout(4500)
        record("login", "#/workbench" in page.url, page.url)

        # 数据集目录页
        page.goto(f"{FRONT}/#/datasets", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        body = page.locator("body").inner_text()
        is_404 = "404" in body[:120] or "页面不存在" in body[:120]
        record("B16-page-renders", not is_404 and "数据集目录" in body,
               f"404={is_404}; 含标题={'数据集目录' in body}")
        has_row = "DS_B16" in body
        record("B16-dataset-row", has_row, f"DS_B16 行可见={has_row}")
        has_pub = "published" in body
        record("B16-status-published", has_pub, f"published 状态可见={has_pub}")
        # readable 列（已授权 tag）
        has_granted = "已授权" in body
        record("B16-readable-tag", has_granted, f"已授权标签={has_granted}")
        page.screenshot(path=str(SHOTS / "B16_数据集目录.png"))

        # 批次查询面板（真实 API）
        page.locator(".batch-bar input").first.fill("RUN-B16")
        page.get_by_role("button", name="查询批次").click()
        page.wait_for_timeout(2000)
        batch_json = page.locator(".batch-json").inner_text() if page.locator(".batch-json").count() else ""
        record("B16-batch-query", '"written": 3' in batch_json.replace(" ", " ") or "written" in batch_json,
               f"批次 JSON 含计数={'written' in batch_json}; 片段={batch_json[:90]!r}")
        page.screenshot(path=str(SHOTS / "B16_批次查询.png"))

        # 回归：表目录路由未受影响
        page.goto(f"{FRONT}/#/asset/tables", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        body2 = page.locator("body").inner_text()
        record("regression-tables-route", "资产表目录" in body2, "表目录页可达")

        hard = [e for e in errors if "favicon" not in e.lower()][:6]
        record("console-errors", len(hard) == 0, f"错误数={len(hard)} 样例={hard[:2]}")
        browser.close()

    passed = sum(1 for r in results if r["ok"])
    summary = {"passed": passed, "failed": len(results) - passed, "results": results,
               "mode": "real-api"}
    (OUT / "b16_evidence.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(f"=== {passed}/{len(results)} PASS ===")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
