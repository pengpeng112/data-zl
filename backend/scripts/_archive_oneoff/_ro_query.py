"""本地只读查询辅助：通过 SSH 在 8.83 容器内对 ODS/HIS 执行只读 SQL。

用法（本机）：
    set APP_SSH_PASSWORD=...   (或已在 backend/.env)
    python backend/scripts/_ro_query.py ODS "SELECT COUNT(*) FROM USER_TABLES"

安全：
    - 仅 SELECT/WITH，拒绝 DML/DDL（服务端 _validate_readonly 已有，这里再加一层客户端校验）
    - 凭据从容器内 /etc/data-asset/credentials 读，不传密码
    - 本脚本已 gitignore（_ro_*.py），不进 git
"""
import os
import re
import sys
import paramiko

SSH_HOST = os.environ.get("APP_SSH_HOST", "10.10.8.83")
SSH_USER = os.environ.get("APP_SSH_USER", "root")
SSH_PWD = os.environ.get("APP_SSH_PASSWORD", "")
CONTAINER = os.environ.get("APP_DOCKER_CONTAINER", "data-asset-api")

# source_code -> 凭据文件名 + 连接描述
SOURCES = {
    "ODS": {"cred": "ods_8_216", "desc": "数据中心 8.216 ODS"},
    "HIS": {"cred": "his_source_10_10_10_15", "desc": "HIS 源库 10.10.10.15"},
}

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|"
    r"lock|commit|rollback|savepoint|call|exec|execute)\b",
    re.IGNORECASE,
)


def validate_readonly(sql: str) -> None:
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        raise ValueError(f"只允许 SELECT/WITH，拒绝: {sql[:60]}")
    m = FORBIDDEN.search(s)
    if m:
        raise ValueError(f"SQL 含禁止关键字 '{m.group(0)}'，拒绝执行")


def run(source: str, sql: str, max_rows: int = 200) -> dict:
    validate_readonly(sql)
    if source not in SOURCES:
        raise ValueError(f"未知 source: {source}，可选: {list(SOURCES)}")
    cred = SOURCES[source]["cred"]
    # 凭据文件格式: "user:password"（与 credentials.py resolve() 一致）
    # DSN 固定，账号从凭据文件拆出
    if source == "ODS":
        dsn_line = 'dsn = "10.10.8.216:1521/orcl"'
    else:
        dsn_line = 'dsn = "10.10.10.15:1521/his"'
    inner = f'''
import oracledb, json, sys
try:
    with open("/etc/data-asset/credentials/{cred}") as f:
        raw = f.read().strip()
    # 凭据 "user:password" 拆分
    if ":" in raw:
        user, pwd = raw.split(":", 1)
    else:
        user, pwd = raw, raw  # 退化为纯密码(不该发生)
except Exception as e:
    print(json.dumps({{"error": f"read cred fail: {{e}}"}})); sys.exit(1)
{dsn_line}
try:
    try:
        oracledb.init_oracle_client(lib_dir="/opt/oracle")
    except Exception:
        pass
    conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
    cur = conn.cursor()
    cur.execute("""{sql}""")
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchmany({max_rows})
    nrows = len(rows)
    print(json.dumps({{"cols": cols, "rows": [list(r) for r in rows], "fetched": nrows, "user": user}}, ensure_ascii=False, default=str))
    cur.close(); conn.close()
except Exception as e:
    print(json.dumps({{"error": f"{{type(e).__name__}}: {{e}}"}})); sys.exit(1)
'''
    # 把 inner 脚本通过 stdin 传给容器 python，避免命令行转义地狱
    ssh_cmd = f'docker exec -i {CONTAINER} python3 -'
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, port=22, username=SSH_USER, password=SSH_PWD,
              timeout=20, look_for_keys=False, allow_agent=False)
    stdin, stdout, stderr = c.exec_command(ssh_cmd, timeout=120)
    stdin.write(inner)
    stdin.flush()
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    c.close()
    if err.strip() and not out.strip():
        return {"error": err[:1000]}
    import json
    try:
        return json.loads(out.strip().splitlines()[-1])
    except Exception:
        return {"raw_stdout": out[:2000], "raw_stderr": err[:500]}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python _ro_query.py <ODS|HIS> '<SQL>' [max_rows]")
        sys.exit(1)
    src = sys.argv[1]
    query = sys.argv[2]
    mr = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    import json
    # 从 backend/.env 读 SSH 密码
    if not SSH_PWD:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            for line in open(env_path, encoding="utf-8"):
                if line.startswith("APP_SSH_PASSWORD="):
                    os.environ["APP_SSH_PASSWORD"] = SSH_PWD = line.split("=", 1)[1].strip()
    r = run(src, query, mr)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
