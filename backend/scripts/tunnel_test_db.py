"""SSH local forward to 10.10.8.83 PostgreSQL for APP_TEST_DB_URL.

Credentials from environment only (never commit):
  APP_SSH_HOST          default 10.10.8.83
  APP_SSH_USER          default root
  APP_SSH_PASSWORD      required (or use key)
  APP_SSH_KEY           optional private key path
  APP_TUNNEL_LOCAL_PORT default 55432

Example:
  set APP_SSH_PASSWORD=***
  python -m scripts.tunnel_test_db
  set APP_TEST_DB_URL=postgresql+psycopg://asset_app:***@127.0.0.1:55432/data_asset_test
  python -m pytest tests/ -q
"""

from __future__ import annotations

import os
import select
import socketserver
import threading
import time

import paramiko

HOST = os.environ.get("APP_SSH_HOST", "10.10.8.83")
USER = os.environ.get("APP_SSH_USER", "root")
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "")
KEY = os.environ.get("APP_SSH_KEY", "")
LOCAL_PORT = int(os.environ.get("APP_TUNNEL_LOCAL_PORT", "55432"))
REMOTE_HOST = os.environ.get("APP_TUNNEL_REMOTE_HOST", "127.0.0.1")
REMOTE_PORT = int(os.environ.get("APP_TUNNEL_REMOTE_PORT", "5432"))


class ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(transport: paramiko.Transport):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                chan = transport.open_channel(
                    "direct-tcpip",
                    (REMOTE_HOST, REMOTE_PORT),
                    self.request.getpeername(),
                )
            except Exception:
                return
            if chan is None:
                return
            try:
                while True:
                    r, _w, _x = select.select([self.request, chan], [], [], 60)
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

    return Handler


def main() -> None:
    if not PASSWORD and not KEY:
        raise SystemExit("Set APP_SSH_PASSWORD or APP_SSH_KEY")

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    connect_kwargs = {
        "hostname": HOST,
        "username": USER,
        "timeout": 15,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if KEY:
        connect_kwargs["key_filename"] = KEY
    if PASSWORD:
        connect_kwargs["password"] = PASSWORD
    client.connect(**connect_kwargs)
    transport = client.get_transport()
    if transport is None:
        raise SystemExit("SSH transport unavailable")
    transport.set_keepalive(30)

    server = ForwardServer(("127.0.0.1", LOCAL_PORT), make_handler(transport))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(
        f"TUNNEL_READY 127.0.0.1:{LOCAL_PORT} -> {HOST}:{REMOTE_HOST}:{REMOTE_PORT}",
        flush=True,
    )
    print(
        "Set APP_TEST_DB_URL=postgresql+psycopg://asset_app:<password>@127.0.0.1:"
        f"{LOCAL_PORT}/data_asset_test",
        flush=True,
    )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
        client.close()


if __name__ == "__main__":
    main()
