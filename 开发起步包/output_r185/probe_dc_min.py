# -*- coding: utf-8 -*-
"""Docare 10.10.10.68 最小连接探测（185 docare 诊断双臂之对照臂）。
同一容器/同一驱动，仅换目标库——用于排除 8.83 出网整体故障。"""
from pathlib import Path
from datetime import datetime
from app.services.db_connectors import OracleConnector

u, p = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip().split(":", 1)
conn = OracleConnector(host="10.10.10.68", port=1521, database="docare", user=u, password=p,
                       connection_mode="direct", oracle_client_lib_dir="/opt/oracle", timeout_ms=60000)
r = conn.execute_readonly("SELECT 1 AS OK, TO_CHAR(SYSDATE,'HH24:MI:SS') AS T FROM DUAL")
print("DC_PROBE_OK", r, "at", datetime.now().isoformat())
