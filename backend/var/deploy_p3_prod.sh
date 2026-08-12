#!/bin/bash
set -euo pipefail
RELEASE="${1:?release id}"
REMOTE="/opt/data-asset/releases/${RELEASE}"
CONTAINER=data-asset-api

echo "=== backup ==="
sudo -u postgres /usr/local/pgsql/bin/pg_dump -Fc -d data_asset -f "/tmp/data_asset_pre_${RELEASE}.dump"
mv "/tmp/data_asset_pre_${RELEASE}.dump" /opt/data-asset/backups/
ls -lh "/opt/data-asset/backups/data_asset_pre_${RELEASE}.dump"

echo "=== extract backend ==="
mkdir -p "${REMOTE}/backend"
tar -xzf "${REMOTE}/backend.tar.gz" -C "${REMOTE}/backend"
docker cp "${REMOTE}/backend/." "${CONTAINER}:/app/"
docker exec "${CONTAINER}" python -c "from app.services.core_metric_import import import_core_metrics; print('import_ok')"

echo "=== migrate ==="
docker exec "${CONTAINER}" python -m alembic upgrade head
sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset -t -c 'SELECT version_num FROM alembic_version;'

echo "=== restart ==="
docker restart "${CONTAINER}"
sleep 8
curl -fsS http://127.0.0.1:8000/api/v1/health
echo

echo "=== core48 sql ==="
mkdir -p "${REMOTE}/core48"
tar -xzf "${REMOTE}/core48-sql.tar.gz" -C "${REMOTE}/core48"
docker exec "${CONTAINER}" mkdir -p /app/var/core48_sql
docker cp "${REMOTE}/core48/." "${CONTAINER}:/app/var/core48_sql/"

echo "=== import core 48 ==="
docker exec "${CONTAINER}" python - <<'PY'
from pathlib import Path
from app.core.db import SessionLocal
from app.services.core_metric_import import import_core_metrics
db = SessionLocal()
try:
    r = import_core_metrics(
        db,
        sql_dir=Path("/app/var/core48_sql"),
        dry_run=False,
        created_by="prod_import_core48",
    )
    print("count", r["count"])
    print("active_metrics", sum(1 for i in r["items"] if i.get("metric", {}).get("status") == "active"))
    print("sample", [(i["metric_code"], i["title"]) for i in r["items"][:5]])
finally:
    db.close()
PY

echo "=== counts ==="
sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset -c \
  "SELECT count(*) AS queries FROM asset.asset_query_definitions;
   SELECT count(*) AS metrics FROM asset.asset_metric_definitions;
   SELECT count(*) AS q_active FROM asset.asset_query_versions WHERE is_active;
   SELECT count(*) AS m_active FROM asset.asset_metric_versions WHERE is_active;"

python3 - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json", timeout=15))
paths = d.get("paths", {})
for k in [
    "/api/v1/queries/import/core-48",
    "/api/v1/queries/impact/table",
    "/api/v1/queries/schedules",
]:
    print(k, "OK" if k in paths else "MISSING")
print("APP_QUERY_SCHEDULE_ENABLED default off (not set)")
PY
echo DEPLOY_P3_DONE
