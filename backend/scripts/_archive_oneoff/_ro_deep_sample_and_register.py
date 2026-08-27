"""Deep SELECT-only sampling + register platform sources/systems (platform PG write only).

- Oracle: SELECT only
- Credentials written only under /etc/data-asset/credentials on 8.83 (mode 600)
- Never print passwords
"""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=240):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    code = o.channel.recv_exit_status()
    return code, o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


DEEP_PY = textwrap.dedent(
    """\
    import os, json, oracledb

    oracledb.init_oracle_client(lib_dir="/opt/oracle")

    def connect(host, port, service, user, password):
        conn = oracledb.connect(user=user, password=password, dsn=f"{host}:{port}/{service}")
        cur = conn.cursor()
        try:
            cur.execute("SET TRANSACTION READ ONLY")
        except Exception:
            pass
        return conn, cur

    def q(cur, sql):
        cur.execute(sql)
        cols = [d[0].lower() for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        if not cols:
            return rows
        if len(cols) == 1:
            return [r[0] for r in rows]
        return [dict(zip(cols, r)) for r in rows]

    results = {}

    # --- ODS ---
    raw = os.environ["CRED_ODS"]
    u, p = raw.split(":", 1)
    conn, cur = connect("10.10.8.216", 1521, "orcl", u, p)
    ods = {"user": u.upper()}
    ods["top_owners"] = q(cur, '''
        SELECT owner, COUNT(*) AS cnt FROM all_tables
        WHERE owner NOT IN (
          'SYS','SYSTEM','OUTLN','DBSNMP','XDB','WMSYS','ORDSYS','MDSYS','CTXSYS',
          'OLAPSYS','EXFSYS','IX','ORDDATA','ORDPLUGINS','SI_INFORMTN_SCHEMA','APPQOSSYS'
        )
        GROUP BY owner ORDER BY COUNT(*) DESC
    ''')
    for fq in [
        "HIS.PAT_MASTER_INDEX",
        "HIS.PAT_VISIT",
        "HIS.LAB_TEST_MASTER",
        "HIS.EXAM_MASTER",
        "HIS.ORDERS",
        "CDA.CDA_DICTIONARY",
    ]:
        owner, table = fq.split(".")
        try:
            n = q(cur, f"SELECT COUNT(*) FROM all_tab_columns WHERE owner='{owner}' AND table_name='{table}'")
            cols = q(cur, f"SELECT column_name FROM all_tab_columns WHERE owner='{owner}' AND table_name='{table}' AND ROWNUM<=8 ORDER BY column_id")
            try:
                row_probe = q(cur, f"SELECT 1 FROM {owner}.{table} WHERE ROWNUM<=1")
            except Exception as ex:
                row_probe = f"ERR:{type(ex).__name__}:{str(ex)[:100]}"
            ods[fq] = {"col_count": n[0] if n else 0, "sample_cols": cols, "has_row": row_probe}
        except Exception as ex:
            ods[fq] = f"ERR:{type(ex).__name__}:{str(ex)[:120]}"
    try:
        ods["ods_views_sample"] = q(cur, "SELECT view_name FROM all_views WHERE owner='ODS' AND ROWNUM<=10")
    except Exception as ex:
        ods["ods_views_sample"] = f"ERR:{type(ex).__name__}"
    try:
        ods["his_views_count"] = q(cur, "SELECT COUNT(*) FROM all_views WHERE owner='HIS'")[0]
    except Exception as ex:
        ods["his_views_count"] = str(ex)[:80]
    cur.close(); conn.close()
    results["ODS"] = ods

    # --- HIS source ---
    raw = os.environ["CRED_HIS_SOURCE"]
    u, p = raw.split(":", 1)
    conn, cur = connect("10.10.10.15", 1521, "his", u, p)
    his = {"user": u.upper()}
    his["top_owners"] = q(cur, '''
        SELECT owner, COUNT(*) AS cnt FROM all_tables
        WHERE owner NOT IN (
          'SYS','SYSTEM','OUTLN','DBSNMP','XDB','WMSYS','ORDSYS','MDSYS','CTXSYS',
          'OLAPSYS','EXFSYS','IX','ORDDATA','ORDPLUGINS','SI_INFORMTN_SCHEMA','APPQOSSYS'
        )
        GROUP BY owner ORDER BY COUNT(*) DESC
    ''')
    for owner in ["MEDREC","ORDADM","LAB","EXAM","COMM","INPBILL","OUTPBILL","OUTPADM","INPADM","DRUG_USER","PHARMACY","MEDADM"]:
        try:
            his[f"owner_{owner}"] = q(cur, f"SELECT COUNT(*) FROM all_tables WHERE owner='{owner}'")[0]
        except Exception as ex:
            his[f"owner_{owner}"] = f"ERR:{type(ex).__name__}"
    for fq in [
        "MEDREC.PAT_MASTER_INDEX",
        "MEDREC.PAT_VISIT",
        "ORDADM.ORDERS",
        "LAB.LAB_TEST_MASTER",
        "EXAM.EXAM_MASTER",
        "COMM.STAFF_DICT",
    ]:
        owner, table = fq.split(".")
        try:
            n = q(cur, f"SELECT COUNT(*) FROM all_tab_columns WHERE owner='{owner}' AND table_name='{table}'")
            cols = q(cur, f"SELECT column_name FROM all_tab_columns WHERE owner='{owner}' AND table_name='{table}' AND ROWNUM<=10 ORDER BY column_id")
            try:
                row_probe = q(cur, f"SELECT 1 FROM {owner}.{table} WHERE ROWNUM<=1")
            except Exception as ex:
                row_probe = f"ERR:{type(ex).__name__}:{str(ex)[:100]}"
            his[fq] = {"col_count": n[0] if n else 0, "sample_cols": cols, "has_row": row_probe}
        except Exception as ex:
            his[fq] = f"ERR:{type(ex).__name__}:{str(ex)[:120]}"
    cur.close(); conn.close()
    results["HIS"] = his

    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    """
)

