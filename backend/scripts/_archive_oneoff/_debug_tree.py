import io
import os
import traceback

import paramiko

HOST = os.environ.get("APP_SSH_HOST", "10.10.8.83")
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")

REMOTE = r"""
import traceback
from app.core.db import SessionLocal
from app.api.v1.systems import assets_tree
db=SessionLocal()
try:
    res=assets_tree(system_code=None, system_category=None, include_tables=False, max_tables_per_schema=0, db=db)
    print('ok', len(res.data))
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
    sftp.putfo(io.BytesIO(REMOTE.encode()), "/tmp/debug_tree.py")
    sftp.close()
    _, o, e = c.exec_command(
        "docker cp /tmp/debug_tree.py data-asset-api:/tmp/debug_tree.py; "
        "docker exec -e PYTHONPATH=/app -w /app data-asset-api python /tmp/debug_tree.py",
        timeout=60,
    )
    print(o.read().decode())
    print(e.read().decode()[:3000])
    c.close()


if __name__ == "__main__":
    main()
