#!/usr/bin/env python3
"""Sync local backend + frontend dist to 10.10.8.83 running container.

Usage (PowerShell):
  $env:APP_SSH_PASSWORD='***'
  python deploy/scripts/sync_local_to_server.py

Does NOT write to HIS/ODS/HRP business databases.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"

DEFAULT_HOST = os.environ.get("APP_SSH_HOST", "10.10.8.83")
DEFAULT_USER = os.environ.get("APP_SSH_USER", "root")
CONTAINER = os.environ.get("APP_DOCKER_CONTAINER", "data-asset-api")


def _connect_sshd(host: str, user: str, password: str) -> paramiko.SSHClient:
    """111 号 S7：默认拒绝未知主机，杜绝 AutoAddPolicy 静默信任。

    加载系统 known_hosts（或 APP_SSH_KNOWN_HOSTS 显式文件）后，用
    RejectPolicy 连接：目标主机不在 known_hosts 或指纹不匹配时 paramiko
    抛 SSHException，连接失败关闭，绝不静默接受未知主机。
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    known_hosts_path = os.environ.get("APP_SSH_KNOWN_HOSTS", "")
    if known_hosts_path:
        client.load_host_keys(str(Path(known_hosts_path).expanduser()))
    else:
        client.load_system_host_keys()
    try:
        client.connect(
            host,
            username=user,
            password=password,
            timeout=20,
            allow_agent=False,
            look_for_keys=False,
        )
    except (paramiko.SSHException, OSError) as exc:
        raise SystemExit(
            f"SSH 连接被拒绝：目标主机 {host} 未通过 host key 校验。"
            f"请先将 {host} 的 host key 加入 known_hosts "
            f"(或设置 APP_SSH_KNOWN_HOSTS 指向受控文件) 后重试。原因: {exc}"
        )
    return client


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_backend_tar() -> Path:
    ignore_dirs = {
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "logs",
        "data",
        ".mypy_cache",
        "htmlcov",
        ".ruff_cache",
    }
    ignore_prefixes = ("_tmp", "_deploy", "_run", "_sync", "_ufe", "_v", "_chk", "_ready", "_hotfix", "_audit")
    fd, name = tempfile.mkstemp(suffix="-backend-sync.tar.gz")
    os.close(fd)
    out = Path(name)
    with tarfile.open(out, "w:gz") as tar:
        for path in BACKEND.rglob("*"):
            if not path.is_file():
                continue
            if any(p in ignore_dirs for p in path.parts):
                continue
            if path.suffix == ".pyc":
                continue
            if path.name.startswith(ignore_prefixes):
                continue
            # keep tests for completeness but optional
            arc = f"backend/{path.relative_to(BACKEND).as_posix()}"
            tar.add(path, arcname=arc)
    return out


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    _i, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    return o.channel.recv_exit_status(), out, err


def sftp_mkdirs(sftp: paramiko.SFTPClient, path: str) -> None:
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def put_tree(sftp: paramiko.SFTPClient, local: Path, remote: str) -> int:
    n = 0
    sftp_mkdirs(sftp, remote)
    for root, _dirs, files in os.walk(local):
        rel = os.path.relpath(root, local).replace("\\", "/")
        rdir = remote if rel == "." else f"{remote}/{rel}"
        sftp_mkdirs(sftp, rdir)
        for f in files:
            sftp.put(str(Path(root) / f), f"{rdir}/{f}")
            n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=os.environ.get("APP_SSH_PASSWORD", ""))
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--restart", action="store_true", default=True)
    args = parser.parse_args()
    if not args.password:
        raise SystemExit("Set APP_SSH_PASSWORD or pass --password")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    remote_rel = f"/opt/data-asset/releases/sync-{stamp}"

    client = _connect_sshd(args.host, args.user, args.password)
    print(f"ssh_ok {args.host}")

    sftp = client.open_sftp()
    sftp_mkdirs(sftp, remote_rel)

    if not args.skip_backend:
        print("packing backend...")
        tar_path = make_backend_tar()
        remote_tar = f"{remote_rel}/backend-sync.tar.gz"
        print("upload backend", round(tar_path.stat().st_size / 1024 / 1024, 2), "MB")
        sftp.put(str(tar_path), remote_tar)
        tar_path.unlink(missing_ok=True)
        code, out, err = run(
            client,
            f"set -e; cd {remote_rel}; tar -xzf backend-sync.tar.gz; "
            f"docker cp {remote_rel}/backend/. {CONTAINER}:/app/; "
            f"if [ -d {remote_rel}/../202607130921-login/wheels_login ]; then "
            f"  docker cp {remote_rel}/../202607130921-login/wheels_login {CONTAINER}:/wheels_login || true; "
            f"fi; "
            f"docker exec {CONTAINER} pip install --no-index --find-links=/wheels_login "
            f"  'argon2-cffi>=23.1' 'python-jose[cryptography]>=3.3' >/tmp/pip_sync.log 2>&1 || true; "
            f"docker exec {CONTAINER} python -c \"from app.api.v1 import auth; import argon2,jose; print('backend_ok')\"",
            timeout=600,
        )
        print("backend_sync", code, out.strip()[-300:])
        if code != 0:
            print(err[-500:])
            raise SystemExit("backend sync failed")

    if not args.skip_frontend:
        if not FRONTEND_DIST.exists():
            raise SystemExit("frontend/dist missing; run pnpm build first")
        print("upload frontend dist...")
        n = put_tree(sftp, FRONTEND_DIST, f"{remote_rel}/frontend-dist")
        print("frontend_files", n)
        code, out, err = run(
            client,
            f"set -e; rm -rf /opt/data-asset/frontend-dist/*; "
            f"cp -a {remote_rel}/frontend-dist/. /opt/data-asset/frontend-dist/; "
            f"nginx -t && systemctl reload nginx; echo frontend_ok",
        )
        print("frontend_sync", code, out.strip()[-200:])

    sftp.close()

    if args.restart:
        code, out, err = run(client, f"docker restart {CONTAINER}; sleep 4; curl -fsS http://127.0.0.1:8000/health")
        print("restart", code, out.strip()[:220])

    # verify key files
    checks = [
        "docker exec data-asset-api python -c \"from app.api.v1 import auth; print('auth_module_ok')\"",
        "python3 - <<'PY'\nimport json,urllib.request\nd=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json',timeout=10))\nprint('has_login', '/api/v1/auth/login' in d.get('paths',{}))\nPY",
        "python3 - <<'PY'\nfrom pathlib import Path\nimport re\nt=Path('/opt/data-asset/frontend-dist/index.html').read_text(errors='ignore')\nprint(re.findall(r'index-[A-Za-z0-9_-]+\\.js', t)[:2])\nPY",
    ]
    for cmd in checks:
        code, out, err = run(client, cmd)
        print("verify", out.strip()[:200])

    # write sync stamp on server
    run(client, f"echo {stamp} > /opt/data-asset/LAST_SYNC_STAMP; date >> /opt/data-asset/LAST_SYNC_STAMP")
    print("SYNC_DONE", stamp)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
