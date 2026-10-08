#!/usr/bin/env bash
# R212 S3 浏览器复跑（数据已在库，仅重置测试身份密码→起服务→捕获→停服务）
set -uo pipefail
ROOT="F:/python/数据资产"
RUN="$ROOT/开发起步包/output_r212/r212-20261008-zcode-r214b"
PY="$ROOT/backend/.venv/Scripts/python.exe"

R212_USER_PW="$R212_ADMIN_PW" "$PY" "$ROOT/backend/scripts/create_role_user_r212.py" --username platform-admin --role platform_admin --force || exit 1
R212_USER_PW="$R212_VIEWER_PW" "$PY" "$ROOT/backend/scripts/create_role_user_r212.py" --username r212-viewer --role asset_viewer --force || exit 1

cd "$ROOT/backend"
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$RUN/logs/uvicorn2.log" 2>&1 &
BACKEND_PID=$!
cd "$ROOT/frontend"
pnpm exec vite preview --port 8898 --strictPort > "$RUN/logs/preview2.log" 2>&1 &
PREVIEW_PID=$!
for i in $(seq 1 45); do
  B=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null)
  F=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8898/ 2>/dev/null)
  [ "$B" != "000" ] && [ "$F" != "000" ] && break
  sleep 2
done
echo "wait_ready: backend=$B preview=$F"
cd "$RUN"
R212_ADMIN_PW="$R212_ADMIN_PW" R212_VIEWER_PW="$R212_VIEWER_PW" "$PY" capture_r212.py
S3=$?
kill $BACKEND_PID $PREVIEW_PID 2>/dev/null
sleep 2
echo "s3_exit=$S3"
