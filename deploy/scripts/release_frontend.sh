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

# 3. 原子切换：previous -> 当前 current 指向；current -> 新版本
#    214 E-A3 修复（两处叠加缺陷，r169→r203→r210 生产表现=previous 恒指 r169）：
#    a) 原 `cp -d "${CURRENT_LINK}"` 对“指向目录的软链”在部分 cp 实现下按目录
#       处理（-r 未指定直接拒绝）；
#    b) 原 `mv -f "${PREVIOUS_LINK}.tmp" "${PREVIOUS_LINK}"` 在 previous 已是
#       “指向目录的软链”时把 .tmp 移进目录内部而非替换（缺 -T）——
#       第二次发布起 previous 永不更新。
#    改为 readlink 显式取目标 + ln 造 .tmp + `mv -Tf` 原子替换；
#    同版本复跑视为 no-op（previous 不动，避免覆盖回滚锚点）。
NEED_SWITCH=1
if [ -L "${CURRENT_LINK}" ] && [ "$(readlink "${CURRENT_LINK}")" = "${TARGET_DIR}" ]; then
  NEED_SWITCH=0
fi
if [ "${NEED_SWITCH}" = "1" ]; then
  if [ -L "${CURRENT_LINK}" ]; then
    OLD_CURRENT_TARGET="$(readlink "${CURRENT_LINK}")"
    ln -sfn "${OLD_CURRENT_TARGET}" "${PREVIOUS_LINK}.tmp"
    mv -Tf "${PREVIOUS_LINK}.tmp" "${PREVIOUS_LINK}"
    echo "[release_frontend] previous -> ${OLD_CURRENT_TARGET}"
  else
    echo "[release_frontend] no current link yet; previous left untouched"
  fi
  ln -sfn "${TARGET_DIR}" "${CURRENT_LINK}"
else
  echo "[release_frontend] current already -> ${TARGET_DIR}; skip switch (previous untouched)"
fi

# 4. 切换后校验：current 原始链接目标必须等于本次 target；
#    previous（若存在）不得与 current 同目标。用 readlink 原始值比对，
#    不用 readlink -f（MSYS 下对末级软链不解析，Linux 行为虽正常但无必要）。
CUR_NOW="$(readlink "${CURRENT_LINK}")"
if [ "${CUR_NOW}" != "${TARGET_DIR}" ]; then
  echo "[release_frontend] ERROR: current does not point to target after switch" >&2
  exit 1
fi
PREV_NOW="$(readlink "${PREVIOUS_LINK}" 2>/dev/null || true)"
if [ -n "${PREV_NOW}" ] && [ "${PREV_NOW}" = "${CUR_NOW}" ]; then
  echo "[release_frontend] ERROR: previous must not point to the just-released build" >&2
  exit 1
fi

echo "[release_frontend] current -> ${TARGET_DIR}"
echo "[release_frontend] previous -> $(readlink -f "${PREVIOUS_LINK}" 2>/dev/null || echo none)"
echo "[release_frontend] DONE. nginx root should point to ${CURRENT_LINK}"
