# -*- coding: utf-8 -*-
"""T27/T28 浏览器闭环 API 壳：真实 app + 进程级假源连接器（sqlite ATTACH comm）。

用法（仓库根，先 source tools/dev_env.sh）：
  cd backend && PYTHONPATH=. ./.venv/Scripts/python.exe \\
    "../开发起步包/output_r200/r200-20260922-remediation/browser_t27_t28/run_t27_api.py"

要点：
- 平台库 = 隔离库 data_asset_test（隧道 15432）；业务源库连接数恒为 0；
- dict_sync_executor/medical_code_push 两个命名空间的 _open_write_connection /
  _run_write_on_conn / _run_select_on_conn 被替换为 sqlite 假源（dialect 报 "oracle"
  以沿用 Oracle 方言 SQL；SYSDATE 改写为 CURRENT_TIMESTAMP；:name 绑定 sqlite 原生支持）；
- dispatch_target/_run_target_transaction/outcomes/回读/outbox 全部走真实代码路径。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("APP_JWT_SECRET", "t27-browser-only-secret")
os.environ.setdefault("APP_DICT_MEDICAL_PUSH_ENABLED", "true")
os.environ.setdefault("APP_DICT_MEDICAL_PUSH_CONFIRMATION_TOKEN", "t27-confirm-token")
os.environ.setdefault("APP_DICT_MEDICAL_HIS_SOURCE_CODE", "qa_t27_his")
os.environ.setdefault("APP_DICT_MEDICAL_JHEMR_SOURCE_CODE", "qa_t27_jhemr")
os.environ.setdefault("QA_T27_FAKE_CRED", "u:p")
os.environ.setdefault("APP_DICT_MEDICAL_WORKER_INTERVAL_SECONDS", "2")

DIAG_COLS = [
    ("DIAGNOSIS_CODE", "TEXT"), ("DIAGNOSIS_NAME", "TEXT"), ("STD_INDICATOR", "TEXT"),
    ("APPROVED_INDICATOR", "TEXT"), ("CREATE_DATE", "TEXT"), ("INPUT_CODE", "TEXT"),
    ("DIAG_INDICATOR", "TEXT"), ("NM1", "TEXT"), ("YB_CODE", "TEXT"), ("YB_NAME", "TEXT"),
    ("STOP_FLAG", "INTEGER"), ("DIAGNOSIS_CODE_GUO", "TEXT"), ("DIAGNOSIS_NAME_GUO", "TEXT"),
    ("DIAGNOSIS_TYPE", "TEXT"), ("MTB_FLAG", "TEXT"), ("MTB_CODE", "TEXT"), ("MTB_NAME", "TEXT"),
    ("DIAGNOSIS_CODE_MB", "TEXT"), ("DIAGNOSIS_NAME_MB", "TEXT"), ("DIAGNOSIS_CODE_ICD", "TEXT"),
    ("DIAGNOSIS_NAME_ICD", "TEXT"), ("DIAGNOSIS_CODE_CRB", "TEXT"), ("DIAGNOSIS_NAME_CRB", "TEXT"),
]


def _build_stub_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("ATTACH DATABASE ':memory:' AS comm")
    cols = ", ".join(f"{c} {t}" for c, t in DIAG_COLS)
    cur.execute(f"CREATE TABLE IF NOT EXISTS comm.diagnosis_dict ({cols})")
    cur.execute("CREATE TABLE IF NOT EXISTS comm.operation_dict ("
                "OPERATION_CODE TEXT, OPERATION_NAME TEXT, STOP_FLAG INTEGER)")
    conn.commit()
    cur.close()
    return conn


def _install_fake_source_connectors() -> None:
    import re

    from app.services import dict_sync_executor as ex
    from app.services import medical_code_push as mcp

    def _fake_open(source):  # noqa: ANN001
        return _build_stub_conn(), "oracle"

    def _fake_write(conn, dialect, sql, params):
        cur = conn.cursor()
        try:
            cur.execute(sql.replace("SYSDATE", "CURRENT_TIMESTAMP"), params or {})
            rc = cur.rowcount if cur.rowcount is not None else 0
        finally:
            cur.close()
        return int(rc)

    def _sqlite_sql(sql: str) -> str:
        # Oracle → sqlite 方言改写：SYSDATE 与 ROWNUM<=N（存在性比对/读回用）
        sql = sql.replace("SYSDATE", "CURRENT_TIMESTAMP")
        m = re.search(r"ROWNUM\s*<=\s*(\d+)", sql, flags=re.I)
        if m:
            sql = re.sub(r"(AND\s+)?ROWNUM\s*<=\s*\d+", "", sql, flags=re.I)
            sql = f"{sql.rstrip(';')} LIMIT {m.group(1)}"
        return sql

    def _fake_select(conn, dialect, sql, params):
        cur = conn.cursor()
        try:
            cur.execute(_sqlite_sql(sql), params or {})
            colnames = [d[0] if d else f"c{i}" for i, d in enumerate(cur.description or [])]
            rows = cur.fetchall() or []
            return [{colnames[i]: row[i] for i in range(len(colnames))} for row in rows]
        finally:
            cur.close()

    for mod in (ex, mcp):
        mod._open_write_connection = _fake_open
        mod._run_write_on_conn = _fake_write
        mod._run_select_on_conn = _fake_select
    print("[t27-api] 假源连接器已安装（sqlite ATTACH comm；SYSDATE/ROWNUM 方言改写；业务源库连接=0）", flush=True)


def main() -> int:
    url = os.environ.get("APP_DB_URL", "") or os.environ.get("APP_TEST_DB_URL", "")
    if "test" not in url.lower():
        print("[t27-api] 拒绝：APP_DB_URL 未标识测试库")
        return 2
    _install_fake_source_connectors()

    import uvicorn
    from app.main import app

    print(f"[t27-api] serving 127.0.0.1:8000 -> {url.split('@')[-1]}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
