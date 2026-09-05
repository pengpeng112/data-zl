@echo off
chcp 65001 >nul
setlocal
set KEY=C:\Users\Administrator\.ssh\id_ed25519_ai
set SSH=ssh -i %KEY% -o BatchMode=yes -o StrictHostKeyChecking=accept-new root@10.10.8.83
set SCP=scp -i %KEY% -o BatchMode=yes -o StrictHostKeyChecking=accept-new
set OUT=F:\python\数据资产\开发起步包\output_r170
set PY=F:\python\数据资产\backend\.venv\Scripts\python.exe

echo [1/7] vitest systemMap
cd /d F:\python\数据资产\frontend
call pnpm vitest run tests/systemMap.test.ts > "%OUT%\test.log" 2>&1

echo [2/7] typecheck
call pnpm run typecheck > "%OUT%\typecheck.log" 2>&1

echo [3/7] export production display data (read-only)
%SCP% "F:\python\数据资产\开发起步包\output_r170\export170.py" root@10.10.8.83:/tmp/export170.py
%SSH% "docker cp /tmp/export170.py data-asset-api:/tmp/export170.py && docker exec data-asset-api python /tmp/export170.py"
%SSH% "docker cp data-asset-api:/tmp/export170.json /tmp/export170.json"
%SCP% root@10.10.8.83:/tmp/export170.json "F:\python\数据资产\开发起步包\output_r170\export170.json"

echo [4/7] import into isolated DB (incl. benchmark + token)
cd /d F:\python\数据资产\backend
set APP_TEST_DB_URL=postgresql+psycopg://postgres@127.0.0.1:15432/data_asset_test
set APP_DB_URL=postgresql+psycopg://postgres@127.0.0.1:15432/data_asset_test
set APP_ENV=test
%PY% "..\开发起步包\output_r170\import170.py" > "%OUT%\import.log" 2>&1
type "%OUT%\import.log"

echo [5/7] start backend (isolated DB)
start "uvicorn170" /min cmd /c "set APP_TEST_DB_URL=postgresql+psycopg://postgres@127.0.0.1:15432/data_asset_test&& set APP_DB_URL=postgresql+psycopg://postgres@127.0.0.1:15432/data_asset_test&& set APP_ENV=test&& set APP_RATE_LIMIT_ENABLED=false&& set APP_JWT_SECRET=fix170-only&& %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > %OUT%\uvicorn.log 2>&1"

echo [6/7] start vite
cd /d F:\python\数据资产\frontend
start "vite170" /min cmd /c "pnpm dev > %OUT%\vite.log 2>&1"
timeout /t 30 /nobreak >nul

echo [7/7] screenshot
cd /d F:\python\数据资产\backend
%PY% "..\开发起步包\output_r170\screenshot170.py"
echo DONE
exit
