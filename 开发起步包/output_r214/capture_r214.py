# -*- coding: utf-8 -*-
"""E-A1 复拍脚本（214 §7.2）：真实 Chrome（channel=chrome）视口 1600x900。

用法（密码经 argv 传入，不写入任何文件）：
  backend/.venv/Scripts/python.exe capture_r214.py <一次性密码> <评审新密码>

产出：
  screenshots/*.png        逐页截图（序号_页签名_页面标题）
  e_a1_results.json        逐页判定 + DEF-02 三轮切换结论
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8898"
HERE = Path(__file__).parent
SHOT_DIR = HERE / "screenshots"
SHOT_DIR.mkdir(exist_ok=True)

# (序号, 路由, 菜单/页签名, 侧边栏分组) —— 分组用于菜单点击导航
PAGES = [
    ("00", "/login", "登录页", None),
    ("01", "/welcome", "运行总览", "工作台"),
    ("02", "/workbench", "日常工作台", "工作台"),
    ("03", "/asset/systems", "系统与数据资源", "资产目录"),
    ("04", "/datasets", "数据集目录", "资产目录"),
    ("05", "/asset/tables", "表与字段", "资产目录"),
    ("06", "/asset/graph", "关系图谱", "资产目录"),
    ("07", "/asset/relation-review", "关系复核", "标准与关系"),
    ("08", "/asset/relation-recipes", "关系配方", "标准与关系"),
    ("09", "/value-domains", "值域知识库", "标准与关系"),
    ("10", "/dict/medical", "诊断手术字典", "标准与关系"),
    ("11", "/metadata/changes", "元数据变更", "资产目录"),
    ("12", "/asset/ai-sql", "AI辅助编写", "查询与指标"),
    ("13", "/identity/accounts", "业务系统账号", "人员与权限"),
    ("14", "/quality/issues", "质量台账", "质量治理"),
    ("15", "/ops/runs", "运维任务", "平台运维"),
    ("16", "/ops/sql-workbench", "受控SQL运维", "平台运维"),
    ("17", "/ops/audit", "操作审计", "平台运维"),
]

STATE_JS = """
() => {
  const main = document.querySelector('.app-main');
  const skel = document.querySelector('.app-main .route-skeleton');
  const h1 = document.querySelector('.app-main .re-page-header h1');
  const tags = [...document.querySelectorAll('.scroll-item.is-active')]
    .map(e => (e.textContent || '').trim());
  const crumb = [...document.querySelectorAll('.el-breadcrumb__item')]
    .map(e => (e.textContent || '').trim()).join('/');
  const txt = main ? (main.innerText || '').replace(/\\s+/g, ' ').trim() : '';
  return {
    hash: location.hash,
    mainLen: txt.length,
    head: txt.slice(0, 120),
    skeleton: !!skel,
    h1: h1 ? h1.textContent.trim() : null,
    activeTags: tags,
    crumb
  };
}
"""


def sample(page):
    return page.evaluate(STATE_JS)


def wait_rendered(page, timeout_ms=15000, min_len=30):
    """等正文渲染完成：骨架消失且内容区有实文。返回最终采样。"""
    deadline = time.time() + timeout_ms / 1000
    st = sample(page)
    while time.time() < deadline:
        st = sample(page)
        if not st["skeleton"] and st["mainLen"] > min_len:
            return st
        page.wait_for_timeout(300)
    return st


def nav_hash(page, route):
    page.evaluate("r => { location.hash = '#' + r; }", route)


def nav_menu(page, item_title, group_title):
    item = page.locator(".el-menu-item", has_text=item_title).first
    # 子项在折叠分组下仍存在于 DOM（隐藏态），需先展开所在分组
    if item.count() == 0 or not item.is_visible():
        grp = page.locator(".el-sub-menu__title", has_text=group_title).first
        if grp.count() == 0 or not grp.is_visible():
            raise RuntimeError(f"菜单组不可见: {group_title}")
        grp.click()
        page.wait_for_timeout(700)
    if item.count() == 0 or not item.is_visible():
        raise RuntimeError(f"展开后菜单项仍不可见: {item_title}")
    item.click()


def judge(st, expected_title):
    """通过判定：激活页签=预期页 且 内容非空白。（页签与正文同页另看 h1/head 采样）
    /welcome 的多页签固定叫「首页」，按同页特例接受。"""
    accept = {expected_title} | ({"首页"} if expected_title == "运行总览" else set())
    tag_ok = any(t in accept for t in st["activeTags"])
    content_ok = (not st["skeleton"]) and st["mainLen"] > 30
    return bool(tag_ok and content_ok), {
        "expected": expected_title,
        "hash": st["hash"],
        "activeTags": st["activeTags"],
        "h1": st["h1"],
        "crumb": st["crumb"],
        "mainLen": st["mainLen"],
        "head": st["head"],
        "skeleton": st["skeleton"],
    }


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:40]


def main():
    one_time_pw = sys.argv[1]
    review_pw = sys.argv[2]
    results = {"pages": [], "def02": {}, "console_errors": []}

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
            mode = "chrome-headed"
        except Exception:
            browser = p.chromium.launch(channel="chrome", headless=True)
            mode = "chrome-headless"
        results["browser_mode"] = mode
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on("pageerror", lambda e: results["console_errors"].append(f"pageerror: {e}"))
        page.on(
            "console",
            lambda m: results["console_errors"].append(f"console.{m.type}: {m.text[:200]}")
            if m.type == "error"
            else None,
        )

        # ---- 登录页截图（T01 复核：无 // 注释文本） ----
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)
        st = sample(page)
        page.screenshot(path=str(SHOT_DIR / "00_登录页_登录.png"), full_page=False)
        login_txt = (page.locator("body").inner_text() or "")
        results["pages"].append({
            "idx": "00", "route": "/login", "title": "登录页",
            "pass": "//" not in login_txt,
            "evidence": {"hasBareComment": "//" in login_txt},
        })

        # ---- 登录（一次性密码）→ 强制改密 ----
        page.get_by_placeholder("账号", exact=True).fill("platform-admin")
        page.get_by_placeholder("密码", exact=True).fill(one_time_pw)
        page.get_by_role("button", name="登录").click()
        page.wait_for_timeout(1500)
        # 首次登录修改密码对话框（以“原密码”输入框存在为准）
        old_pw_box = page.get_by_placeholder("默认可用登录密码")
        for _ in range(10):
            if old_pw_box.count() > 0 and old_pw_box.is_visible():
                break
            page.wait_for_timeout(500)
        if old_pw_box.count() > 0:
            old_pw_box.fill(one_time_pw)
            page.get_by_placeholder("8-18位，数字/字母/符号任意两类").fill(review_pw)
            # 确认新密码框无 placeholder，按表单项 label 定位
            confirm_item = page.locator(".el-dialog .el-form-item", has_text="确认新密码")
            confirm_item.locator("input").fill(review_pw)
            dlg_confirm = page.get_by_role("button", name="确认修改")
            dlg_confirm.first.click()
            # 等对话框消失（改密成功后自动登出）
            for _ in range(20):
                if old_pw_box.count() == 0 or not old_pw_box.is_visible():
                    break
                page.wait_for_timeout(500)
        # 用新密码重新登录
        page.get_by_placeholder("账号", exact=True).fill("platform-admin")
        page.get_by_placeholder("密码", exact=True).fill(review_pw)
        page.get_by_role("button", name="登录").click()
        page.wait_for_timeout(2500)
        st = wait_rendered(page)
        results["login_landing"] = {"hash": st["hash"], "head": st["head"][:80]}
        page.screenshot(path=str(SHOT_DIR / "00b_改密后重登_落地页.png"))

        # ---- 逐页复拍（hash 直达 + 等正文渲染完成） ----
        for idx, route, title, group in PAGES[1:]:
            nav_hash(page, route)
            st = wait_rendered(page)
            ok, ev = judge(st, title)
            results["pages"].append({
                "idx": idx, "route": route, "title": title, "pass": ok, "evidence": ev,
            })
            body_title = ev["h1"] or (ev["activeTags"][0] if ev["activeTags"] else "空")
            page.screenshot(path=str(SHOT_DIR / f"{idx}_{safe_name(title)}_{safe_name(body_title)}.png"))

        # ---- 退出再登录（头像下拉 → 退出系统） ----
        avatar = page.locator(".el-dropdown-link", has_text="platform-admin")
        if avatar.count() > 0:
            avatar.first.click()
            page.wait_for_timeout(800)
            page.locator(".el-dropdown-menu__item", has_text="退出系统").first.click()
            page.wait_for_timeout(800)
            confirm = page.locator(".el-message-box").get_by_role("button", name="确定")
            if confirm.count() > 0:
                confirm.click()
            page.wait_for_timeout(1500)
            st = sample(page)
            logged_out = "login" in st["hash"] or page.get_by_placeholder("账号", exact=True).count() > 0
            page.get_by_placeholder("账号", exact=True).fill("platform-admin")
            page.get_by_placeholder("密码", exact=True).fill(review_pw)
            page.get_by_role("button", name="登录").click()
            st2 = wait_rendered(page)
            page.screenshot(path=str(SHOT_DIR / "18_退出重登_落地页.png"))
            results["relogin"] = {
                "loggedOut": bool(logged_out),
                "landingHash": st2["hash"],
                "landingHead": st2["head"][:80],
                "pass": bool(logged_out and st2["mainLen"] > 30),
            }

        # ---- DEF-02 三轮切换测试 ----
        switch_routes = [
            ("/welcome", "运行总览"), ("/quality/issues", "质量台账"),
            ("/value-domains", "值域知识库"), ("/asset/tables", "表与字段"),
            ("/dict/medical", "诊断手术字典"), ("/metadata/changes", "元数据变更"),
            ("/asset/relation-recipes", "关系配方"), ("/ops/audit", "操作审计"),
            ("/workbench", "日常工作台"), ("/asset/graph", "关系图谱"),
        ]

        # 轮1：逐页 hash 切换 + 每次等1.2s 采样（原缺陷：URL/面包屑变而主视图不变）
        r1 = []
        for route, title in switch_routes:
            nav_hash(page, route)
            page.wait_for_timeout(1200)
            st = sample(page)
            # 主视图是否为目标页：正文头部含页面特征或激活页签一致且内容非旧页
            stale = st["mainLen"] > 30 and (
                not ({title} | ({"首页"} if title == "运行总览" else set())
                     & set(st["activeTags"]))
            )
            r1.append({"route": route, "title": title, "hash": st["hash"],
                       "activeTags": st["activeTags"], "head": st["head"][:60],
                       "suspicious": bool(stale)})
        results["def02"]["round1_hash_stepwise"] = r1

        # 轮2：连续快速 hash 切换（300ms 间隔，不等待渲染），结束后核对末页
        for route, _ in switch_routes:
            nav_hash(page, route)
            page.wait_for_timeout(300)
        page.wait_for_timeout(3000)
        st = sample(page)
        last = switch_routes[-1]
        results["def02"]["round2_rapid"] = {
            "finalRoute": last[0], "hash": st["hash"],
            "activeTags": st["activeTags"], "head": st["head"][:80],
            "mainLen": st["mainLen"],
            "final_ok": any(t == last[1] for t in st["activeTags"]) and st["mainLen"] > 30,
        }

        # 轮3：真实菜单点击逐页切换（最接近原始报告触发方式）
        r3 = []
        menu_plan = [
            ("质量治理", "质量台账"), ("平台运维", "操作审计"),
            ("标准与关系", "值域知识库"), ("资产目录", "表与字段"),
            ("工作台", "运行总览"), ("查询与指标", "AI辅助编写"),
            ("标准与关系", "诊断手术字典"), ("工作台", "日常工作台"),
        ]
        for group, item in menu_plan:
            try:
                nav_menu(page, item, group)
                page.wait_for_timeout(1500)
                st = sample(page)
                ok = any(t == item for t in st["activeTags"]) and st["mainLen"] > 30
                r3.append({"menu": item, "hash": st["hash"], "ok": bool(ok),
                           "head": st["head"][:60]})
                if not ok:
                    # 复现判定信号：手动刷新后恢复
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    st2 = wait_rendered(page)
                    r3[-1]["after_reload_ok"] = bool(
                        any(t == item for t in st2["activeTags"]) and st2["mainLen"] > 30)
                    r3[-1]["after_reload_hash"] = st2["hash"]
                    # 恢复导航继续
            except Exception as e:
                r3.append({"menu": item, "error": str(e)[:120]})
        results["def02"]["round3_menu_clicks"] = r3

        suspicious = [x for x in r1 if x.get("suspicious")]
        reproduced = bool(suspicious) or any(
            x.get("ok") is False and x.get("after_reload_ok") for x in r3)
        results["def02"]["conclusion"] = (
            "REPRODUCED" if reproduced else "NOT_REPRODUCED")

        browser.close()

    (HERE / "e_a1_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pass = sum(1 for x in results["pages"] if x["pass"])
    print(f"pages_pass={n_pass}/{len(results['pages'])} def02={results['def02']['conclusion']}")


if __name__ == "__main__":
    main()
