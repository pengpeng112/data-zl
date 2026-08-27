"""Debug dashboard_summary failure on server."""
from __future__ import annotations

import io
import os
import traceback

import paramiko

HOST = os.environ.get("APP_SSH_HOST", "10.10.8.83")
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")

REMOTE = r"""
import traceback
from app.core.db import SessionLocal
from app.api.v1.tables import dashboard_summary

db = SessionLocal()
try:
    res = dashboard_summary(db=db)
    data = res.data if hasattr(res, 'data') else res
    print('OK keys', list(data.keys()) if isinstance(data, dict) else type(data))
except Exception:
    traceback.print_exc()
finally:
    db.close()
"""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    try:
        sftp.putfo(io.BytesIO(REMOTE.encode()), "/tmp/debug_dash.py")
        _, o, e = c.exec_command(
            "docker cp /tmp/debug_dash.py data-asset-api:/tmp/debug_dash.py; "
            "docker exec -e PYTHONPATH=/app -w /app data-asset-api python /tmp/debug_dash.py; "
            "docker logs data-asset-api --tail 40 2>&1",
            timeout=60,
        )
        print(o.read().decode("utf-8", "replace"))
        print(e.read().decode("utf-8", "replace")[:2000])
    finally:
        sftp.close()
        c.close()


if __name__ == "__main__":
    main()