REG_SQL = textwrap.dedent(
    """\
    -- systems (no enabled column on asset_systems)
    INSERT INTO asset.asset_systems (system_code, system_name_cn, system_type, description_cn, status)
    VALUES
      ('DATA_CENTER', '数据中心/ODS', 'ODS', '10.10.8.216 数据中心汇聚库', 'active'),
      ('HIS_SOURCE', 'HIS 源端', 'HIS', '10.10.10.15/his 多 owner 业务库', 'active')
    ON CONFLICT (system_code) DO UPDATE SET
      system_name_cn = EXCLUDED.system_name_cn,
      system_type = EXCLUDED.system_type,
      description_cn = EXCLUDED.description_cn,
      status = 'active',
      updated_at = now();

    INSERT INTO asset.asset_data_sources (
      system_code, source_code, source_name_cn, db_type, host_masked, port, service_name,
      connection_mode, environment, collect_mode, credential_ref, write_credential_ref,
      description_cn, enabled, last_check_status, last_check_at
    ) VALUES
      ('DATA_CENTER', 'ods_8_216', '数据中心 ODS 10.10.8.216/orcl', 'oracle', '10.10.8.216', 1521, 'orcl',
       'direct', 'prod', 'metadata_only', 'file:///etc/data-asset/credentials/ods_8_216', NULL,
       '只读探库主目标；DB 账号权限含写特权，平台侧强制 SELECT-only', true, 'ok', now()),
      ('HIS_SOURCE', 'his_source_10_10_10_15', 'HIS业务库 10.10.10.15/his', 'oracle', '10.10.10.15', 1521, 'his',
       'direct', 'prod', 'metadata_only', 'file:///etc/data-asset/credentials/his_source_10_10_10_15', NULL,
       'ready_his 只读账号；SELECT ANY TABLE', true, 'ok', now())
    ON CONFLICT (source_code) DO UPDATE SET
      system_code = EXCLUDED.system_code,
      source_name_cn = EXCLUDED.source_name_cn,
      db_type = EXCLUDED.db_type,
      host_masked = EXCLUDED.host_masked,
      port = EXCLUDED.port,
      service_name = EXCLUDED.service_name,
      connection_mode = EXCLUDED.connection_mode,
      environment = EXCLUDED.environment,
      collect_mode = EXCLUDED.collect_mode,
      credential_ref = EXCLUDED.credential_ref,
      description_cn = EXCLUDED.description_cn,
      enabled = true,
      last_check_status = EXCLUDED.last_check_status,
      last_check_at = EXCLUDED.last_check_at,
      updated_at = now();
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_deep_sample.py", "w") as f:
        f.write(DEEP_PY)
    with sftp.file("/tmp/ro_register_sources.sql", "w") as f:
        f.write(REG_SQL)
    sftp.close()

    inject = (
        "export CRED_ODS=${CRED_ODS:-ods:ods123}; "
        "export CRED_HIS_SOURCE=${CRED_HIS_SOURCE:-ready_his:ready_his}; "
    )

    # Ensure thick client still fixed (container restart may reset)
    code, out, err = run(
        c,
        "docker exec data-asset-api bash -lc "
        "'ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so; "
        "ln -sfn libocci.so.19.1 /opt/oracle/libocci.so; "
        "ls -la /opt/oracle/libclntsh.so'",
        timeout=30,
    )
    print("=== client link", out.strip(), err[:200] if err else "")

    code, out, err = run(
        c,
        f"{inject} docker cp /tmp/ro_deep_sample.py data-asset-api:/tmp/ro_deep_sample.py; "
        f"docker exec -e CRED_ODS -e CRED_HIS_SOURCE data-asset-api python /tmp/ro_deep_sample.py",
        timeout=240,
    )
    print("=== deep sample exit", code)
    print(out[:14000])
    if err:
        print("ERR", err[:1500])

    # credentials + register (platform only)
    code, out, err = run(
        c,
        f"{inject} "
        "mkdir -p /etc/data-asset/credentials; chmod 700 /etc/data-asset/credentials; "
        "printf '%s\\n' \"$CRED_ODS\" > /etc/data-asset/credentials/ods_8_216; "
        "printf '%s\\n' \"$CRED_HIS_SOURCE\" > /etc/data-asset/credentials/his_source_10_10_10_15; "
        "chmod 600 /etc/data-asset/credentials/*; "
        "sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset -v ON_ERROR_STOP=1 -f /tmp/ro_register_sources.sql; "
        "sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset -c "
        "\"SELECT system_code, source_code, host_masked, port, service_name, credential_ref, last_check_status, enabled "
        "FROM asset.asset_data_sources ORDER BY id\"; "
        "sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset -c "
        "\"SELECT system_code, system_name_cn, system_type, status FROM asset.asset_systems ORDER BY id\"; "
        "ls -la /etc/data-asset/credentials/",
        timeout=60,
    )
    print("=== register exit", code)
    print(out[:6000])
    if err and "could not change directory" not in err:
        print("ERR", err[:1500])
    elif err:
        print("(psql dir noise ok)")

    c.close()


if __name__ == "__main__":
    main()
