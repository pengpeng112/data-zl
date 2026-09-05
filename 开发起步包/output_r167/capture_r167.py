from pathlib import Path

from playwright.sync_api import sync_playwright


OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(exist_ok=True)


def payload(url: str):
    if "/quality/ai/status" in url:
        return {"code": 0, "data": {"enabled": True, "configured": True, "provider": "hospital_llm", "success_count": 12, "last_success_at": "2026-08-30T08:15:00+08:00", "hospital_llm": {"enabled": True, "configured": True, "model": "deepseek-r1", "host": "10.10.8.*:9000"}}}
    if "/quality/ai/patrol/targets" in url:
        targets = [
            ("HIS", "PAT_VISIT", "病人住院主记录", "字段登记异常；关系孤儿率 0.29%/0.55%", 12077),
            ("SM", "MED_OPERATION_MASTER", "病人手术主记录", "字段登记异常；关系孤儿率 0.066%/0.19%", 11218),
            ("YDHL", "INPATIENTS", "移动护理镜像区数据表", "字段登记异常；关系孤儿率 0.7%", 12580),
        ]
        return {"code": 0, "data": {"plan": {"label": "每日 02:00", "status": "demo_only", "scheduler_enabled": False}, "targets": [{"system_code": "DATA_CENTER", "source_code": "ods_demo", "schema_name": s, "table_name": t, "name_cn": n, "column_count": 100, "issue_label": issue, "finding_ids": [fid, fid + 1], "evidence": {"rule_id": "TABLE_ZERO_COLUMNS", "finding_id": fid, "metric_value": issue, "captured_at": "2026-08-29T02:00:02+08:00", "data_as_of": "2026-08-29T02:00:06+08:00", "snapshot_version": "quality-run-49"}} for s, t, n, issue, fid in targets]}}
    if "/quality/ai/patrol/runs" in url:
        return {"code": 0, "data": {"total": 1, "page": 1, "page_size": 10, "items": [{"patrol_run_id": "patrol-20260830-demo", "started_at": "2026-08-30T08:15:00+08:00", "tables_total": 3, "tables_done": 3, "summary": "3/3 张表分析成功", "jobs": [1, 2, 3]}]}}
    if "/quality/findings" in url or "/quality/ai/jobs" in url:
        return {"code": 0, "data": {"total": 0, "page": 1, "page_size": 20, "items": []}}
    if "/ai/ai-sql/history" in url:
        return {"code": 0, "data": {"total": 1, "page": 1, "page_size": 20, "items": [{"id": 1, "request": {"question_summary": "按月统计住院人次并关联出院方式", "selected_tables": ["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"], "context_digest": {"tables": 2}}, "response_summary": "generated=486 chars; blocked=False", "called_at": "2026-08-30T08:18:00+08:00"}]}}
    if url.endswith("/api/v1/tables") or "/api/v1/tables?" in url:
        return {"code": 0, "data": {"total": 2, "page": 1, "page_size": 30, "items": [{"system_code": "DATA_CENTER", "source_code": "ods_8_216", "schema_name": "HIS", "table_name": "PAT_VISIT", "table_name_cn": "病人住院主记录", "comment": "", "column_count": 268, "domain": "住院", "source": "ods"}, {"system_code": "DATA_CENTER", "source_code": "ods_8_216", "schema_name": "HIS", "table_name": "PAT_MASTER_INDEX", "table_name_cn": "病人主索引", "comment": "", "column_count": 90, "domain": "患者", "source": "ods"}]}}
    if "/permissions/me" in url:
        return {"code": 0, "data": {"user_identifier": "demo", "roles": ["admin"], "permissions": ["asset.quality.ai.view", "asset.quality.ai.analyze", "asset.quality.ai.connection_test", "asset.quality.ai.review", "ai.context.read"]}}
    if "/routes" in url:
        return {"code": 0, "data": []}
    return {"code": 0, "data": {}}


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    context.add_init_script("""localStorage.setItem('user-info', JSON.stringify({accessToken:'demo',expires:4102444800000,refreshToken:'',username:'demo',nickname:'演示账号',roles:['admin'],permissions:['asset.quality.ai.view','asset.quality.ai.analyze','asset.quality.ai.connection_test','asset.quality.ai.review','ai.context.read']})); document.cookie='multiple-tabs=true; path=/';""")
    page = context.new_page()
    page.route("**/api/**", lambda route: route.fulfill(status=200, content_type="application/json", body=__import__("json").dumps(payload(route.request.url), ensure_ascii=False)))
    page.goto("http://127.0.0.1:4173/#/asset/ai-quality", wait_until="networkidle")
    page.get_by_text("AI 巡查演示", exact=True).click()
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / "ai-quality-patrol.png"), full_page=True)
    page.goto("http://127.0.0.1:4173/#/asset/ai-sql", wait_until="networkidle")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / "ai-sql-workbench.png"), full_page=True)
    browser.close()
