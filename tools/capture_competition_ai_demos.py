"""Capture polished, explicitly labelled AI demonstration states for the competition deck.

Read-only production GETs are proxied through the normal tunnel. The AI SQL result
is a browser-only fixture so the screenshot never submits a production POST or
stores a generated prompt/history record. The capture banner labels this state as
脱敏演示视图.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from e2e_graph_acceptance import LOCAL_PORT, TunnelForward, fetch_session_material  # noqa: E402

FRONTEND = "http://127.0.0.1:4173"
PRODUCTION = f"http://127.0.0.1:{LOCAL_PORT}"
OUTPUT = Path(r"D:\中心\20、评级\3、大赛\2026\14山东省数智健康大赛\多源医疗数据资产图谱与高质量数据治理实践\参赛截图_系统核查_20260830")

DEMO_SQL = {
    "sql": """WITH visit_scope AS (\n  SELECT p.PATIENT_ID, p.VISIT_ID, p.DISCHARGE_DISPOSITION,\n         p.DISCHARGE_DATE_TIME\n  FROM DATA_CENTER.V_EMR_PAT_VISIT p\n  WHERE p.DISCHARGE_DATE_TIME >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -12)\n)\nSELECT TO_CHAR(TRUNC(DISCHARGE_DATE_TIME, 'MM'), 'YYYY-MM') AS 月份,\n       DISCHARGE_DISPOSITION AS 离院方式,\n       COUNT(*) AS 住院人次\nFROM visit_scope\nGROUP BY TRUNC(DISCHARGE_DATE_TIME, 'MM'), DISCHARGE_DISPOSITION\nORDER BY TRUNC(DISCHARGE_DATE_TIME, 'MM')\nFETCH NEXT 100 ROWS ONLY""",
    "risk": {"blocked": False, "readonly": True, "limit_present": True, "notes": "仅生成 SELECT；未执行"},
    "dialect": "oracle", "executed": False,
    "context_digest": {"tables": 2, "relations": 1, "value_domains": 1, "payload_bytes": 18420, "truncated": False},
}
DEMO_PATROL_JOBS = {
    9201: {"id": 9201, "job_id": 9201, "task_type": "finding_batch", "status": "succeeded", "finding_ids": [12077], "result": {"id": 9201, "job_id": 9201, "risk_level": "medium", "summary": "发现字段登记与关系证据不完整，建议补充字段级 JOIN 证据后复核。", "review_status": "pending", "structured_result": {"root_causes": [], "recommendations": [], "false_positive": {"possible": False}}}},
    9202: {"id": 9202, "job_id": 9202, "task_type": "finding_batch", "status": "succeeded", "finding_ids": [12218], "result": {"id": 9202, "job_id": 9202, "risk_level": "low", "summary": "关系覆盖率存在提升空间，当前结论基于脱敏元数据。", "review_status": "pending", "structured_result": {"root_causes": [], "recommendations": [], "false_positive": {"possible": False}}}},
    9203: {"id": 9203, "job_id": 9203, "task_type": "finding_batch", "status": "succeeded", "finding_ids": [12580], "result": {"id": 9203, "job_id": 9203, "risk_level": "medium", "summary": "移动护理镜像表存在治理提醒，建议纳入下一轮人工复核。", "review_status": "pending", "structured_result": {"root_causes": [], "recommendations": [], "false_positive": {"possible": False}}}},
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    session = fetch_session_material()
    tunnel = TunnelForward(); tunnel.start(); tunnel.serve()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1, color_scheme="light")
            context.add_init_script("localStorage.setItem('user-info', JSON.stringify(%s));document.cookie='multiple-tabs=true; path=/';" % json.dumps({**session, "nickname": "演示账号", "username": "demo"}, ensure_ascii=False))

            def proxy(route: Route) -> None:
                req = route.request; parsed = urlsplit(req.url)
                if not (parsed.path.startswith("/api/") or parsed.path == "/get-async-routes"):
                    route.continue_(); return
                # The generated SQL is a local, clearly labelled UI fixture.
                if req.method == "POST" and parsed.path.endswith("/ai/ai-sql/generate"):
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"code": 0, "message": "success", "data": DEMO_SQL}, ensure_ascii=False)); return
                if req.method == "POST" and parsed.path.endswith("/quality/ai/patrol/run"):
                    jobs = [{"table": "HIS.PAT_VISIT", "job_id": 9201}, {"table": "SM.MED_OPERATION_MASTER", "job_id": 9202}, {"table": "YDHL.INPATIENTS", "job_id": 9203}]
                    route.fulfill(status=202, content_type="application/json", body=json.dumps({"code": 0, "message": "accepted", "data": {"patrol_run_id": "demo-patrol-20260831", "jobs": jobs, "errors": []}}, ensure_ascii=False)); return
                if req.method == "GET" and "/quality/ai/jobs/" in parsed.path:
                    try: job = DEMO_PATROL_JOBS[int(parsed.path.rsplit("/", 1)[-1])]
                    except (KeyError, ValueError): job = None
                    if job:
                        route.fulfill(status=200, content_type="application/json", body=json.dumps({"code": 0, "message": "success", "data": job}, ensure_ascii=False)); return
                if req.method not in {"GET", "HEAD", "OPTIONS"}:
                    route.abort("blockedbyclient"); return
                headers = {k: v for k, v in req.headers.items() if k.lower() not in {"host", "origin", "referer", "content-length"}}
                headers["Authorization"] = f"Bearer {session['accessToken']}"
                target = f"{PRODUCTION}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
                route.fulfill(response=context.request.fetch(target, method=req.method, headers=headers, timeout=45_000))

            context.route("**/*", proxy)

            # AI patrol: switch to the complete target/evidence view without pressing
            # the state-changing “一键巡查” button.
            page = context.new_page(); page.goto(f"{FRONTEND}/?capture=1#/asset/ai-quality", wait_until="networkidle", timeout=90_000); page.wait_for_timeout(3000)
            page.get_by_text("AI 巡查演示", exact=True).click(); page.wait_for_timeout(1800)
            page.get_by_text("一键巡查", exact=True).click(); page.wait_for_timeout(1800)
            page.screenshot(path=str(OUTPUT / "08_AI巡查完整功能.png"), full_page=False); page.close()

            # AI SQL: fill a realistic request and select two real catalogue tables.
            page = context.new_page(); page.goto(f"{FRONTEND}/?capture=1#/asset/ai-sql", wait_until="networkidle", timeout=90_000); page.wait_for_timeout(1800)
            page.locator("textarea").first.fill("按月统计近12个月住院人次，并关联离院方式；结果限制100行")
            select = page.locator(".table-select input").first
            select.click(); select.fill("PAT_VISIT"); page.wait_for_timeout(900)
            options = page.locator(".el-select-dropdown__item:not(.is-disabled)")
            if options.count(): options.first.click()
            page.keyboard.press("Escape")
            select.click(); select.fill("PAT_MASTER_INDEX"); page.wait_for_timeout(900)
            options = page.locator(".el-select-dropdown__item:not(.is-disabled)")
            if options.count(): options.first.click()
            page.keyboard.press("Escape")
            page.locator("textarea").first.click()
            page.wait_for_timeout(400)
            page.get_by_text("3. 生成只读 SQL", exact=True).click(force=True, timeout=5000); page.wait_for_timeout(1800)
            page.screenshot(path=str(OUTPUT / "09_AI写SQL完整生成结果_脱敏演示.png"), full_page=False); page.close()
            browser.close()
    finally:
        tunnel.stop()
    print(json.dumps({"output": str(OUTPUT), "count": 2}, ensure_ascii=False))


if __name__ == "__main__":
    main()
