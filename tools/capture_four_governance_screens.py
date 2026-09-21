"""Capture four PPT-ready governance screenshots from live read-only APIs."""
from __future__ import annotations
import json, sys
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from e2e_graph_acceptance import LOCAL_PORT, TunnelForward, fetch_session_material  # noqa: E402

FRONTEND = "http://127.0.0.1:4173"
PRODUCTION = f"http://127.0.0.1:{LOCAL_PORT}"
OUT = Path(r"D:\中心\20、评级\3、大赛\2026\14山东省数智健康大赛\多源医疗数据资产图谱与高质量数据治理实践\参赛截图_系统核查_20260830\四类治理配图")
PAGES = {
    "01_资产治理_资产目录.png": "/asset/tables",
    "02_关系治理_证据分级与人工确认.png": "/asset/relation-review",
    "03_标准治理_医学编码与字典映射.png": "/dict/mappings",
    "04_质量治理_规则与问题闭环.png": "/asset/quality",
}

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    session=fetch_session_material(); tunnel=TunnelForward(); tunnel.start(); tunnel.serve()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=True)
            context=pw.chromium.launch
            ctx=browser.new_context(viewport={"width":1920,"height":1080},device_scale_factor=1,color_scheme="light")
            ctx.add_init_script("localStorage.setItem('user-info', JSON.stringify(%s));document.cookie='multiple-tabs=true; path=/';" % json.dumps({**session,"nickname":"演示账号","username":"demo"},ensure_ascii=False))
            def proxy(route: Route) -> None:
                req=route.request; p=urlsplit(req.url)
                if not (p.path.startswith('/api/') or p.path=='/get-async-routes'): route.continue_(); return
                if req.method not in {'GET','HEAD','OPTIONS'}: route.abort('blockedbyclient'); return
                headers={k:v for k,v in req.headers.items() if k.lower() not in {'host','origin','referer','content-length'}}
                headers['Authorization']=f"Bearer {session['accessToken']}"
                target=f"{PRODUCTION}{p.path}"+(f"?{p.query}" if p.query else '')
                route.fulfill(response=ctx.request.fetch(target,method=req.method,headers=headers,timeout=45000))
            ctx.route('**/*',proxy)
            for filename,path in PAGES.items():
                page=ctx.new_page(); page.goto(f"{FRONTEND}/#{path}",wait_until='networkidle',timeout=90000); page.wait_for_timeout(3500)
                # Keep real menus, while removing popovers/tooltips that obscure the subject.
                page.keyboard.press('Escape'); page.screenshot(path=str(OUT/filename),full_page=False); page.close()
            ctx.close(); browser.close()
    finally:
        tunnel.stop()
    print(json.dumps({"output":str(OUT),"count":len(PAGES)},ensure_ascii=False))

if __name__=='__main__': main()
