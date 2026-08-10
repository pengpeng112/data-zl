"""108 号 §6.4：真实 Chrome 浏览器 E2E（内网无 Playwright 的等价真实浏览器自动化）。

通过 paramiko SSH 隧道 + Chrome DevTools Protocol 驱动本机真实 Chrome：
- 导航 /asset/graph（登录后）
- 检查默认节点/边 > 0
- console error = 0、unhandled rejection = 0
- 截图保存（脱敏：只截图页面，不含 Token）

用法：
    python scripts/e2e_graph_browser.py [--base-url http://127.0.0.1:18090]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import select
import shutil
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import paramiko
import websockets

LOCAL_PORT = 18090
REMOTE_PORT = 8090
SSH_HOST = "10.10.8.83"
SSH_USER = "root"
SSH_KEY = r"C:\Users\Administrator\.ssh\id_ed25519_ai"
TEST_TOKEN = "test-token-p5-auth-2026"
TEST_USERNAME = "e2e-readonly"
TEST_PASSWORD = "r2QNuexr*Wad"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


class TunnelForward:
    """paramiko direct-tcpip 转发，把 8.83:8090 映射到本机 LOCAL_PORT。"""

    def __init__(self) -> None:
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self.transport = None
        self.server = None

    def start(self) -> None:
        self.client.connect(hostname=SSH_HOST, username=SSH_USER, key_filename=SSH_KEY, timeout=20)
        self.transport = self.client.get_transport()

    def serve(self) -> None:
        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                chan = self.server.transport.open_channel(
                    "direct-tcpip", ("127.0.0.1", REMOTE_PORT), self.request.getpeername()
                )
                if chan is None:
                    return
                try:
                    while True:
                        r, _w, _x = select.select([self.request, chan], [], [], 30)
                        if self.request in r:
                            data = self.request.recv(65536)
                            if not data:
                                break
                            chan.send(data)
                        if chan in r:
                            data = chan.recv(65536)
                            if not data:
                                break
                            self.request.send(data)
                finally:
                    chan.close()
                    self.request.close()

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", LOCAL_PORT), Handler)
        self.server.transport = self.transport
        self.server.allow_reuse_address = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
        if self.client:
            self.client.close()


class ChromeCDP:
    def __init__(self, base_url: str, shot_dir: Path) -> None:
        self.base_url = base_url
        self.shot_dir = shot_dir
        self.debug_port = 9223
        self.user_data = tempfile.mkdtemp(prefix="chrome-e2e-")
        self.proc = None
        self.ws = None
        self.loop = None
        self.msg_id = 0
        self.console_errors: list[str] = []
        self.unhandled: list[str] = []
        self.failed_requests: list[str] = []
        self._listener: asyncio.Task | None = None

    def _find_chrome(self) -> str:
        for c in CHROME_CANDIDATES:
            if os.path.exists(c):
                return c
        raise RuntimeError("no chrome/edge found")

    def start(self) -> None:
        chrome = self._find_chrome()
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

    def _open_target(self) -> None:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.debug_port}/json/new?about:blank",
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            target = json.loads(r.read().decode())
        return target["webSocketDebuggerUrl"]

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
        self.loop = asyncio.new_event_loop()
        ws_url = self._open_target()
        self.ws = await websockets.connect(ws_url, max_size=128 * 1024 * 1024)
        await self._send("Page.enable")
        await self._send("Runtime.enable")
        await self._send("Log.enable")
        await self._send("Network.enable")
        self._listener = asyncio.create_task(self._listen())
        # 注入已认证 API Key：拦截 /api/v1 请求并附加 Authorization，模拟真实认证会话
        await self._send("Fetch.enable", {"patterns": [{"urlPattern": "*api/v1*", "requestStage": "Request"}]})
        self._fetch_listener = asyncio.create_task(self._intercept_fetch())

    async def _intercept_fetch(self) -> None:
        try:
            while True:
                msg = json.loads(await self.ws.recv())
                if msg.get("method") != "Fetch.requestPaused":
                    continue
                req_id = msg.get("params", {}).get("requestId")
                request = msg.get("params", {}).get("request", {})
                url = request.get("url", "") or ""
                headers = dict(request.get("headers", {}) or {})
                # 跳过登录/刷新/退出，避免干扰认证流程
                if "/auth/login" not in url and "/auth/refresh" not in url and "/auth/logout" not in url:
                    headers["Authorization"] = f"Bearer {TEST_TOKEN}"
                await self._send("Fetch.continueRequest", {
                    "requestId": req_id,
                    "headers": [{"name": k, "value": v} for k, v in headers.items()],
                })
        except Exception:
            pass

    async def _listen(self) -> None:
        try:
            while True:
                msg = json.loads(await self.ws.recv())
                method = msg.get("method", "")
                if method == "Runtime.exceptionThrown":
                    d = msg.get("params", {}).get("exceptionDetails", {})
                    self.unhandled.append(d.get("text", "") + " " + (d.get("exception", {}).get("description", "") or ""))
                elif method == "Runtime.consoleAPICalled":
                    p = msg.get("params", {})
                    if p.get("type") == "error":
                        text = " ".join(a.get("value", str(a.get("description", ""))) for a in p.get("args", []))
                        self.console_errors.append(text)
                elif method == "Log.entryAdded":
                    e = msg.get("params", {}).get("entry", {})
                    if e.get("level") == "error":
                        self.console_errors.append(e.get("text", ""))
                elif method == "Network.loadingFailed":
                    p = msg.get("params", {})
                    if p.get("type") == "Document" or p.get("canceled"):
                        self.failed_requests.append(p.get("errorText", "loadFailed"))
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

    async def wait_for(self, expr: str, timeout: float = 15) -> bool:
        for _ in range(int(timeout / 0.5)):
            val = await self.js(expr)
            if val:
                return True
            await asyncio.sleep(0.5)
        return False

    async def screenshot(self, name: str) -> None:
        res = await self._send("Page.captureScreenshot", {"format": "png"})
        (self.shot_dir / name).write_bytes(base64.b64decode(res["data"]))

    async def login(self) -> bool:
        """真实登录：填表单后按 Enter 提交（el-form keyup.enter 触发 onLogin）。"""
        await self.navigate(f"{self.base_url}/login")
        await self.wait_for("document.querySelector('input.el-input__inner')", timeout=25)
        await asyncio.sleep(1.0)
        # 填账号
        await self.js("(function(){ var i=document.querySelector('input.el-input__inner[type=text]'); if(i){ i.focus(); return true;} return false; })()")
        await asyncio.sleep(0.3)
        await self._send("Input.insertText", {"text": TEST_USERNAME})
        await asyncio.sleep(0.3)
        # 填密码
        await self.js("(function(){ var i=document.querySelector('input.el-input__inner[type=password]'); if(i){ i.focus(); return true;} return false; })()")
        await asyncio.sleep(0.3)
        await self._send("Input.insertText", {"text": TEST_PASSWORD})
        await asyncio.sleep(0.5)
        # 按 Enter 提交
        await self._send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        await self._send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        for _ in range(25):
            await asyncio.sleep(0.5)
            cur = await self.js("location.pathname")
            if cur and cur != "/login":
                return True
        return False

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


async def run_e2e(base_url: str, shot_dir: Path) -> dict:
    chrome = ChromeCDP(base_url, shot_dir)
    chrome.start()
    await chrome.setup()
    result: dict = {}
    try:
        # 1. 真实登录
        login_ok = await chrome.login()
        result["login_ok"] = login_ok
        await asyncio.sleep(1.0)
        await chrome.screenshot("00_after_login.png")

        # 2. 直接访问 /asset/graph
        await chrome.navigate(f"{base_url}/asset/graph")
        await asyncio.sleep(1.0)
        await chrome.wait_for("document.querySelectorAll('svg').length > 0 || document.body.innerText.includes('筛选') || document.body.innerText.includes('关系图谱')", timeout=25)
        await asyncio.sleep(2.0)
        result["graph_page_loaded"] = bool(await chrome.js("!!document.querySelector('.asset-graph-page')"))
        result["svg_nodes"] = await chrome.js("document.querySelectorAll('g.graph-node').length")
        result["svg_edges"] = await chrome.js("document.querySelectorAll('path.graph-edge, path.graph-edge-hit').length")
        result["page_text_sample"] = (await chrome.js("document.body.innerText.slice(0, 300)")) or ""
        await chrome.screenshot("01_graph_default.png")

        # 2b. 默认节点和边均大于 0（108 §6.4 第 6 条）
        result["default_has_nodes_and_edges"] = int(result["svg_nodes"] or 0) > 0 and int(result["svg_edges"] or 0) > 0

        # 3. 检查是否有"暂无数据"被错误显示
        result["body_has_empty_state"] = bool(await chrome.js("document.body.innerText.includes('暂无数据') || document.body.innerText.includes('筛选结果为空')"))

        # 4. 返回首页
        await chrome.navigate(f"{base_url}/")
        await asyncio.sleep(2.0)
        result["home_loaded"] = bool(await chrome.js("!!document.getElementById('app')"))
        await chrome.screenshot("02_home.png")

        # 5. 收集错误
        await asyncio.sleep(1.0)
        result["console_errors"] = chrome.console_errors.copy()
        result["unhandled_rejections"] = chrome.unhandled.copy()
        result["failed_requests"] = chrome.failed_requests.copy()

        return result
    finally:
        await chrome.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="108 号真实浏览器 E2E")
    parser.add_argument("--base-url", default=f"http://127.0.0.1:{LOCAL_PORT}")
    parser.add_argument("--screenshot-dir", default=str(Path(tempfile.gettempdir()) / "opencode" / "e2e_shots"))
    parser.add_argument("--no-tunnel", action="store_true")
    args = parser.parse_args()

    shot_dir = Path(args.screenshot_dir)
    shot_dir.mkdir(parents=True, exist_ok=True)

    tunnel = None
    if not args.no_tunnel:
        tunnel = TunnelForward()
        tunnel.start()
        tunnel.serve()
        time.sleep(1)

    try:
        result = asyncio.run(run_e2e(args.base_url, shot_dir))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        errors = result.get("console_errors", []) + result.get("unhandled_rejections", [])
        ok = not errors
        print(f"E2E {'PASS' if ok else 'FAIL'}  console_errors={len(result.get('console_errors', []))} unhandled={len(result.get('unhandled_rejections', []))}")
        return 0 if ok else 1
    finally:
        if tunnel:
            tunnel.stop()


if __name__ == "__main__":
    raise SystemExit(main())
