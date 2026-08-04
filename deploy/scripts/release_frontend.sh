#!/bin/bash
# ============================================================
# 108 号 P0-03：前端版本目录完整上传后原子切换（软链接）
#
# 用法：
#   ./release_frontend.sh <build_id> <dist目录> [nginx_root]
#
# 行为：
#   1. 将 dist 完整复制到 <nginx_root>/releases/<build_id>（不混放旧包）
#   2. 校验 HTML 引用的所有 JS/CSS 均存在（发布后自动检查）
#   3. 原子切换软链接 current -> releases/<build_id>
#   4. 保留 previous -> 上一个版本，供回滚
#
# 安全：不在活动目录混放新旧 hash 分包；切换是原子符号链接操作。
# ============================================================
set -euo pipefail

BUILD_ID="${1:?usage: release_frontend.sh <build_id> <dist_dir> [nginx_root]}"
DIST_DIR="${2:?usage: release_frontend.sh <build_id> <dist_dir> [nginx_root]}"
NGINX_ROOT="${3:-/opt/data-asset/frontend-dist}"

RELEASES_DIR="${NGINX_ROOT}/releases"
CURRENT_LINK="${NGINX_ROOT}/current"
PREVIOUS_LINK="${NGINX_ROOT}/previous"
TARGET_DIR="${RELEASES_DIR}/${BUILD_ID}"

echo "[release_frontend] build_id=${BUILD_ID}"
echo "[release_frontend] dist=${DIST_DIR}"
echo "[release_frontend] target=${TARGET_DIR}"

mkdir -p "${RELEASES_DIR}"

# 1. 完整复制（幂等：目标已存在则视为已完成上传）
if [ -d "${TARGET_DIR}" ]; then
  echo "[release_frontend] target exists, skip copy"
else
  echo "[release_frontend] copying dist -> target (完整版本目录，不增量覆盖)"
  cp -a "${DIST_DIR}/." "${TARGET_DIR}/"
fi

# 2. 校验 HTML 引用的所有静态资源存在
echo "[release_frontend] verifying referenced assets..."
INDEX_HTML="${TARGET_DIR}/index.html"
if [ ! -f "${INDEX_HTML}" ]; then
  echo "[release_frontend] ERROR: index.html missing in target" >&2
  exit 1
fi
MISSING=0
for ref in $(grep -oE 'src="[^"]+"|href="[^"]+"' "${INDEX_HTML}" | sed -E 's/^(src|href)="//; s/"$//' | grep -E '^/'); do
  rel="${ref#/}"
  if [ ! -f "${TARGET_DIR}/${rel}" ]; then
    echo "[release_frontend] MISSING asset: ${ref}" >&2
    MISSING=$((MISSING+1))
  fi
done
if [ "${MISSING}" -gt 0 ]; then
  echo "[release_frontend] ERROR: ${MISSING} referenced assets missing" >&2
  exit 1
fi
echo "[release_frontend] all referenced assets present"

# 3. 原子切换：previous -> 当前 current；current -> 新版本
if [ -L "${CURRENT_LINK}" ]; then
  cp -d "${CURRENT_LINK}" "${PREVIOUS_LINK}.tmp"
  mv -f "${PREVIOUS_LINK}.tmp" "${PREVIOUS_LINK}"
fi
ln -sfn "${TARGET_DIR}" "${CURRENT_LINK}"

echo "[release_frontend] current -> ${TARGET_DIR}"
echo "[release_frontend] previous -> $(readlink -f "${PREVIOUS_LINK}" 2>/dev/null || echo none)"
echo "[release_frontend] DONE. nginx root should point to ${CURRENT_LINK}"
