#!/bin/bash
# ============================================================
# 108 号 P0-03：前端完整版本回滚（原子切换回 previous）
#
# 用法：
#   ./rollback_frontend.sh [nginx_root]
#
# 回滚使用完整旧版本目录，不是只回滚单个 JS/Python 文件。
# ============================================================
set -euo pipefail

NGINX_ROOT="${1:-/opt/data-asset/frontend-dist}"
CURRENT_LINK="${NGINX_ROOT}/current"
PREVIOUS_LINK="${NGINX_ROOT}/previous"

if [ ! -L "${PREVIOUS_LINK}" ]; then
  echo "[rollback_frontend] ERROR: no previous version to rollback to" >&2
  exit 1
fi

PREV_TARGET="$(readlink -f "${PREVIOUS_LINK}")"
echo "[rollback_frontend] rolling back current -> ${PREV_TARGET}"

# 当前版本保留为 new previous（支持连续回滚）
ln -sfn "${PREV_TARGET}" "${CURRENT_LINK}"
rm -f "${PREVIOUS_LINK}"

echo "[rollback_frontend] current now -> $(readlink -f "${CURRENT_LINK}")"
echo "[rollback_frontend] DONE. reload nginx: nginx -s reload"
