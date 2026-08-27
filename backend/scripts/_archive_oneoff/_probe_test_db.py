"""Probe APP_DB_URL host for data_asset_test without printing secrets."""
from __future__ import annotations

import re
from pathlib import Path

import psycopg

text = Path(__file__).resolve().parents[1].joinpath(".env").read_text(encoding="utf-8", errors="ignore")
url = ""
for line in text.splitlines():
    if line.startswith("APP_DB_URL="):
        url = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
m = re.match(r"postgresql(?:\+\w+)?://([^:]+):([^@]+)@([^:/]+):(\d+)/(\w+)", url)
if not m:
    print("PARSE_FAIL")
    raise SystemExit(1)
user, pwd, host, port, db = m.group(1), m.group(2), m.group(3), int(m.group(4)), m.group(5)
print(f"HOST={host} PORT={port} USER={user} PROD_DB={db}")
for target in ("data_asset_test", db):
    try:
        conn = psycopg.connect(host=host, port=port, user=user, password=pwd, dbname=target, connect_timeout=8)
        cur = conn.cursor()
        cur.execute("select current_database(), current_user")
        print("OK", target, cur.fetchone())
        cur.execute("select count(*) from information_schema.tables where table_schema='asset'")
        print("asset_table_count", cur.fetchone()[0])
        try:
            cur.execute("select version_num from alembic_version")
            print("alembic", cur.fetchone())
        except Exception as exc:  # noqa: BLE001
            print("alembic_err", type(exc).__name__, str(exc)[:80])
            conn.rollback()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        print("FAIL", target, type(exc).__name__, str(exc)[:160])
