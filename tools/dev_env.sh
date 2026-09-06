#!/usr/bin/env bash
# dev_env.sh — 数据资产项目开发环境一键自检/装配（Git Bash）。
# 用法：
#   source tools/dev_env.sh              # 建隧道(15432 不通才建) + 推导 APP_TEST_DB_URL(不回显口令)
#   bash tools/dev_env.sh --domain-baseline [FILE]   # 记录他人域(layout/capture)文件哈希基线
#   bash tools/dev_env.sh --domain-check [FILE]       # 对照基线校验他人域是否被改
# 规则：不杀别人的 15432 转发（占用即复用）；口令只进环境变量不落终端历史。
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="C:/Users/Administrator/.ssh/id_ed25519_ai"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -i "$KEY")

OTHER_DOMAIN_FILES=(
  "frontend/src/layout/index.vue"
  "frontend/src/layout/components/lay-content/index.vue"
  "frontend/src/layout/components/lay-setting/index.vue"
  "frontend/src/layout/hooks/useDataThemeChange.ts"
  "frontend/src/layout/hooks/useTag.ts"
  "frontend/src/store/modules/app.ts"
  "frontend/src/layout/captureMode.ts"
  "frontend/tests/competitionCaptureMode.test.ts"
  "tools/capture_ai_patrol_gif.py"
  "tools/capture_competition_ai_demos.py"
  "tools/capture_competition_screens.py"
  "tools/capture_four_governance_screens.py"
  "tools/capture_governance_gifs.py"
)

tunnel_up() {
  # 185 WARN 最小修复：本机 Git Bash 的 grep 为 ugrep，netstat 输出（CRLF+GBK 头）
  # 使 `grep -q "127.0.0.1:15432.*LISTENING"` 恒不命中 → 误判隧道不在、重复建转发失败。
  # 改用 bash 内建 /dev/tcp 探测（无外部命令依赖，实测 2026-09-06）。
  (exec 3<>/dev/tcp/127.0.0.1/15432) 2>/dev/null
}

ensure_tunnel() {
  if tunnel_up; then
    echo "[tunnel] 15432 已在监听（复用，未动现有转发）"
  else
    echo "[tunnel] 15432 不通，建立新转发…"
    ssh -f -N -L 15432:127.0.0.1:5432 -o ServerAliveInterval=30 \
      -o ExitOnForwardFailure=yes "${SSH_OPTS[@]}" root@10.10.8.83 2>/dev/null
    sleep 1
    tunnel_up && echo "[tunnel] 建立 OK" || { echo "[tunnel] 建立失败：检查公钥 SSH root@10.10.8.83"; return 1; }
  fi
}

derive_url() {  # 口令不回显；输出写入全局 APP_TEST_DB_URL
  local url
  url="$(ssh "${SSH_OPTS[@]}" root@10.10.8.83 \
    'grep ^APP_DB_URL /etc/data-asset/backend.env' 2>/dev/null \
    | sed -E 's/^APP_DB_URL=//; s#@[^/]+/#@127.0.0.1:15432/#; s#/data_asset(\?.*)?$#/data_asset_test\1#')"
  if [[ -z "$url" || "$url" != *data_asset_test* ]]; then
    echo "[url] 推导失败（服务器 env 读取异常）" >&2; return 1
  fi
  export APP_TEST_DB_URL="$url"
  export APP_DB_URL="$url"
  echo "[url] APP_TEST_DB_URL 已设置 -> $(echo "$url" | sed -E 's#//[^@]+@#//***@#')"
}

domain_files_existing() {
  local f
  for f in "${OTHER_DOMAIN_FILES[@]}"; do
    [[ -f "$ROOT/$f" ]] && echo "$f"
  done
}

case "${1:-}" in
  --domain-baseline)
    OUT="${2:-$ROOT/开发起步包/output_domain_baseline.txt}"
    { echo "# other-domain hash baseline $(date '+%F %T') HEAD=$(git -C "$ROOT" rev-parse --short HEAD)"
      cd "$ROOT" && git hash-object $(domain_files_existing)
    } > "$OUT"
    echo "[baseline] $(grep -c . "$OUT") 行 -> $OUT";;
  --domain-check)
    BASE="${2:-$ROOT/开发起步包/output_domain_baseline.txt}"
    [[ -f "$BASE" ]] || { echo "[check] 基线不存在: $BASE（先 --domain-baseline）"; exit 2; }
    NOW="$(cd "$ROOT" && git hash-object $(domain_files_existing))"
    if diff <(grep -v '^#' "$BASE") <(echo "$NOW") >/dev/null; then
      echo "[check] 他人域 $(domain_files_existing | wc -l) 文件与基线一致 ✔"
    else
      echo "[check] ✘ 他人域有变动："
      diff <(grep -v '^#' "$BASE") <(echo "$NOW") || true
      exit 1
    fi;;
  "")
    ensure_tunnel && derive_url
    echo "[remind] 隔离库脚本一律显式 \$APP_TEST_DB_URL；跑全量 pytest 前终止非本会话 pytest；"
    echo "[remind] pytest 后按惯例重灌: PYTHONPATH=backend backend/.venv/Scripts/python.exe 开发起步包/output_r170/import170.py";;
  *) echo "用法: source tools/dev_env.sh | bash tools/dev_env.sh --domain-baseline|--domain-check [FILE]"; exit 2;;
esac
