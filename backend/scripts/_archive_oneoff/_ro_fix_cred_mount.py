"""Mount credentials into container if missing; re-test platform connector."""
from __future__ import annotations

import os
import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=120):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    return o.channel.recv_exit_status(), o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    for cmd in [
        'docker inspect data-asset-api --format "{{json .Mounts}}"',
        "docker exec data-asset-api ls -la /etc/data-asset 2>&1 || true",
        "docker exec data-asset-api ls -la /etc/data-asset/credentials 2>&1 || true",
        "ls -la /etc/data-asset/credentials/",
    ]:
        code, out, err = run(c, cmd)
        print("===", cmd)
        print(out[:2500])
        if err:
            print("ERR", err[:400])

    # Copy credential files into container (durable enough until restart with proper mount)
    # Also add env-based credential_ref alternative in DB if file path not visible
    code, out, err = run(
        c,
        "docker exec data-asset-api mkdir -p /etc/data-asset/credentials; "
        "docker cp /etc/data-asset/credentials/ods_8_216 data-asset-api:/etc/data-asset/credentials/ods_8_216; "
        "docker cp /etc/data-asset/credentials/his_source_10_10_10_15 data-asset-api:/etc/data-asset/credentials/his_source_10_10_10_15; "
        "docker exec data-asset-api chmod 600 /etc/data-asset/credentials/*; "
        "docker exec data-asset-api ls -la /etc/data-asset/credentials/",
    )
    print("=== copy creds into container")
    print(out)
    if err:
        print("ERR", err[:500])

    # Also inject env vars into a one-shot check (without printing values)
    # Prefer dual: file works after copy
    code, out, err = run(
        c,
        "docker exec -e PYTHONPATH=/app data-asset-api bash -lc "
        "'ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so; "
        "ln -sfn libocci.so.19.1 /opt/oracle/libocci.so; "
        "cd /app && python /tmp/ro_platform_check.py'",
        timeout=120,
    )
    print("=== platform check exit", code)
    print(out[:8000])
    if err:
        print("ERR", err[:1500])

    # Recommend durable mount: show how container is started
    code, out, err = run(
        c,
        "docker inspect data-asset-api --format '{{.HostConfig.Binds}}' ; "
        "docker inspect data-asset-api --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E 'APP_|ORACLE|CRED' | sed -E 's/(PASSWORD|SECRET|KEY|TOKEN)=.*/\\1=***/I'",
    )
    print("=== binds/env keys")
    print(out[:3000])
    c.close()


if __name__ == "__main__":
    main()
