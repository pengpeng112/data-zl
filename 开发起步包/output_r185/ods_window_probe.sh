#!/bin/bash
# ods_window_probe.sh — 185 docare 诊断：双臂只读探测（服务器端自主运行）
# 用法：
#   bash /tmp/ods_window_probe.sh now    # 立即单次迭代（自测用）
#   nohup bash /tmp/ods_window_probe.sh </dev/null >/dev/null 2>&1 &
#                                       # 睡到今晚 23:50，然后每 5 分钟一次共 16 点，至 01:05
# 每行日志：时间 | ODS 尾行 | DC 尾行（成功=*_PROBE_OK；失败=异常尾行，含 ORA-xxxx）
LOG=/tmp/ods_window_probe_result.log
P_ODS=/tmp/probe_ods_min.py
P_DC=/tmp/probe_dc_min.py

one_pass() {
  local TS O D
  TS=$(date '+%F %T')
  O=$(timeout 40 docker exec -i data-asset-api python - < "$P_ODS" 2>&1 | tail -n 1)
  D=$(timeout 40 docker exec -i data-asset-api python - < "$P_DC" 2>&1 | tail -n 1)
  echo "$TS | ODS: $O | DC: $D" >> "$LOG"
}

if [ "${1:-}" = "now" ]; then
  one_pass
  tail -n 1 "$LOG"
  exit 0
fi

TARGET=$(date -d "23:50" +%s)
NOW=$(date +%s)
[ "$TARGET" -le "$NOW" ] && TARGET=$((TARGET + 86400))
SLEEP=$((TARGET - NOW))
echo "=== launcher armed at $(date '+%F %T'), sleeping ${SLEEP}s until $(date -d @"$TARGET" '+%F %T') ===" >> "$LOG"
sleep "$SLEEP"
for i in $(seq 0 15); do
  one_pass
  [ "$i" -lt 15 ] && sleep 300
done
echo "=== probe series done at $(date '+%F %T') ===" >> "$LOG"
