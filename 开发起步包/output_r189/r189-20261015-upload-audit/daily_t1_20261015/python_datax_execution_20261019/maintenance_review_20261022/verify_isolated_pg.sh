#!/usr/bin/env bash
# Uses the existing disposable test database only; never the application DB.
set -euo pipefail
source tools/dev_env.sh
export APP_ENV=test
backend/.venv/Scripts/python.exe -c 'import os; from sqlalchemy import create_engine,text; from sqlalchemy.engine import make_url; u=make_url(os.environ["APP_TEST_DB_URL"]); assert u.database == "data_asset_test"; e=create_engine(u); c=e.connect(); n=c.execute(text("SELECT current_database()")).scalar_one(); assert n == "data_asset_test"; print("verified_database="+n); c.close(); e.dispose()'
# Do not load the root autouse TRUNCATE fixture or touch another test's schema.
backend/.venv/Scripts/python.exe '开发起步包/output_r189/r189-20261015-upload-audit/daily_t1_20261015/python_datax_execution_20261019/maintenance_review_20261022/run_executor_regression.py'
backend/.venv/Scripts/python.exe '开发起步包/output_r189/r189-20261015-upload-audit/daily_t1_20261015/python_datax_execution_20261019/maintenance_review_20261022/verify_control_pg.py'
