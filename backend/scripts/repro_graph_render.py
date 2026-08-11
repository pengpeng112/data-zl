"""119 号 S3：生产脱敏响应 + 最小复现页在真实 Chrome 中的渲染验证。

复用 e2e_graph_browser.py 的 CDP 驱动方式，但不需要 SSH 隧道和登录：
- 本地静态服务 frontend/repro/dist；
- 分别用 ?engine=g6 和 ?engine=svg 加载；
- 收集 console error、unhandled rejection、canvas/svg 元素计数、截图。

用法：
    .\\.venv\\Scripts\\python.exe scripts/repro_graph_render.py
"""
from __future__ import annotations

import asyncio
import base64
import functools
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import websockets

REPRO_DIST = Path(__file__).resolve().parents[2] / "frontend" / "repro" / "dist"
HTTP_PORT = 18099
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


class StaticServer:
    def __init__(self, directory: Path, port: int) -> None:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()


class ChromeCDP:
    def __init__(self, shot_dir: Path) -> None:
        self.shot_dir = shot_dir
        self.debug_port = 9224
        self.user_data = tempfile.mkdtemp(prefix="chrome-repro-")
        self.proc = None
        self.ws = None
        self.msg_id = 0
        self.console_errors: list[str] = []
        self.unhandled: list[str] = []
        self._listener: asyncio.Task | None = None

    def start(self) -> None:
        chrome = next((c for c in CHROME_CANDIDATES if os.path.exists(c)), None)
        if not chrome:
            raise RuntimeError("no chrome/edge found")
        self.proc = subprocess.Popen(
            [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--disable-dev-shm-usage", f"--remote-debugging-port={self.debug_port}",
                f"--user-data-dir={self.user_data}", "--window-size=1440,900",
                "--disable-background-networking", "--disable-component-update",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.debug_port}/json/version", timeout=2):
                    break
            except Exception:
                time.sleep(0.5)

    def _open_target(self) -> str:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.debug_port}/json/new?about:blank", method="PUT",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())["webSocketDebuggerUrl"]

    async def _send(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        self.msg_id += 1
        mid = self.msg_id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
            if resp.get("id") == mid:
                if "error" in resp:
                    raise RuntimeError(f"CDP {method}: {resp['error']}")
                return resp.get("result", {})

    async def setup(self) -> None:
        self.ws = await websockets.connect(self._open_target(), max_size=128 * 1024 * 1024)
        await self._send("Page.enable")
        await self._send("Runtime.enable")
        await self._send("Log.enable")
        # Error 对象经 CDP 序列化会丢失堆栈；在页面脚本加载前挂钩 console.error 保留完整堆栈。
        await self._send("Page.addScriptToEvaluateOnNewDocument", {"source": """
window.__errs = [];
(function () {
  var orig = console.error;
  console.error = function () {
    var parts = [];
    for (var i = 0; i < arguments.length; i++) {
      var a = arguments[i];
      parts.push(a && a.stack ? a.stack : String(a));
    }
    window.__errs.push(parts.join(' | '));
    return orig.apply(console, arguments);
  };
  window.addEventListener('unhandledrejection', function (e) {
    window.__errs.push('unhandledrejection: ' + (e.reason && e.reason.stack ? e.reason.stack : String(e.reason)));
  });
  window.addEventListener('error', function (e) {
    window.__errs.push('error: ' + (e.error && e.error.stack ? e.error.stack : e.message));
  });
})();
"""})
        self._listener = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            while True:
                msg = json.loads(await self.ws.recv())
                method = msg.get("method", "")
                if method == "Runtime.exceptionThrown":
                    d = msg.get("params", {}).get("exceptionDetails", {})
                    desc = d.get("exception", {}).get("description", "") or ""
                    self.unhandled.append((d.get("text", "") + " " + desc).strip())
                elif method == "Runtime.consoleAPICalled":
                    p = msg.get("params", {})
                    if p.get("type") == "error":
                        text = " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))
                        self.console_errors.append(text)
                elif method == "Log.entryAdded":
                    e = msg.get("params", {}).get("entry", {})
                    if e.get("level") == "error":
                        self.console_errors.append(e.get("text", ""))
        except Exception:
            pass

    async def navigate(self, url: str) -> None:
        await self._send("Page.navigate", {"url": url})
        for _ in range(40):
            await asyncio.sleep(0.5)
            res = await self._send("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
            if res.get("result", {}).get("value") == "complete":
                break

    async def js(self, expr: str) -> object:
        res = await self._send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if res.get("exceptionDetails"):
            return None
        return res.get("result", {}).get("value")

    async def screenshot(self, name: str) -> None:
        res = await self._send("Page.captureScreenshot", {"format": "png"})
        (self.shot_dir / name).write_bytes(base64.b64decode(res["data"]))

    async def close(self) -> None:
        if self._listener:
            self._listener.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.proc:
            self.proc.terminate()
        shutil.rmtree(self.user_data, ignore_errors=True)


async def check_engine(chrome: ChromeCDP, engine: str, wait_s: float) -> dict:
    chrome.console_errors.clear()
    chrome.unhandled.clear()
    await chrome.navigate(f"http://127.0.0.1:{HTTP_PORT}/index.html?engine={engine}")
    await asyncio.sleep(wait_s)
    result = {
        "engine": engine,
        "repro_state": await chrome.js("window.__repro"),
        "canvas_count": await chrome.js("document.querySelectorAll('canvas').length"),
        "svg_nodes": await chrome.js("document.querySelectorAll('g.graph-node').length"),
        "svg_edges": await chrome.js("document.querySelectorAll('path.graph-edge').length"),
        "g6_dom_nodes": await chrome.js("document.querySelectorAll('.g6-node, [data-element-type=node]').length"),
        "page_errors": await chrome.js("window.__errs || []"),
        "console_errors": chrome.console_errors.copy(),
        "unhandled_rejections": chrome.unhandled.copy(),
    }
    await chrome.screenshot(f"repro_{engine}.png")
    return result


async def main() -> dict:
    shot_dir = Path(tempfile.gettempdir()) / "graph_repro_shots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    server = StaticServer(REPRO_DIST, HTTP_PORT)
    server.start()
    chrome = ChromeCDP(shot_dir)
    chrome.start()
    await chrome.setup()
    try:
        results = []
        results.append(await check_engine(chrome, "g6", 30.0))
        results.append(await check_engine(chrome, "svg", 4.0))
        return {"shots": str(shot_dir), "results": results}
    finally:
        await chrome.close()
        server.stop()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main()), ensure_ascii=False, indent=2))
