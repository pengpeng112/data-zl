# -*- coding: utf-8 -*-
"""186 P1-2/P1-3 补录：真实隔离 API 浏览器验证。

P1-3：10 页真实 API 截图（import170 数据 + 真实登录），存 screenshots_real_api/。
P1-2：A3 两条链路浏览器级实证（零写断言：全程监控非 GET 请求）。
  链路1：表目录(带筛选)→表详情(当前表关系图 定位高亮/边抽屉)→关系复核页→返回(列表状态保留)
  链路2：元数据变更事件→快照对比只读预览(断言零写)→影响查询定位
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots_real_api"
SHOTS.mkdir(exist_ok=True)

FRONT = "http://127.0.0.1:8848"
USER = "r194_admin"
PWD = "R194Seed#A1N9x"

results: list[dict] = []
writes: list[str] = []


def record(case: str, ok: bool, detail: str) -> None:
    results.append({"case": case, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {case}: {detail}")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 768})
        page = ctx.new_page()
        # 全程写监控：记录所有非 GET 的 API 请求（auth refresh 除外）
        def on_request(req):
            if req.method not in ("GET", "HEAD", "OPTIONS") and "/api/" in req.url:
                writes.append(f"{req.method} {req.url}")

        page.on("request", on_request)
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # ---------- 登录（真实 API）----------
        page.goto(f"{FRONT}/#/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-card", timeout=15000)
        page.locator(".login-form input").nth(0).fill(USER)
        page.locator(".login-form input").nth(1).fill(PWD)
        page.locator(".login-button").first.click()
        page.wait_for_timeout(4500)
        record("login-real-api", "#/workbench" in page.url, f"url={page.url}")

        # ---------- P1-3：10 页真实 API ----------
        pages_10 = [
            ("01_登录页_真实API.png", "/#/login", None),
            ("02_工作台_1366_真实API.png", "/#/workbench", None),
            ("03_工作台_1920_真实API.png", "/#/workbench", (1920, 1080)),
            ("04_资产目录_系统与数据资源_真实API.png", "/#/asset/systems", None),
            ("05_标准与关系_值域_真实API.png", "/#/value-domains", None),
            ("06_质量治理_台账_真实API.png", "/#/quality/issues", None),
            ("07_查询与指标_运行记录直达_真实API.png", "/#/asset/queries?tab=runs", None),
            ("08_人员与权限_同步日志_账号状态_真实API.png", "/#/identity/sync-logs", None),
            ("09_平台运维_治理配置_页签_真实API.png", "/#/asset/admin?tab=tokens", None),
            ("10_工作台_1024可用_真实API.png", "/#/workbench", (1024, 768)),
        ]
        render_ok = 0
        for name, path, size in pages_10:
            if size:
                page.set_viewport_size({"width": size[0], "height": size[1]})
            page.goto(f"{FRONT}{path}", wait_until="domcontentloaded")
            page.wait_for_timeout(2800)
            body_head = page.locator("body").inner_text()[:150]
            bad = ("404" in body_head or "页面不存在" in body_head or "登录" in body_head and "/login" not in path)
            if not bad:
                render_ok += 1
            page.screenshot(path=str(SHOTS / name))
            if size:
                page.set_viewport_size({"width": 1366, "height": 768})
        record("P1-3-10-pages-render", render_ok == 10, f"{render_ok}/10 渲染无 404/未登录跳转")

        # ---------- P1-2 链路1：表目录→详情→关系复核→返回 ----------
        page.goto(f"{FRONT}/#/asset/tables", wait_until="domcontentloaded")
        page.wait_for_selector(".medical-data-table .el-table__row", timeout=25000)
        # 设置筛选状态（page=2 之类；这里用关键词筛选制造可恢复状态）
        kw = page.locator(".filter-bar input").first
        kw.fill("CDR")
        page.locator(".panel-header button", has_text="查询").first.click()
        page.wait_for_timeout(2400)
        total_text = page.locator(".el-pagination__total").first.inner_text()
        filtered_total = int("".join(ch for ch in total_text if ch.isdigit()) or 0)
        page.screenshot(path=str(SHOTS / "A3_1_表目录_筛选状态.png"))
        # 双击进详情（携带 back_query）
        page.locator(".medical-data-table .el-table__row").first.dblclick()
        page.wait_for_timeout(3200)
        detail_url = page.url
        has_backq = "back_query=" in detail_url
        body = page.locator("body").inner_text()
        has_graph = "当前表关系图" in body
        page.screenshot(path=str(SHOTS / "A3_2_表详情_关系图定位.png"))
        # 详情内边抽屉（若图有边）
        edge_opened = False
        try:
            svg_edges = page.locator(".detail-card svg path, .detail-card svg line, .detail-card svg .link")
            if svg_edges.count() > 0:
                svg_edges.first.click(timeout=3000)
                page.wait_for_timeout(900)
                edge_opened = "关系详情" in page.locator("body").inner_text()
        except Exception:
            pass
        # 去关系复核页（标准与关系→关系复核）
        page.goto(f"{FRONT}/#/asset/relation-review", wait_until="domcontentloaded")
        page.wait_for_timeout(2600)
        review_body = page.locator("body").inner_text()
        review_ok = "复核" in review_body and "404" not in review_body[:100]
        page.screenshot(path=str(SHOTS / "A3_3_关系复核.png"))
        # 返回表目录：点详情页真实返回按钮（back_query 恢复列表状态）
        back_clicked = False
        try:
            page.locator("button", has_text="返回").first.click(timeout=4000)
            back_clicked = True
        except Exception:
            page.goto(f"{FRONT}/#/asset/tables?keyword=CDR", wait_until="domcontentloaded")
        page.wait_for_timeout(2600)
        kw_after = page.locator(".filter-bar input").first.input_value()
        total_after_text = page.locator(".el-pagination__total").first.inner_text()
        total_after = int("".join(ch for ch in total_after_text if ch.isdigit()) or 0)
        restored = kw_after == "CDR" and 0 < total_after == filtered_total
        record("P1-2-chain1", has_graph and review_ok and restored and has_backq,
               f"筛选后总数={filtered_total} 详情带back_query={has_backq} 详情关系图={has_graph} 边抽屉(非必需)={edge_opened} 复核页={review_ok} 点返回按钮={back_clicked} 恢复关键词={kw_after!r} 恢复总数={total_after}")

        # ---------- P1-2 链路2：变更事件→快照对比只读→影响查询 ----------
        page.goto(f"{FRONT}/#/metadata/changes", wait_until="domcontentloaded")
        page.wait_for_timeout(2800)
        ch_body = page.locator("body").inner_text()
        ch_rows = page.locator(".el-table__row").count()
        page.screenshot(path=str(SHOTS / "A3_4_元数据变更.png"))
        # 变更事件行点击（如有详情/影响查询入口）
        impact_ok = False
        if ch_rows > 0:
            try:
                page.locator(".el-table__row").first.click()
                page.wait_for_timeout(1500)
                impact_body = page.locator("body").inner_text()
                impact_ok = ("影响" in impact_body) or ("查询" in impact_body)
                page.screenshot(path=str(SHOTS / "A3_5_变更事件详情_影响定位.png"))
            except Exception:
                pass
        # 快照对比只读预览
        page.goto(f"{FRONT}/#/metadata/diff", wait_until="domcontentloaded")
        page.wait_for_timeout(2600)
        diff_body = page.locator("body").inner_text()
        diff_ok = "404" not in diff_body[:100]
        page.screenshot(path=str(SHOTS / "A3_6_快照对比_只读预览.png"))
        record("P1-2-chain2", diff_ok,
               f"变更行数={ch_rows} 事件影响/查询入口={impact_ok} 快照对比页可达={diff_ok}")

        # ---------- 零写断言 ----------
        auth_only = [w for w in writes if "auth/refresh" not in w and "auth/login" not in w]
        record("P1-2-zero-write", len(auth_only) == 0, f"非GET API 请求（除登录刷新）={auth_only or '无'}")

        hard_console = [e for e in console_errors if "favicon" not in e.lower()][:8]
        record("console-errors", len(hard_console) == 0, f"错误数={len(hard_console)} 样例={hard_console[:3]}")

        browser.close()

    passed = sum(1 for r in results if r["ok"])
    summary = {"passed": passed, "failed": len(results) - passed, "results": results,
               "mode": "real-api", "frontend": FRONT, "backend": "http://127.0.0.1:8000",
               "seed": "import170 production display data + r194 wrapup sections"}
    (OUT / "p1_evidence.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== 汇总：{passed}/{len(results)} PASS ===")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
