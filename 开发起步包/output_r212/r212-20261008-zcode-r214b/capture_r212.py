# -*- coding: utf-8 -*-
"""R212 S3：真实 Chrome（channel=chrome）E2 抽测脚本。

覆盖（212 §5/§6 对候选增量面的分层抽样）：
  1. 登录/改密/逐页渲染（管理员，候选增量相关页集：AI/质量/数据集/核心资产/审计）
  2. F03 受限身份（asset_viewer）：菜单可见性 + 写按钮隐藏（v-perms）
  3. B07 浏览器级 403 信封：页面上下文真实 fetch（login→Bearer→写端点），
     断言 {code:403,message:'权限不足',data.resource_code,detail,request_id}；非403不重塑抽查
  4. 退出再登录

凭据经环境变量传入（R212_ADMIN_PW / R212_VIEWER_PW），不写入任何文件。
产出：browser/screenshots/*.png + browser/r212_s3_results.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8898"
HERE = Path(__file__).parent
SHOT = HERE / "browser" / "screenshots"
SHOT.mkdir(parents=True, exist_ok=True)

ADMIN_PAGES = [
    ("01", "/welcome", "运行总览"),
    ("02", "/asset/tables", "表与字段"),
    ("03", "/asset/graph", "关系图谱"),
    ("04", "/value-domains", "值域知识库"),
    ("05", "/asset/ai-sql", "AI辅助编写"),
    ("06", "/datasets", "数据集目录"),
    ("07", "/quality/issues", "质量台账"),
    ("08", "/quality/observations", "观测记录"),
    ("09", "/quality/controls", "质控清单"),
    ("10", "/ops/audit", "操作审计"),
]

STATE_JS = """
() => {
  const main = document.querySelector('.app-main');
  const skel = document.querySelector('.app-main .route-skeleton');
  const h1 = document.querySelector('.app-main .re-page-header h1');
  const tags = [...document.querySelectorAll('.scroll-item.is-active')].map(e => (e.textContent || '').trim());
  const crumb = [...document.querySelectorAll('.el-breadcrumb__item')].map(e => (e.textContent || '').trim()).join('/');
  const txt = main ? (main.innerText || '').replace(/\\s+/g, ' ').trim() : '';
  return {hash: location.hash, mainLen: txt.length, head: txt.slice(0, 120), skeleton: !!skel,
          h1: h1 ? h1.textContent.trim() : null, activeTags: tags, crumb};
}
"""

B07_FETCH_JS = """
async ([username, password, writeUrl, writeBody]) => {
  // 与前端 axios 一致携带 X-Requested-With，过 CSRF Origin 校验（161 P3-2 既定前提）
  const H = {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'};
  const login = await fetch('/api/v1/auth/login', {method: 'POST', headers: H,
    body: JSON.stringify({username, password})});
  const loginJson = await login.json().catch(() => ({}));
  const token = loginJson && loginJson.data && (loginJson.data.access_token || loginJson.data.accessToken);
  if (!token) return {step: 'login', status: login.status, body: loginJson};
  const resp = await fetch(writeUrl, {
    method: 'PATCH',
    headers: {...H, 'Authorization': 'Bearer ' + token},
    body: JSON.stringify(writeBody)});
  const body = await resp.json().catch(() => null);
  return {step: 'write', status: resp.status, body,
          envelope: body && typeof body === 'object' ? {
            keys: Object.keys(body).sort(),
            code: body.code, message: body.message,
            resource_code: body.data && body.data.resource_code,
            detail: body.detail, has_request_id: 'request_id' in body} : null};
}
"""


def sample(page):
    return page.evaluate(STATE_JS)


def wait_rendered(page, timeout_ms=15000, min_len=30):
    deadline = time.time() + timeout_ms / 1000
    st = sample(page)
    while time.time() < deadline:
        st = sample(page)
        if not st["skeleton"] and st["mainLen"] > min_len:
            return st
        page.wait_for_timeout(300)
    return st


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:40]


def main():
    admin_pw = os.environ.get("R212_ADMIN_PW", "")
    viewer_pw = os.environ.get("R212_VIEWER_PW", "")
    if not admin_pw or not viewer_pw:
        raise SystemExit("缺少 R212_ADMIN_PW / R212_VIEWER_PW 环境变量")
    results = {"pages": [], "f03_viewer": {}, "b07": {}, "console_errors": []}

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
            results["browser_mode"] = "chrome-headed"
        except Exception:
            browser = p.chromium.launch(channel="chrome", headless=True)
            results["browser_mode"] = "chrome-headless"
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on("pageerror", lambda e: results["console_errors"].append(f"pageerror: {e}"))
        page.on("console", lambda m: results["console_errors"].append(f"console.error: {m.text[:200]}")
                if m.type == "error" else None)

        # ---- 管理员登录（账号已过改密轮，直接登录） ----
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.get_by_placeholder("账号", exact=True).fill("platform-admin")
        page.get_by_placeholder("密码", exact=True).fill(admin_pw)
        page.get_by_role("button", name="登录").click()
        page.wait_for_timeout(2500)
        st = wait_rendered(page)
        results["admin_login_landing"] = {"hash": st["hash"], "head": st["head"][:80]}
        page.screenshot(path=str(SHOT / "01_管理员登录_落地.png"))

        # ---- 逐页抽测（hash 直达 + 等渲染） ----
        for idx, route, title in ADMIN_PAGES:
            page.evaluate("r => { location.hash = '#' + r; }", route)
            st = wait_rendered(page)
            page.wait_for_timeout(600)  # 页签条与路由过渡完成后再采样
            st = sample(page)
            accept = {title} | ({"首页"} if title == "运行总览" else set())
            tag_ok = any(t in accept for t in st["activeTags"])
            # AI 写 SQL 页签名可能与路由名不同（h1 为准），标签空时以正文标题判定
            h1_ok = title == "AI辅助编写" and st["h1"] and "AI" in st["h1"] and "SQL" in st["h1"].upper()
            content_ok = (not st["skeleton"]) and st["mainLen"] > 30
            ok = bool((tag_ok or h1_ok) and content_ok)
            results["pages"].append({"idx": idx, "route": route, "title": title, "pass": ok,
                                     "evidence": {"hash": st["hash"], "activeTags": st["activeTags"],
                                                  "h1": st["h1"], "mainLen": st["mainLen"],
                                                  "head": st["head"][:100], "skeleton": st["skeleton"]}})
            page.screenshot(path=str(SHOT / f"{idx}_{safe_name(title)}.png"))

        # ---- AI SQL 页专门证据（FIX-211-01 增量面）：页面加载且无 500 痕迹 ----
        page.evaluate("r => { location.hash = '#' + r; }", "/asset/ai-sql")
        st = wait_rendered(page)
        results["ai_sql_page"] = {"mainLen": st["mainLen"], "head": st["head"][:100],
                                  "has_500_text": "500" in (st["head"] or "") or "上下文构建失败" in (st["head"] or "")}

        # ---- B07：浏览器内真实 fetch 信封断言（viewer 对写端点） ----
        b07 = page.evaluate(B07_FETCH_JS, [
            "r212-viewer", viewer_pw,
            "/api/v1/value-domains/999999/confirm",   # viewer 无 value_domain.confirm
            {"reason": "r212-browser-envelope-probe"}])
        results["b07"]["viewer_confirm_403"] = b07
        b07b = page.evaluate(B07_FETCH_JS, [
            "platform-admin", admin_pw,
            "/api/v1/value-domains/999999/confirm",   # 管理员有权但对象不存在 -> 404，验证非403不重塑
            {"reason": "r212-browser-envelope-probe"}])
        results["b07"]["admin_non403_shape"] = b07b
        page.screenshot(path=str(SHOT / "11_B07_信封证据页.png"))

        # ---- F03：viewer 登录，菜单/按钮可见性 ----
        avatar = page.locator(".el-dropdown-link", has_text="platform-admin")
        if avatar.count() > 0:
            avatar.first.click(); page.wait_for_timeout(700)
            page.locator(".el-dropdown-menu__item", has_text="退出系统").first.click()
            page.wait_for_timeout(700)
            confirm = page.locator(".el-message-box").get_by_role("button", name="确定")
            if confirm.count() > 0:
                confirm.click()
            page.wait_for_timeout(1500)
        page.get_by_placeholder("账号", exact=True).fill("r212-viewer")
        page.get_by_placeholder("密码", exact=True).fill(viewer_pw)
        page.get_by_role("button", name="登录").click()
        page.wait_for_timeout(2500)
        st = wait_rendered(page)
        menu_el = page.locator(".el-menu.outer-most")
        if menu_el.count() == 0:
            menu_el = page.locator(".el-menu").first
        menu_txt = menu_el.inner_text() if menu_el.count() > 0 else ""
        results["f03_viewer"] = {
            "landing_hash": st["hash"],
            "menu_has_quality_ledger": "质量台账" in menu_txt,
            "menu_has_ai_sql": "AI辅助编写" in menu_txt or "AI 写 SQL" in menu_txt,
            "menu_has_ops": any(k in menu_txt for k in ("运维任务", "受控SQL", "操作审计")),
            "menu_text_head": menu_txt.replace("\n", "|")[:200],
        }
        page.screenshot(path=str(SHOT / "12_viewer_菜单可见性.png"))
        # 值域页：viewer 的确认按钮应隐藏（v-perms=value_domain.confirm）
        try:
            page.evaluate("r => { location.hash = '#' + r; }", "/value-domains")
            st = wait_rendered(page)
            page.wait_for_timeout(1200)
            dlg_btn = page.locator("button:has-text('确认值域')")
            row_btns = page.locator("button:has-text('确认')")
            results["f03_viewer"]["value_domain_confirm_buttons"] = {
                "dialog_buttons": dlg_btn.count(), "confirm_like_buttons": row_btns.count(),
                "page_reachable": st["mainLen"] > 30,
            }
            page.screenshot(path=str(SHOT / "13_viewer_值域页_按钮隐藏.png"))
        except Exception as e:  # noqa: BLE001
            results["f03_viewer"]["value_domain_check_error"] = repr(e)[:200]

        # ---- viewer 退出 ----
        avatar = page.locator(".el-dropdown-link", has_text="r212-viewer")
        if avatar.count() == 0:
            avatar = page.locator(".el-dropdown-link").first
        if avatar.count() > 0:
            avatar.first.click(); page.wait_for_timeout(700)
            page.locator(".el-dropdown-menu__item", has_text="退出系统").first.click()
            page.wait_for_timeout(700)
            confirm = page.locator(".el-message-box").get_by_role("button", name="确定")
            if confirm.count() > 0:
                confirm.click()
            page.wait_for_timeout(1500)
        st = sample(page)
        results["logout_back_to_login"] = ("login" in st["hash"]
                                          or page.get_by_placeholder("账号", exact=True).count() > 0)
        page.screenshot(path=str(SHOT / "14_viewer退出_回登录页.png"))

        browser.close()

    out = HERE / "browser" / "r212_s3_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    passed = sum(1 for x in results["pages"] if x["pass"])
    print(f"pages: {passed}/{len(results['pages'])} pass; console_errors={len(results['console_errors'])}")
    print(f"results -> {out}")


if __name__ == "__main__":
    main()
