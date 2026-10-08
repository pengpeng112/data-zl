#!/usr/bin/env bash
# R212 S3/O01 编排：全量pytest结束后串行执行（独占隔离库窗口）。
# 密码经环境变量：R212_ADMIN_PW / R212_VIEWER_PW（不落文件）。
# 用法：source tools/dev_env.sh 后 bash s3_pipeline.sh
set -uo pipefail
ROOT="F:/python/数据资产"
RUN="$ROOT/开发起步包/output_r212/r212-20261008-zcode-r214b"
PY="$ROOT/backend/.venv/Scripts/python.exe"

echo "== [1/6] 重灌基础数据 import170 =="
PYTHONPATH="$ROOT/backend" "$PY" "$ROOT/开发起步包/output_r170/import170.py" || { echo "import170 FAIL"; exit 1; }

echo "== [2/6] RBAC 角色+权限码 =="
"$PY" "$ROOT/backend/scripts/seed_platform_rbac.py" || exit 1

echo "== [3/6] 测试身份：platform-admin + r212-viewer(asset_viewer) =="
R212_USER_PW="$R212_ADMIN_PW" "$PY" "$ROOT/backend/scripts/create_role_user_r212.py" --username platform-admin --role platform_admin --force || exit 1
R212_USER_PW="$R212_VIEWER_PW" "$PY" "$ROOT/backend/scripts/create_role_user_r212.py" --username r212-viewer --role asset_viewer --force || exit 1

echo "== [4/6] 启动后端 :8000 与前端 preview :8898 =="
cd "$ROOT/backend"
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$RUN/logs/uvicorn.log" 2>&1 &
BACKEND_PID=$!
cd "$ROOT/frontend"
pnpm exec vite preview --port 8898 --strictPort > "$RUN/logs/preview.log" 2>&1 &
PREVIEW_PID=$!
echo "backend_pid=$BACKEND_PID preview_pid=$PREVIEW_PID"
# 等两个端口就绪（冷启动可能>8s，最多90s）
for i in $(seq 1 45); do
  B=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null)
  F=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8898/ 2>/dev/null)
  [ "$B" != "000" ] && [ "$F" != "000" ] && break
  sleep 2
done
echo "wait_ready: backend=$B preview=$F (after ${i}x2s)"

echo "== [5/6] 浏览器 S3 =="
cd "$RUN"
R212_ADMIN_PW="$R212_ADMIN_PW" R212_VIEWER_PW="$R212_VIEWER_PW" "$PY" capture_r212.py
S3_EXIT=$?

echo "== [6/6] O01 短负载 =="
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"platform-admin\",\"password\":\"$R212_ADMIN_PW\"}" \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin)['data']['accessToken'])")
if [ -z "$TOKEN" ]; then echo "login for O01 FAIL"; else
  R212_TOKEN="$TOKEN" "$PY" o01_short_load.py
fi

echo "== 收尾：停服务 =="
kill $BACKEND_PID $PREVIEW_PID 2>/dev/null
sleep 2
echo "s3_exit=$S3_EXIT done"
