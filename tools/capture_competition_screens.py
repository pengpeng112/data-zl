"""Capture anonymized competition screenshots against the live read-only platform API.

The frontend must already be running at http://127.0.0.1:4173. A short-lived
JWT is minted in the application container, kept in memory, and never printed
or written to disk. The script only forwards browser reads to the production
API through an SSH tunnel; it does not submit any state-changing request.
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
OUTPUT = Path(
    r"D:\中心\20、评级\3、大赛\2026\14山东省数智健康大赛"
    r"\多源医疗数据资产图谱与高质量数据治理实践\参赛截图_系统核查_20260830"
)

PAGES = {
    "01_数据资产指挥中心.png": "/welcome",
    "02_资产目录.png": "/asset/tables",
    "03_关系图谱.png": "/asset/graph",
    "04_探查发现.png": "/probe-findings",
    "05_值域知识.png": "/value-domains",
    "06_AI质控分析.png": "/asset/ai-quality",
    "07_治理审计.png": "/ops/audit",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    session = fetch_session_material()
    tunnel = TunnelForward()
    tunnel.start()
    tunnel.serve()
    console_errors: dict[str, list[str]] = {}
    api_errors: dict[str, list[str]] = {}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=True,
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                color_scheme="light",
            )
            safe_session = {
                **session,
                "nickname": "演示账号",
                "username": "demo",
            }
            context.add_init_script(
                "localStorage.setItem('user-info', JSON.stringify(%s));"
                "document.cookie='multiple-tabs=true; path=/';"
                % json.dumps(safe_session, ensure_ascii=False)
            )

            def proxy_api(route: Route) -> None:
                request = route.request
                parsed = urlsplit(request.url)
                if not (
                    parsed.path.startswith("/api/")
                    or parsed.path == "/get-async-routes"
                ):
                    route.continue_()
                    return
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    route.abort("blockedbyclient")
                    return
                headers = {
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() not in {"host", "origin", "referer", "content-length"}
                }
                headers["Authorization"] = f"Bearer {session['accessToken']}"
                target = f"{PRODUCTION}{parsed.path}"
                if parsed.query:
                    target += f"?{parsed.query}"
                response = context.request.fetch(
                    target,
                    method=request.method,
                    headers=headers,
                    timeout=45_000,
                )
                route.fulfill(response=response)

            context.route("**/*", proxy_api)

            for filename, route_path in PAGES.items():
                page = context.new_page()
                errors: list[str] = []
                failed_api: list[str] = []
                page.on(
                    "console",
                    lambda message, bucket=errors: bucket.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on(
                    "response",
                    lambda response, bucket=failed_api: bucket.append(
                        f"{response.status} {urlsplit(response.url).path}"
                    )
                    if "/api/" in response.url and response.status >= 400
                    else None,
                )
                page.goto(
                    f"{FRONTEND}/?capture=1#{route_path}",
                    wait_until="networkidle",
                    timeout=90_000,
                )
                page.wait_for_timeout(2_500 if "graph" not in route_path else 8_000)
                page.screenshot(path=str(OUTPUT / filename), full_page=False)
                console_errors[filename] = errors[:10]
                api_errors[filename] = failed_api[:10]
                page.close()

            browser.close()
    finally:
        tunnel.stop()

    summary = {
        "screenshots": list(PAGES),
        "viewport": "1920x1080",
        "source": "live production read-only API through SSH tunnel",
        "console_errors": console_errors,
        "api_errors": api_errors,
    }
    (OUTPUT / "截图核查摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT), "count": len(PAGES)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
