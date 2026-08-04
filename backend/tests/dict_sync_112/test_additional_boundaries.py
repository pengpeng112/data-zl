"""Additional 112 boundary checks in a subprocess with an explicit test URL."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_additional_boundaries():
    code = r'''
from app.core.config import settings
from app.services.dict_medical_push import normalize_target_system
from app.services.dict_sync_executor import _run_target_transaction

assert normalize_target_system("HIS") == "HIS_SOURCE"
assert normalize_target_system("JHEMR") == "JHEMR_VASTBASE"
try:
    normalize_target_system("arbitrary_database")
except ValueError:
    pass
else:
    raise AssertionError("unknown target must fail closed")

settings.jhemr_serial_whitelisted_sequence = ""
calls = []
class Conn:
    def rollback(self):
        pass
def writer(*args, **kwargs):
    calls.append(True)
    return 1
import app.services.dict_sync_executor as executor
executor._run_write_on_conn = writer
try:
    _run_target_transaction(Conn(), "postgresql", [{
        "action_id": "icd-1", "action_type": "insert",
        "target_table": "jhemr.jhdict_icd_vs_clinic",
        "sql": "INSERT INTO jhemr.jhdict_icd_vs_clinic (serial_no) VALUES (%(serial_no)s)",
        "params": {"serial_no": None}, "plan_status": "blocked",
    }], row_counts={})
except Exception:
    pass
else:
    raise AssertionError("missing sequence must fail closed")
assert calls == []
print("BOUNDARIES_OK")
'''
    env = {k: v for k, v in os.environ.items() if not k.startswith("APP_")}
    env["APP_ENV"] = "test"
    env["APP_TEST_DB_URL"] = "postgresql://u:p@127.0.0.1:5432/asset_test"
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BOUNDARIES_OK" in proc.stdout
