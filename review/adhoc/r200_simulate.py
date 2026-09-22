"""Run existing dictionary simulations with isolated import-only configuration.

No application/source database connection is opened by this harness.
The original tests strip APP_*; inject local SQLite config inside each snippet.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FILES = ["test_dict_executor.py", "test_dict_outbox_policy.py",
         "test_identity_write_gates.py", "test_orchestrator_write_gates.py",
         "test_review_fixes.py"]


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="r200_test_") as directory:
        url = "sqlite+pysqlite:///" + (Path(directory) / "r200_test.db").as_posix()
        prefix = "import os\nos.environ.update(" + repr({
            "APP_ENV": "test", "APP_DB_URL": url, "APP_TEST_DB_URL": url,
            "APP_JWT_SECRET": "synthetic-r200-test-only-secret",
        }) + ")\n"
        for name in FILES:
            spec = importlib.util.spec_from_file_location("case", BACKEND / "tests/dict_sync_112" / name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            snippet = prefix + module._SNIPPET.replace("{BACKEND_DIR}", str(BACKEND))
            env = {k: v for k, v in os.environ.items() if not k.startswith(("APP_", "PYTEST_"))}
            result = subprocess.run([sys.executable, "-c", snippet], cwd=ROOT,
                                    env=env, capture_output=True, text=True, timeout=90)
            results.append({"case": name, "returncode": result.returncode,
                            "stdout": result.stdout, "stderr": result.stderr})
        probe = r'''
import sys
sys.path.insert(0, BACKEND_PATH)
from app.services.medical_code_push import build_stop_action
from app.services.dict_sync_executor import _run_target_transaction
class Cursor:
    def __init__(self, owner, rowcount=1, select_rows=None):
        self.owner = owner; self.rowcount = rowcount; self._select_rows = select_rows or []
        self.description = [("code",), ("stopped",)]
        self._is_select = False
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params=None):
        self.owner.calls.append((sql, params))
        self._is_select = (sql or "").lstrip().upper().startswith("SELECT")
    def fetchone(self): return self._select_rows[0] if self._select_rows else None
    def fetchall(self): return list(self._select_rows)
    def close(self): pass
class Connection:
    def __init__(self, rowcount=1, select_rows=None):
        self.calls = []; self._rowcount = rowcount; self._select_rows = select_rows
    def cursor(self): return Cursor(self, rowcount=self._rowcount, select_rows=self._select_rows)

# 200 D04 修复后回归断言：stop 动作不进入任何 INSERT 存在检查，
# 直接以正确业务键执行 UPDATE；rowcount=1 → stopped。
action = build_stop_action(category_code="operation", target_system="JHEMR_VASTBASE",
                           item_code="SYNTHETIC_OP_01", hospital_no="SYNTHETIC_HOSP").to_dict()
conn = Connection(rowcount=1)
counts = {}; outcomes = {}
_run_target_transaction(conn, "postgresql", [action], row_counts=counts, outcomes=outcomes)
writes = [(sql, p) for sql, p in conn.calls if not sql.lstrip().upper().startswith("SELECT")]
assert len(writes) == 1 and writes[0][0].startswith("UPDATE"), writes
assert counts[action["action_id"]] == 1
assert outcomes[action["action_id"]] == "stopped"
params = writes[0][1]
assert params == {"code": "SYNTHETIC_OP_01", "hospital_no": "SYNTHETIC_HOSP"}, params

# rowcount=0 且回读已停用一致 → no_op（不再是被 INSERT 查重吞掉的 0）。
conn2 = Connection(rowcount=0, select_rows=[("SYNTHETIC_OP_01", 1)])
counts2 = {}; outcomes2 = {}
_run_target_transaction(conn2, "postgresql", [dict(action)], row_counts=counts2, outcomes=outcomes2)
assert counts2[action["action_id"]] == 0
assert outcomes2[action["action_id"]] == "no_op"
print("REGRESSION OK: stop bypasses INSERT existence branch; UPDATE by exact key; stopped/no_op classified")
'''
        probe = probe.replace("BACKEND_PATH", repr(str(BACKEND)))
        result = subprocess.run([sys.executable, "-c", prefix + probe], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=90)
        results.append({"case": "stop_existing_row_regression", "returncode": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return int(any(row["returncode"] for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
