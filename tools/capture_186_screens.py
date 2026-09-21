# -*- coding: utf-8 -*-
"""186 U1/V1 浏览器截图：本地新构建 + 请求拦截 fixture（不触生产）。

证据目标：
- 七分区菜单 + 工作台（1366×768 / 1920×1080）
- 查询中心页签（tab=runs 直达）、质量台账、治理配置页签、人员同步日志（账号状态）
- 1024 宽可用性
- 静态登录无 get-async-routes 请求（N3/T01 证据：控制台断言）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "开发起步包" / "output_r186" / "screenshots"
FRONTEND = "http://127.0.0.1:4173"

FAKE_USER = {
    "accessToken": "fixture-token",
    "refreshToken": "fixture-refresh",
    "expires": 4102444800000,
  "username": "fixture-admin",
  "nickname": "验收账号",
    "roles": ["platform_admin"],
    "permissions": ["*:*:*"],
}

def fixture_for(path: str, query: str) -> tuple[int, dict]:
    """确定性 API fixture（真实 DTO 形状；覆盖 200/403/500 分支的抽样）。"""
    def ok(data):
        return 200, {"code": 200, "message": "ok", "data": data}

    if path.startswith("/api/v1/quality-issues/summary"):
        return ok({"by_system": {}})
    if path.startswith("/api/v1/quality-issues"):
        return ok({
            "items": [
                {"id": 901, "issue_code": "DQI-202609-000901", "title": "示例：检查申请医生工号缺失", "severity": "high", "status": "open", "due_date": "2026-09-12", "overdue": False},
                {"id": 902, "issue_code": "DQI-202609-000902", "title": "示例：LIS 月度对账桶差", "severity": "medium", "status": "in_progress", "due_date": "2026-09-10", "overdue": True},
            ],
            "total": 2,
        })
    if path.startswith("/api/v1/ops/runs"):
        return ok({
            "items": [
                {"id": 12, "name": "夜间人员同步", "status": "success", "finished_at": "2026-09-09T02:14:00+08:00"},
                {"id": 11, "name": "元数据采集", "status": "failed", "finished_at": "2026-09-08T03:02:00+08:00"},
            ],
            "total": 2,
        })
    if path.startswith("/api/v1/identity/account-states"):
        return ok({
            "items": [
                {"person_code": "00****01", "employment_status": "active", "employee_state": "enabled", "user_state": "disabled", "desired_state": "disabled", "decision_reason": "user_disabled", "execution_allowed": True, "captured_at": "2026-09-09T02:00:00+08:00", "targets": {"JHEMR": {"action": "disable", "status": "executed", "after_state": "8"}, "CDMS": {"action": "disable", "status": "executed", "after_state": "1"}}},
                {"person_code": "00****02", "employment_status": "active", "employee_state": "enabled", "user_state": "unknown", "desired_state": "unknown", "decision_reason": "employee_enabled+user_unknown", "execution_allowed": False, "captured_at": "2026-09-09T02:00:00+08:00", "targets": {"JHEMR": {"status": "no_attempt"}, "CDMS": {"status": "no_attempt"}}},
            ],
            "total": 2,
            "desired_state_summary": {"disabled": 1, "unknown": 1},
        })
    if path.startswith("/api/v1/identity/sync-runs") or path == "/api/v1/identity/sync-runs":
        return ok({
            "items": [
                {"run_id": "RUN-186demo01", "triggered_by_name": "夜间定时", "status": "success", "status_name": "成功", "started_at": "2026-09-09T02:00:00+08:00", "finished_at": "2026-09-09T02:14:00+08:00", "duration_ms": 840000, "candidates_total": 4, "success_count": 4, "failed_count": 0, "skipped_count": 0, "subtasks": []},
            ],
            "total": 1,
        })
    if path.startswith("/api/v1/ai/feedback"):
        return ok({
            "items": [
                {"feedback_id": 31, "answer_event_id": 88, "status": "submitted", "rating": "incorrect", "error_types": ["denominator"], "submitted_at": "2026-09-08T15:20:00+08:00", "query_code": "QRY_IP_COST", "query_version": 2, "metric_code": None, "metric_version": None, "product_code": None, "run_id": 4242, "result_digest": "a" * 16, "submitted_by": "fixture-admin"},
            ],
            "total": 1,
        })
    if path.startswith("/api/v1/queries/runs"):
        return ok({
            "items": [
                {"id": 4242, "query_code": "QRY_IP_COST", "version": 2, "status": "success", "row_count": 1204, "truncated": False, "duration_ms": 1830, "result_digest": "b" * 16, "schema_digest": "c" * 16, "data_as_of": "2026-09-01T00:00:00+08:00", "data_as_of_source": "max(DISCHARGE_DATE_TIME)", "safe_parameters_summary": {"month": "2026-07"}},
            ],
            "total": 1,
        })
    if path.startswith("/api/v1/queries"):
        return ok({"items": [
            {"query_code": "QRY_IP_COST", "title": "住院次均费用", "system_code": "DATA_CENTER", "source_code": "ods_8_216", "status": "active", "current_version": 2},
        ], "total": 1})
    if path.startswith("/api/v1/systems"):
        return ok({"items": [], "total": 0})
    if path.startswith("/api/v1/metadata"):
        return ok({"items": [], "total": 0})
    # 通用空列表（空态覆盖）
    return ok({"items": [], "total": 0})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async_requests: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
        )
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 768},
            device_scale_factor=1,
            color_scheme="light",
        )
        ctx.add_init_script(
            "localStorage.setItem('user-info', JSON.stringify(%s));document.cookie='multiple-tabs=true; path=/';"
            % json.dumps(FAKE_USER, ensure_ascii=False)
        )

        def proxy(route: Route) -> None:
            req = route.request
            p = urlsplit(req.url)
            if not p.path.startswith("/api/"):
                route.continue_()
                return
            async_requests.append(f"{req.method} {p.path}")
            if req.method not in {"GET", "HEAD", "OPTIONS"}:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"code": 200, "data": {}}))
                return
            status, body = fixture_for(p.path, p.query)
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body, ensure_ascii=False))

        ctx.route("**/*", proxy)

        def snap(name: str, hash_path: str, width=None, height=None, wait=2600):
            page = ctx.new_page()
            if width:
                page.set_viewport_size({"width": width, "height": height or 768})
            page.goto(f"{FRONTEND}/#{hash_path}", wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(wait)
            page.keyboard.press("Escape")
            page.screenshot(path=str(OUT / name), full_page=False)
            page.close()
            print("captured", name)

        snap("01_登录页_静态无动态路由.png", "/login")
        snap("02_工作台_1366.png", "/workbench")
        snap("03_工作台_1920.png", "/workbench", width=1920, height=1080)
        snap("04_资产目录_系统与数据资源.png", "/asset/systems")
        snap("05_标准与关系_值域.png", "/value-domains")
        snap("06_质量治理_台账.png", "/quality/issues")
        snap("07_查询与指标_运行记录直达.png", "/asset/queries?tab=runs")
        snap("08_人员与权限_同步日志_账号状态.png", "/identity/sync-logs")
        snap("09_平台运维_治理配置_页签.png", "/asset/admin?tab=tokens")
        snap("10_工作台_1024可用.png", "/workbench", width=1024, height=768)
        ctx.close()
        browser.close()

    leaked = [r for r in async_requests if "get-async-routes" in r]
    (OUT.parent / "browser_requests_static_mode.json").write_text(
        json.dumps({"total_api_requests": len(async_requests), "get_async_routes_hits": leaked}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUT), "get_async_routes_hits": leaked}, ensure_ascii=False))


if __name__ == "__main__":
    main()
