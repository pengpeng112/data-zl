import ast
import re
from pathlib import Path

import pytest

from app.services.db_connectors import OracleConnector, PostgresConnector, validate_readonly_sql


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO HIS.PAT_VISIT VALUES (1)",
        "SELECT * INTO copied_visits FROM HIS.PAT_VISIT WHERE patient_id = :patient_id",
        "SELECT * FROM HIS.PAT_VISIT; DELETE FROM HIS.PAT_VISIT",
        "SELECT * FROM HIS.PAT_VISIT FOR UPDATE",
        "COPY HIS.PAT_VISIT TO '/tmp/visits.csv'",
    ],
)
def test_sql_guard_rejects_writes_and_dialect_escape_hatches(sql):
    with pytest.raises(ValueError):
        validate_readonly_sql(sql)


def test_sql_guard_requires_where_for_known_or_configured_large_tables():
    with pytest.raises(ValueError, match="WHERE"):
        validate_readonly_sql("SELECT * FROM HIS.LAB_RESULT")
    with pytest.raises(ValueError, match="WHERE"):
        validate_readonly_sql("SELECT * FROM audit.events", {"audit.events"})

    assert validate_readonly_sql("WITH visits AS (SELECT * FROM HIS.LAB_RESULT WHERE TEST_NO = :test_no) SELECT * FROM visits")


class FakeOracleCursor:
    description = [("PATIENT_ID",)]

    def __init__(self):
        self.executed = []
        self.fetch_size = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchmany(self, size):
        self.fetch_size = size
        return [("P001",)]

    def close(self):
        pass


class FakeOracleConnection:
    def __init__(self):
        self.cursor_instance = FakeOracleCursor()
        self.call_timeout = None

    def cursor(self):
        return self.cursor_instance

    def rollback(self):
        pass


def test_oracle_readonly_transaction_timeout_and_row_cap_are_enforced():
    connector = OracleConnector(host="unused", port=1521, database="unused", timeout_ms=1234)
    connection = FakeOracleConnection()
    connector._conn = connection

    rows = connector.execute_readonly("SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE PATIENT_ID = :patient_id", {"patient_id": "P001"}, 999999)

    assert rows == [{"PATIENT_ID": "P001"}]
    assert connection.call_timeout == 1234
    assert connection.cursor_instance.executed[0] == ("SET TRANSACTION READ ONLY", None)
    # A4：连接器多取 1 行探针（max_rows+1），调用方据此判定截断。
    assert connection.cursor_instance.fetch_size == 10_001


class FakePostgresCursor:
    def __init__(self):
        self.executed = []
        self.fetch_size = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchmany(self, size):
        self.fetch_size = size
        return [{"patient_id": "P001"}]

    def close(self):
        pass


class FakePostgresConnection:
    def __init__(self):
        self.cursor_instance = FakePostgresCursor()

    def cursor(self, **kwargs):
        return self.cursor_instance


def test_postgres_preserves_parameters_and_fetches_at_most_requested_rows(monkeypatch):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "psycopg.rows", types.SimpleNamespace(dict_row=object()))
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(rows=sys.modules["psycopg.rows"]))
    connector = PostgresConnector(host="unused", port=5432, database="unused")
    connection = FakePostgresConnection()
    connector._conn = connection

    connector.execute_readonly("SELECT patient_id FROM asset.asset_patients WHERE patient_id = %(patient_id)s", {"patient_id": "P001"}, 2)

    assert connection.cursor_instance.executed == [
        ("SELECT patient_id FROM asset.asset_patients WHERE patient_id = %(patient_id)s", {"patient_id": "P001"})
    ]
    # A4：多取 1 行探针（max_rows+1）。
    assert connection.cursor_instance.fetch_size == 3


def test_ssh_jump_remote_script_compiles():
    """161 P0-2：锁 F1 不复发。

    ssh_jump 的远端脚本是三引号字符串，没有编译器/测试保护（round-2 曾被编辑
    损坏缩进导致远端 IndentationError、跳板 Oracle 取数全灭）。这里提取全部内嵌
    脚本字面量并逐个 ast.parse，任何缩进/语法损坏直接在本地测试暴露。
    """
    source_path = Path(__file__).resolve().parents[1] / "app" / "services" / "db_connectors.py"
    source = source_path.read_text(encoding="utf-8-sig")
    scripts = re.findall(r'remote_script\s*=\s*r?"""(.*?)"""', source, flags=re.S)
    assert scripts, "ssh_jump remote_script literal not found in db_connectors.py"
    for index, script in enumerate(scripts):
        ast.parse(script, filename=f"<db_connectors remote_script #{index}>")
