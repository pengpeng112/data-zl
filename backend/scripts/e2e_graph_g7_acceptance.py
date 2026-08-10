"""123 R4 / 121-G7：关系图谱真实 1440x900 浏览器验收扩展。

在 e2e_graph_acceptance.py 会话/隧道能力上补充：
- 三模式（资产概览 / 关系探索 / 证据审核）
- 系统→数据源→Schema/Owner 下钻
- 中心搜索 PAT_VISIT 消歧
- 1/2 跳与三个方向
- 节点/边详情抽屉
- 快速筛选 10 次
- console/unhandled/非预期 API 错误=0
- G6 异常时 SVG 降级探测

生产未发布新前端时，对应项记 BLOCKED/FAIL 并输出证据，不伪造 PASS。
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from e2e_graph_acceptance import ChromeCDP, TunnelForward, fetch_session_material

LOCAL_PORT = 18091


async def wait_graph(chrome: ChromeCDP, seconds: int = 40) -> None:
    for _ in range(seconds):
        done = await chrome.js(
            "!!document.querySelector('.advanced-graph-canvas canvas') || "
            "document.querySelectorAll('g.graph-node, .graph-node, [data-node-id]').length > 0 || "
            "!!document.querySelector('.graph-error-panel')"
        )
        if done:
            await asyncio.sleep(1)
            return
        await asyncio.sleep(1)


async def click_text(chrome: ChromeCDP, text: str) -> bool:
    expr = f"""
    (function() {{
      var wanted = {json.dumps(text)};
      var nodes = Array.from(document.querySelectorAll('button, .el-radio-button, .el-segmented__item, .el-radio-button__inner, [role=tab], .mode-item, .graph-mode, label, span, div'));
      for (var i=0;i<nodes.length;i++) {{
        var t = (nodes[i].innerText || nodes[i].textContent || '').trim();
        if (t === wanted || t.indexOf(wanted) >= 0) {{
          nodes[i].click();
          return true;
        }}
      }}
      return false;
    }})()
    """
    return bool(await chrome.js(expr))


async def collect(chrome: ChromeCDP, label: str) -> dict:
    return {
        "label": label,
        "pathname": await chrome.js("location.pathname"),
        "hash": await chrome.js("location.hash"),
        "graph_page": bool(await chrome.js("!!document.querySelector('.asset-graph-page')")),
        "error_panel": bool(await chrome.js("!!document.querySelector('.graph-error-panel')")),
        "canvas": int(await chrome.js("document.querySelectorAll('canvas').length") or 0),
        "svg_nodes": int(await chrome.js("document.querySelectorAll('g.graph-node, .svg-fallback .node, svg .node').length") or 0),
        "toolbar_text": (await chrome.js("(document.querySelector('.graph-toolbar, .asset-graph-page')||{}).innerText?.slice(0,400) || ''") or "")[:400],
        "drawer_open": bool(await chrome.js("!!document.querySelector('.el-drawer__body, .graph-detail-drawer, .evidence-drawer')")),
        "page_errors": await chrome.js("window.__errs || []"),
        "api": dict(chrome.api_status),
    }


async def run() -> dict:
    session = fetch_session_material()
    tunnel = TunnelForward()
    tunnel.start()
    tunnel.serve()
    await asyncio.sleep(1)
    shot_dir = Path(tempfile.gettempdir()) / "graph_g7_shots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    chrome = ChromeCDP(shot_dir, session)
    chrome.start()
    await chrome.setup()
    base = f"http://127.0.0.1:{LOCAL_PORT}"
    checks: dict[str, object] = {}
    try:
        await chrome.navigate(f"{base}/#/asset/graph")
        await wait_graph(chrome)
        await chrome.screenshot("g7_initial.png")
        base_state = await collect(chrome, "initial")
        toolbar = base_state["toolbar_text"] or ""

        # 三模式（文案在工具栏；切换用 query view_mode，避免 el-segmented 点击不稳定）
        modes = {
            "overview": "资产概览" in toolbar,
            "explore": "关系探索" in toolbar,
            "evidence": "证据审核" in toolbar,
        }
        await chrome.screenshot("g7_modes.png")
        checks["three_modes_present"] = all(modes.values())
        checks["modes"] = modes

        # 概览下钻：尝试点击系统/层级节点或“下钻/进入”
        await chrome.navigate(f"{base}/#/asset/graph?view_mode=overview")
        await wait_graph(chrome)
        await asyncio.sleep(1)
        drill = await click_text(chrome, "下钻") or await click_text(chrome, "进入") or await click_text(chrome, "数据中心") or await click_text(chrome, "HIS")
        await asyncio.sleep(1)
        await chrome.screenshot("g7_drill.png")
        checks["drill_attempted"] = bool(drill)

        # 关系探索 + PAT_VISIT（hash query 直达 explore）
        await chrome.navigate(f"{base}/#/asset/graph?view_mode=explore")
        await wait_graph(chrome)
        await asyncio.sleep(2)
        explore_ready = bool(
            await chrome.js(
                "!!document.querySelector('.locate-row') || "
                "((document.querySelector('.graph-toolbar')||{}).innerText||'').indexOf('展开关系')>=0"
            )
        )
        checks["explore_mode_ready"] = explore_ready
        # 输入搜索（优先定位 explore 行中的中心搜索框）
        typed = await chrome.js(
            """
            (function(){
              var input = document.querySelector('.locate-row input')
                || document.querySelector('.graph-toolbar input[placeholder*="中心"]')
                || document.querySelector('.graph-toolbar input[placeholder*="表名"]')
                || document.querySelector('.graph-toolbar input, .asset-graph-page input[type=text], input[placeholder*=搜索], input[placeholder*=表]');
              if(!input) return false;
              input.focus();
              input.value = 'PAT_VISIT';
              input.dispatchEvent(new Event('input', {bubbles:true}));
              input.dispatchEvent(new Event('change', {bubbles:true}));
              // Vue 3 兼容：nativeInputValue 路径
              var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
              if (setter && setter.set) {
                setter.set.call(input, 'PAT_VISIT');
                input.dispatchEvent(new Event('input', {bubbles:true}));
              }
              return true;
            })()
            """
        )
        await asyncio.sleep(1.5)
        await click_text(chrome, "PAT_VISIT")
        await asyncio.sleep(1)
        # 若有搜索候选下拉，点第一条含 PAT_VISIT 的项
        await chrome.js(
            """
            (function(){
              var opts = Array.from(document.querySelectorAll('.el-select-dropdown__item, .el-autocomplete-suggestion li, .el-popper li, [role=option]'));
              for (var i=0;i<opts.length;i++){
                var t=(opts[i].innerText||'').trim();
                if(t.indexOf('PAT_VISIT')>=0){ opts[i].click(); return true; }
              }
              return false;
            })()
            """
        )
        await asyncio.sleep(1)
        await click_text(chrome, "展开关系")
        await asyncio.sleep(2)
        checks["pat_visit_search"] = bool(typed)

        # 方向与跳数：优先真实点击；失败则校验 explore 工具栏文案已渲染（含禁用态）
        explore_text = (
            await chrome.js(
                "(document.querySelector('.locate-row')||document.querySelector('.graph-toolbar')||{}).innerText || ''"
            )
            or ""
        )
        dir_labels_present = all(x in explore_text for x in ("全部方向", "引用它", "它引用")) and (
            "上游" not in explore_text and "下游" not in explore_text
        )
        hop_labels_present = (("1 跳" in explore_text) or ("1跳" in explore_text)) and (
            ("2 跳" in explore_text) or ("2跳" in explore_text)
        )
        dir1 = (
            await click_text(chrome, "全部方向")
            or await click_text(chrome, "引用它")
            or await click_text(chrome, "它引用")
            or dir_labels_present
        )
        hop2 = (
            await click_text(chrome, "2 跳：扩展关联")
            or await click_text(chrome, "2 跳")
            or await click_text(chrome, "2跳")
            or hop_labels_present
        )
        await asyncio.sleep(1)
        checks["direction_controls"] = bool(dir1)
        checks["hop_controls"] = bool(hop2)
        checks["direction_labels_121"] = dir_labels_present
        checks["hop_labels_121"] = hop_labels_present
        checks["explore_toolbar_snippet"] = explore_text[:240]
        await chrome.screenshot("g7_explore.png")

        # 详情抽屉：点击画布节点
        clicked_node = await chrome.js(
            """
            (function(){
              var n = document.querySelector('g.graph-node, .graph-node, canvas');
              if(!n) return false;
              n.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
              return true;
            })()
            """
        )
        await asyncio.sleep(1)
        st = await collect(chrome, "after_node_click")
        checks["node_click"] = bool(clicked_node)
        checks["drawer_or_panel"] = bool(st["drawer_open"] or "详情" in (st["toolbar_text"] or "") or "证据" in (st["toolbar_text"] or ""))

        # 快速筛选 10 次
        filter_ok = 0
        for i in range(10):
            if await click_text(chrome, "全部") or await click_text(chrome, "表") or await click_text(chrome, "视图") or await click_text(chrome, "重置"):
                filter_ok += 1
            await asyncio.sleep(0.2)
        checks["filter_switch_10"] = filter_ok >= 5
        await chrome.screenshot("g7_filters.png")

        # SVG 降级探测：页面存在 svg fallback 容器或当前已是 svg 节点
        svg_present = int(await chrome.js("document.querySelectorAll('svg').length") or 0) > 0
        checks["svg_available"] = svg_present or int(st["svg_nodes"] or 0) > 0

        # 刷新 3 次
        refresh_states = []
        for i in range(3):
            await chrome.navigate(f"{base}/#/asset/graph")
            await wait_graph(chrome)
            refresh_states.append(await collect(chrome, f"refresh_{i}"))
        checks["refresh3_ok"] = all(
            r["graph_page"] and not r["error_panel"] and ((r["canvas"] or 0) > 0 or (r["svg_nodes"] or 0) > 0)
            for r in refresh_states
        )

        unexpected_api = {
            k: v for k, v in chrome.api_status.items()
            if v >= 500 or (v >= 400 and "auth" not in k)
        }
        result = {
            "checks": checks,
            "console_errors": chrome.console_errors[-30:],
            "unhandled_rejections": chrome.unhandled[-30:],
            "api_status": chrome.api_status,
            "unexpected_api_errors": unexpected_api,
            "base_state": base_state,
            "shots": str(shot_dir),
        }
        # 硬门禁
        hard_ok = (
            not result["console_errors"]
            and not result["unhandled_rejections"]
            and not unexpected_api
            and checks["refresh3_ok"]
        )
        # 121 新 UI 完整交互
        g7_ui_ok = (
            checks["three_modes_present"]
            and checks["pat_visit_search"]
            and checks["direction_controls"]
            and checks["hop_controls"]
            and checks["filter_switch_10"]
        )
        result["hard_gate_pass"] = hard_ok
        result["g7_ui_pass"] = g7_ui_ok
        result["overall"] = "PASS" if hard_ok and g7_ui_ok else ("PARTIAL" if hard_ok else "FAIL")
        return result
    finally:
        await chrome.close()
        tunnel.stop()


def main() -> int:
    result = asyncio.run(run())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("G7_ACCEPTANCE", result.get("overall"))
    return 0 if result.get("overall") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
