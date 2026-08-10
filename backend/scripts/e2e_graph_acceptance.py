"""119 号 S4：生产关系图谱真实浏览器验收门禁。

链路：本机 Chrome(headless=new) → SSH 隧道 → http://10.10.8.83 生产前端/API。
会话材料由服务器容器内 mint_e2e_session.py 铸造（短期 JWT，仅存在于进程内存，
不打印、不落盘）；/api/v1/auth/refresh 由 CDP 履约铸造材料，其余请求直达生产。

验收项（对应 119-S4）：
- 已认证进入 /asset/graph，未被重定向 /login；
- 实际加载的图谱 chunk 名称；
- 默认视图 G6 canvas 渲染成功、无 render-error、无错误面板；
- /api/v1/graph/options|graph|diagnostics 全部 200；
- 连续刷新 3 次无 Edge already exists / split 类错误；
- console error=0、unhandled rejection=0；
- 截图留证。

用法：
    .\\.venv\\Scripts\\python.exe scripts/e2e_graph_acceptance.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import select
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import paramiko
import websockets

LOCAL_PORT = 18091
REMOTE_PORT = 80
SSH_HOST = "10.10.8.83"
SSH_USER = "root"
SSH_KEY = r"C:\Users\Administrator\.ssh\id_ed25519_ai"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def fetch_session_material() -> dict:
    """经 ssh 在容器内铸造会话材料并捕获 stdout（token 只在内存）。"""
    ssh_base = [
        "ssh", "-i", SSH_KEY, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        f"{SSH_USER}@{SSH_HOST}",
    ]
    subprocess.run(
        ssh_base + ["docker cp /tmp/mint_e2e_session.py data-asset-api:/tmp/ 2>/dev/null || true"],
        check=False, capture_output=True,
    )
    src = Path(__file__).resolve().parent / "mint_e2e_session.py"
    subprocess.run(
        ["scp", "-i", SSH_KEY, "-o", "BatchMode=yes", str(src),
         f"{SSH_USER}@{SSH_HOST}:/tmp/mint_e2e_session.py"],
        check=True, capture_output=True,
    )
    proc = subprocess.run(
        ssh_base + ["docker cp /tmp/mint_e2e_session.py data-asset-api:/tmp/ && "
                    "docker exec data-asset-api python /tmp/mint_e2e_session.py; "
                    "rc=$?; rm -f /tmp/mint_e2e_session.py; "
                    "docker exec data-asset-api rm -f /tmp/mint_e2e_session.py; exit $rc"],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        # 诊断只含 stderr；stdout 可能携带 token，绝不打印
        raise RuntimeError(f"会话材料铸造失败 rc={proc.returncode}: {proc.stderr[-300:]}")
    # stdout 只应包含铸造脚本输出的单行 JSON；docker cp 无输出
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
    raise RuntimeError("无法获取会话材料（stdout 无 JSON 行）")


class TunnelForward:
    """paramiko direct-tcpip：本机 LOCAL_PORT → 8.83:80。"""

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
                            try:
                                data = self.request.recv(65536)
                            except (ConnectionResetError, OSError):
                                break
                            if not data:
                                break
                            chan.send(data)
                        if chan in r:
                            try:
                                data = chan.recv(65536)
                            except (ConnectionResetError, OSError):
                                break
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
    def __init__(self, shot_dir: Path, session: dict) -> None:
        self.shot_dir = shot_dir
        self.session = session
        self.debug_port = 9225
        self.user_data = tempfile.mkdtemp(prefix="chrome-acc-")
        self.proc = None
        self.ws = None
        self.msg_id = 0
        self.console_errors: list[str] = []
        self.unhandled: list[str] = []
        self.api_status: dict[str, int] = {}
        self.graph_chunks: set[str] = set()
        self._pending: dict[int, asyncio.Future] = {}
        self._listener: asyncio.Task | None = None
        self.js_requests: list[str] = []
        self.load_failures: list[str] = []

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
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[mid] = fut
        try:
            await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            resp = await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(mid, None)
        if "error" in resp:
            raise RuntimeError(f"CDP {method}: {resp['error']}")
        return resp.get("result", {})

    async def setup(self) -> None:
        self.ws = await websockets.connect(self._open_target(), max_size=128 * 1024 * 1024)
        # 必须先启动分发循环，否则 _send 的应答无人路由
        self._listener = asyncio.create_task(self._dispatch())
        await self._send("Page.enable")
        await self._send("Runtime.enable")
        await self._send("Log.enable")
        await self._send("Network.enable")
        # 会话种子 + 错误挂钩（token 不进种子，只经 refresh 履约进入内存）
        user_info = {
            "accessToken": "",
            "refreshToken": "",
            "expires": self.session["expires"],
            "avatar": "",
            "username": self.session["username"],
            "nickname": self.session["nickname"],
            "roles": self.session["roles"],
            "permissions": self.session["permissions"],
        }
        seed = """
