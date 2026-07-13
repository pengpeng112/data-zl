#!/usr/bin/env bash
# Recommended recreate of data-asset-api with persistent mounts.
# Usage (on 8.83):
#   bash /opt/data-asset/deploy/scripts/run_data_asset_api.sh
# Does NOT write to HIS/ODS/HRP.
set -euo pipefail

IMAGE="${DATA_ASSET_IMAGE:-data-asset-api:local}"
NAME="${DATA_ASSET_CONTAINER:-data-asset-api}"
ENV_FILE="${DATA_ASSET_ENV_FILE:-/etc/data-asset/backend.env}"
CREDS="${DATA_ASSET_CREDENTIALS_DIR:-/etc/data-asset/credentials}"
ORACLE_HOST_DIR="${DATA_ASSET_ORACLE_DIR:-/opt/oracle}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "missing env file: ${ENV_FILE}" >&2
  exit 1
fi
mkdir -p "${CREDS}"

# stop old
if docker ps -a --format '{{.Names}}' | grep -qx "${NAME}"; then
  docker stop "${NAME}" || true
  docker rm "${NAME}" || true
fi

docker run -d --name "${NAME}" --restart unless-stopped \
  --env-file "${ENV_FILE}" \
  -v "${CREDS}:/etc/data-asset/credentials:ro" \
  -v "${ORACLE_HOST_DIR}:/opt/oracle:ro" \
  -p 127.0.0.1:8000:8000 \
  "${IMAGE}" \
  bash -lc 'bash /app/deploy/scripts/ensure_oracle_ro_runtime.sh || true; uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1'

echo "started ${NAME}"
docker ps --filter "name=${NAME}"
