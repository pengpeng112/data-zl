# -*- coding: utf-8 -*-
"""ODS 8.216 最小连接探测（185 docare 诊断双臂之目标臂）。
与每晚 00:10 失败点 his_visits 完全同一原语：同 OracleConnector 参数/凭据/驱动，仅 SELECT 1。"""
from pathlib import Path
from datetime import datetime
from app.services.db_connectors import OracleConnector

u, p = Path("/etc/data-asset/credentials/ods_8_216").read_text(encoding="utf-8").strip().split(":", 1)
conn = OracleConnector(host="10.10.8.216", port=1521, database="orcl", user=u, password=p,
                       connection_mode="direct", oracle_client_lib_dir="/opt/oracle", timeout_ms=60000)
r = conn.execute_readonly("SELECT 1 AS OK, TO_CHAR(SYSDATE,'HH24:MI:SS') AS T FROM DUAL")
print("ODS_PROBE_OK", r, "at", datetime.now().isoformat())
