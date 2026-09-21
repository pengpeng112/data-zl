"""Keep pure-logic collection independent of platform database configuration."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


def test_infectious_sync_cases():
    backend = Path(__file__).resolve().parents[2]
    # New, local, disposable SQLite identity for the unchanged import guard.
    # Cases use fake sessions/cursors; no application DDL or source I/O runs.
    with tempfile.TemporaryDirectory(prefix="infectious_test_") as directory:
        path = Path(directory) / "infectious_test.db"
        conn = sqlite3.connect(path)
        try:
            assert Path(conn.execute("PRAGMA database_list").fetchone()[2]) == path
        finally:
            conn.close()
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("APP_") and not k.startswith("PYTEST_")}
        url = "sqlite+pysqlite:///" + path.as_posix()
        env.update(APP_ENV="test", APP_DB_URL=url, APP_TEST_DB_URL=url)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/dict_sync_112/_infectious_sync_cases.py",
             "--confcutdir=tests/dict_sync_112", "-q"],
            cwd=backend, env=env, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
