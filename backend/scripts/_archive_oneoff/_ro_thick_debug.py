"""Debug Oracle thick-mode init inside data-asset-api container. SELECT-only later."""
from __future__ import annotations

import os
import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=90):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    code = o.channel.recv_exit_status()
    return code, o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    remote = r'''
import os, json, oracledb
info = {
  "oracledb": oracledb.__version__,
  "thin_before": oracledb.is_thin_mode(),
  "ORACLE_HOME": os.environ.get("ORACLE_HOME"),
  "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH"),
  "exists_opt_oracle": os.path.isdir("/opt/oracle"),
  "exists_ic21": os.path.isdir("/opt/oracle/instantclient_21"),
  "listing": [],
  "libs": [],
}
try:
    info["listing"] = sorted(os.listdir("/opt/oracle"))[:40]
except Exception as ex:
    info["listing_err"] = str(ex)
for root, dirs, files in os.walk("/opt/oracle"):
    for f in files:
        if "clntsh" in f.lower() or f.startswith("libocci") or f == "libnnz.so" or "oci" in f.lower():
            info["libs"].append(os.path.join(root, f))
    if len(info["libs"]) > 40:
        break

candidates = [
    "/opt/oracle",
    "/opt/oracle/lib",
    "/opt/oracle/instantclient_21",
    os.environ.get("ORACLE_HOME") or "",
]
init_results = []
for lib in candidates:
    if not lib or not os.path.isdir(lib):
        init_results.append({"lib": lib, "status": "missing"})
        continue
    try:
        # fresh process needed for real re-init; here we just try once
        oracledb.init_oracle_client(lib_dir=lib)
        init_results.append({
            "lib": lib,
            "status": "ok",
            "thin_after": oracledb.is_thin_mode(),
        })
        break
    except Exception as ex:
        init_results.append({"lib": lib, "status": "err", "error": f"{type(ex).__name__}:{str(ex)[:200]}"})

info["init_results"] = init_results
info["thin_after"] = oracledb.is_thin_mode()
print(json.dumps(info, ensure_ascii=False, indent=2))
'''
    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_thick_debug.py", "w") as f:
        f.write(remote)
    sftp.close()

    code, out, err = run(
        c,
        "docker cp /tmp/ro_thick_debug.py data-asset-api:/tmp/ro_thick_debug.py; "
        "docker exec data-asset-api python /tmp/ro_thick_debug.py",
        timeout=60,
    )
    print("exit", code)
    print(out[:8000])
    if err:
        print("ERR", err[:1500])

    # host vs container lib presence
    code, out, err = run(
        c,
        "ls -la /usr/lib/oracle 2>/dev/null; ls -la /opt/oracle 2>/dev/null; "
        "find / -name 'libclntsh.so*' 2>/dev/null | head -20; "
        "docker exec data-asset-api bash -lc 'ldd /opt/oracle/libclntsh.so 2>&1 | head -20; "
        "ls -la /opt/oracle/libclntsh* 2>&1 | head -20'",
        timeout=60,
    )
    print("=== host/container libs")
    print(out[:4000])
    if err:
        print("ERR", err[:800])
    c.close()


if __name__ == "__main__":
    main()
