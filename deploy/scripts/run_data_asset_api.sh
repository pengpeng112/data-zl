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

# credentials 卷需可写：系统连接页通过 credential_store 原子写入 *.readonly 凭据文件。
# 业务源库仍只读；此处仅平台侧凭据文件持久化。目录权限建议 0700。
# 111 号 S7：权限设置失败必须失败关闭，禁止用 || true 忽略。
chmod 700 "${CREDS}"

docker run -d --name "${NAME}" --restart unless-stopped \
  --network host \
  --env-file "${ENV_FILE}" \
  -v "${CREDS}:/etc/data-asset/credentials:rw" \
  -v "${ORACLE_HOST_DIR}:/opt/oracle:ro" \
  -e "APP_CREDENTIAL_DIR=/etc/data-asset/credentials" \
  "${IMAGE}" \
  bash -lc 'bash /app/deploy/scripts/ensure_oracle_ro_runtime.sh; exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1'

echo "started ${NAME}"
docker ps --filter "name=${NAME}"
