#!/bin/sh
set -eu

PACKAGE_ROOT="${1:-/pkg}"
VENV_ROOT="$(mktemp -d /tmp/data-asset-r8.XXXXXX)"
VENV_DIR="$VENV_ROOT/venv"
APP_PID=""

cleanup() {
    if [ -n "$APP_PID" ]; then
        kill "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --require-hashes --no-index \
    --find-links="$PACKAGE_ROOT/wheels" \
    -r "$PACKAGE_ROOT/backend/requirements.lock"
"$VENV_DIR/bin/pip" check

cd "$PACKAGE_ROOT/backend"
"$VENV_DIR/bin/python" -m alembic upgrade head
"$VENV_DIR/bin/python" -m alembic upgrade head
"$VENV_DIR/bin/python" -m alembic downgrade -1
"$VENV_DIR/bin/python" -m alembic upgrade head
"$VENV_DIR/bin/python" -m alembic current

"$VENV_DIR/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >"$VENV_ROOT/uvicorn.log" 2>&1 &
APP_PID=$!

attempt=0
while [ "$attempt" -lt 20 ]; do
    if "$VENV_DIR/bin/python" - <<'PY'
import urllib.request
from urllib.error import URLError

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as response:
        if response.status != 200:
            raise SystemExit(f"unexpected health status: {response.status}")
        print(f"HEALTH_STATUS={response.status}")
except URLError:
    raise SystemExit(1) from None
PY
    then
        echo "R8_BACKEND_DRILL_OK"
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 1
done

echo "health check did not become ready" >&2
cat "$VENV_ROOT/uvicorn.log" >&2
exit 1
