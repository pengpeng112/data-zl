"""Read-only catalog baseline for plan 90 review (no secrets printed)."""
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
    raise SystemExit("parse fail")
user, pwd, host, port, db = m.group(1), m.group(2), m.group(3), int(m.group(4)), m.group(5)
print(f"host={host} db={db} user={user}")
conn = psycopg.connect(host=host, port=port, user=user, password=pwd, dbname=db, connect_timeout=10)
cur = conn.cursor()
try:
    cur.execute("select version_num from alembic_version")
    print("alembic", cur.fetchone())
except Exception as exc:  # noqa: BLE001
    print("alembic_err", type(exc).__name__)
    conn.rollback()

print("=== SYSTEMS ===")
cur.execute(
    "select system_code, system_name_cn, coalesce(status,'') "
    "from asset.asset_systems order by system_code"
)
for row in cur.fetchall():
    print(row)

print("=== SOURCES (base cols) ===")
cur.execute(
    "select system_code, source_code, enabled, coalesce(host_masked,''), coalesce(port::text,'') "
    "from asset.asset_data_sources order by system_code, source_code"
)
for row in cur.fetchall():
    print(row)

print("=== TABLES BY SYSTEM ===")
cur.execute(
    "select coalesce(system_code,'(null)'), count(*) "
    "from asset.asset_tables group by system_code order by 1"
)
for row in cur.fetchall():
    print(row)

print("=== TABLES BY SOURCE ===")
cur.execute(
    "select coalesce(source_code,'(null)'), count(*) "
    "from asset.asset_tables group by source_code order by 2 desc nulls last limit 30"
)
for row in cur.fetchall():
    print(row)

print("=== ROW STATS ===")
cur.execute(
    """
    select
      count(*) filter (where row_count_stats in ('0','0.0')) as zeroish,
      count(*) filter (where row_count_stats is null or btrim(row_count_stats)='') as unknown_rows,
      count(*) as total
    from asset.asset_tables
    """
)
print(cur.fetchone())
cur.execute("select count(*) from asset.asset_columns")
print("columns", cur.fetchone()[0])
cur.execute("select count(*) from asset.asset_relations")
print("relations", cur.fetchone()[0])
conn.close()
