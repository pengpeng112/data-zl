"""Run the existing five executor tests in a fresh UUID-owned test schema."""
import importlib.util
import os
import sys
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path.cwd()
sys.path.insert(0, str(root / "backend"))
url = make_url(os.environ["APP_TEST_DB_URL"])
assert url.database == "data_asset_test"
engine = create_engine(url)
with engine.connect() as connection:
    assert connection.execute(text("SELECT current_database()")).scalar_one() == "data_asset_test"
engine.dispose()
path = root / "backend/tests/reporting_pipeline_integration/test_target_executor_isolated_pg.py"
spec = importlib.util.spec_from_file_location("maintenance_executor_regression", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
schema = "t1_maint_" + uuid.uuid4().hex[:16]
module.SCHEMA = schema
module.TABLE = schema + ".emr_test_table"
module.RECEIPTS = schema + ".asset_receipts_it"
module.EXEC_CONFIG = replace(module.EXEC_CONFIG, tenant=schema, table=module.TABLE, receipt_table=module.RECEIPTS)
original_request = module._apply_request


def scoped_request(*args, **kwargs):
    return replace(original_request(*args, **kwargs), target_object=f"data_asset_test.{schema}.EMR_TEST_TABLE")


module._apply_request = scoped_request
suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.TestExecutorOnRealPg)
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 5 else 1)
