@echo off
cd /d "F:\python\数据资产\backend"
"F:\python\数据资产\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