window.__errs = [];
(function () {
  try {
    localStorage.setItem('user-info', %s);
    document.cookie = 'multiple-tabs=true; path=/';
  } catch (e) {}
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
})();
""" % json.dumps(json.dumps(user_info, ensure_ascii=False))
        await self._send("Page.addScriptToEvaluateOnNewDocument", {"source": seed})
        await self._send("Fetch.enable", {"patterns": [{"urlPattern": "*api/v1*", "requestStage": "Request"}]})

    async def _dispatch(self) -> None:
        """单一消息循环：id 应答路由给 _send 的 future，事件分发到处理器。

        拦截处理走独立 task，避免在分发循环里 await _send 造成死锁。
        """
        try:
            while True:
                msg = json.loads(await self.ws.recv())
                if "id" in msg:
                    fut = self._pending.get(msg["id"])
                    if fut and not fut.done():
                        fut.set_result(msg)
                    continue
                method = msg.get("method", "")
                if method == "Fetch.requestPaused":
                    asyncio.create_task(self._handle_paused(msg.get("params", {})))
                else:
                    self._collect_event(method, msg.get("params", {}))
        except Exception:
            pass

    def _collect_event(self, method: str, params: dict) -> None:
        if method == "Runtime.exceptionThrown":
            d = params.get("exceptionDetails", {})
            desc = d.get("exception", {}).get("description", "") or ""
            self.unhandled.append((d.get("text", "") + " " + desc).strip())
        elif method == "Runtime.consoleAPICalled":
            if params.get("type") == "error":
                text = " ".join(str(a.get("value", a.get("description", ""))) for a in params.get("args", []))
                self.console_errors.append(text)
        elif method == "Log.entryAdded":
            e = params.get("entry", {})
            if e.get("level") == "error":
                self.console_errors.append(e.get("text", ""))
        elif method == "Network.responseReceived":
            resp = params.get("response", {})
            url = resp.get("url", "")
            if "/api/v1/graph" in url:
                key = url.split("/api/v1/")[1].split("?")[0]
                self.api_status[key] = resp.get("status")
            if "AdvancedRelationGraph" in url:
                self.graph_chunks.add(url.rsplit("/", 1)[-1])
            if "/static/js/" in url:
                self.js_requests.append(f"{resp.get('status')} {url.rsplit('/', 1)[-1]}")
        elif method == "Network.loadingFailed":
            self.load_failures.append(str(params.get("errorText", "")) + " " + str(params.get("type", "")))

    async def _handle_paused(self, params: dict) -> None:
        try:
            req_id = params.get("requestId")
            url = (params.get("request", {}) or {}).get("url", "") or ""
            if "/api/v1/auth/refresh" in url:
                # 用铸造材料履约 refresh，等价于真实登录后的续期
                payload = {
                    "code": 0, "message": "success", "success": True,
                    "data": {
                        "avatar": "",
                        "username": self.session["username"],
                        "nickname": self.session["nickname"],
                        "roles": self.session["roles"],
                        "permissions": self.session["permissions"],
                        "accessToken": self.session["accessToken"],
                        "refreshToken": "",
                        "expires": self.session["expires"],
                    },
                }
                await self._send("Fetch.fulfillRequest", {
                    "requestId": req_id,
                    "responseCode": 200,
                    "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                    "body": base64.b64encode(json.dumps(payload).encode()).decode(),
                })
                return
            if "/api/v1/auth/login" in url or "/api/v1/auth/logout" in url:
                await self._send("Fetch.continueRequest", {"requestId": req_id})
                return
            headers = dict(params.get("request", {}).get("headers", {}) or {})
            headers["Authorization"] = f"Bearer {self.session['accessToken']}"
            await self._send("Fetch.continueRequest", {
                "requestId": req_id,
                "headers": [{"name": k, "value": v} for k, v in headers.items()],
            })
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
        for task in (self._listener, getattr(self, "_fetch_task", None)):
            if task:
                task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.proc:
            self.proc.terminate()
        shutil.rmtree(self.user_data, ignore_errors=True)


async def collect_state(chrome: ChromeCDP, label: str) -> dict:
    route_info = await chrome.js(
        "(function(){ var el = document.querySelector('#app');"
        " var app = el && el.__vue_app__;"
        " if (!app) return null;"
        " var r = app.config.globalProperties.$router;"
        " if (!r) return null;"
        " var c = r.currentRoute.value;"
        " return { path: c.path, name: c.name, matched: c.matched.map(function(m){return m.path;}) }; })()"
    )
    return {
        "label": label,
        "pathname": await chrome.js("location.pathname"),
        "hash_route": await chrome.js("location.hash"),
        "route_info": route_info,
        "graph_page": bool(await chrome.js("!!document.querySelector('.asset-graph-page')")),
        "toolbar": bool(await chrome.js("!!document.querySelector('.asset-graph-page .graph-toolbar, .asset-graph-page [class*=toolbar]')")),
        "error_panel": bool(await chrome.js("!!document.querySelector('.graph-error-panel')")),
        "empty_state_text": await chrome.js("(document.querySelector('.graph-wrap')||{}).innerText?.slice(0,80) || ''"),
        "canvas_count": await chrome.js("document.querySelectorAll('.advanced-graph-canvas canvas').length"),
        "svg_nodes": await chrome.js("document.querySelectorAll('g.graph-node').length"),
        "svg_edges": await chrome.js("document.querySelectorAll('path.graph-edge').length"),
        "page_errors": await chrome.js("window.__errs || []"),
        "ls_keys": await chrome.js("Object.keys(localStorage)"),
        "cookies": await chrome.js("document.cookie.replace(/=[^;]*/g, '=*')"),
        "graph_api": dict(chrome.api_status),
        "graph_chunks": sorted(chrome.graph_chunks),
        "js_requests_tail": chrome.js_requests[-15:],
        "load_failures": chrome.load_failures[-10:],
    }


async def run_acceptance(shot_dir: Path) -> dict:
    session = fetch_session_material()
    tunnel = TunnelForward()
    tunnel.start()
    tunnel.serve()
    await asyncio.sleep(1)
    chrome = ChromeCDP(shot_dir, session)
    chrome.start()
    await chrome.setup()
    base = f"http://127.0.0.1:{LOCAL_PORT}"
    try:
        rounds = []
        # 首轮 + 连续 3 次刷新（119-S4：刷新 3 次无 Edge already exists）
        # 前端为 hash 路由（VITE_ROUTER_HISTORY=hash），图谱地址是 /#/asset/graph
        for i in range(4):
            await chrome.navigate(f"{base}/#/asset/graph")
            await asyncio.sleep(3)
            # 等待图谱出现或错误面板出现
            for _ in range(30):
                done = await chrome.js(
                    "!!document.querySelector('.advanced-graph-canvas canvas') || "
                    "document.querySelectorAll('g.graph-node').length > 0 || "
                    "!!document.querySelector('.graph-error-panel') || "
                    "location.hash.includes('/login')"
                )
                if done:
                    break
                await asyncio.sleep(1)
            await asyncio.sleep(8)  # 等 G6 布局/渲染收尾
            state = await collect_state(chrome, f"round_{i}" + ("" if i == 0 else "_refresh"))
            await chrome.screenshot(f"accept_round_{i}.png")
            rounds.append(state)

        bad_errors = [
            e for r in rounds for e in (r["page_errors"] or [])
            if "Edge already exists" in e or "split" in e or "render failed" in e
        ]
        return {
            "shots": str(shot_dir),
            "session_user": session["username"],
            "rounds": rounds,
            "console_errors": chrome.console_errors[-20:],
            "unhandled_rejections": chrome.unhandled[-20:],
            "graph_api_all_200": bool(chrome.api_status) and all(s == 200 for s in chrome.api_status.values()),
            "no_fatal_graph_errors": not bad_errors,
            "fatal_graph_errors": bad_errors[:5],
        }
    finally:
        await chrome.close()
        tunnel.stop()


def main() -> int:
    shot_dir = Path(tempfile.gettempdir()) / "graph_acceptance_shots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(run_acceptance(shot_dir))
    # 输出前脱敏：session 材料不进入结果
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = (
        result["graph_api_all_200"]
        and result["no_fatal_graph_errors"]
        and all(r["graph_page"] and not r["error_panel"] for r in result["rounds"])
        and all((r["canvas_count"] or 0) > 0 or (r["svg_nodes"] or 0) > 0 for r in result["rounds"])
        and not result["console_errors"]
        and not result["unhandled_rejections"]
    )
    print(f"ACCEPTANCE {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
