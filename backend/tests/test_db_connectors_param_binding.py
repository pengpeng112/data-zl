"""A1 回归：SqlServer pymssql 分支参数绑定形态。

历史缺陷：pymssql 分支按 tuple(params.values()) 插入序绑参，SQL 占位符顺序与
dict 插入顺序不一致时会绑错值。修法（153 号裁决 #5）：pymssql 原生支持 dict
命名绑定，直接 cursor.execute(sql, params)；pyodbc 分支保持 dict 透传不变。
"""

from app.services.db_connectors import SqlServerConnector


class FakeSqlServerCursor:
    description = [("CNT",), ("VAL",)]

    def __init__(self):
        self.executed: list[tuple[str, object]] = []
        self.fetch_size = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchmany(self, size):
        self.fetch_size = size
        return [(1, "x")]

    def close(self):
        pass


class FakeSqlServerConnection:
    def __init__(self):
        self.cursor_instance = FakeSqlServerCursor()

    def cursor(self):
        return self.cursor_instance


def _pymssql_connector() -> tuple[SqlServerConnector, FakeSqlServerCursor]:
    connector = SqlServerConnector(host="unused", port=1433, database="unused")
    connector._conn = FakeSqlServerConnection()
    connector._driver = "pymssql"
    return connector, connector._conn.cursor_instance


def test_pymssql_passes_dict_params_verbatim():
    """pymssql 分支必须把 dict 原样交给驱动做命名绑定，禁止 tuple(values())。"""
    connector, cursor = _pymssql_connector()
    # 占位符出现顺序与 dict 插入顺序刻意相反（b 在前、a 在后）。
    params = {"b": "second", "a": "first"}
    connector.execute_readonly(
        "SELECT CNT FROM t WHERE b = :b AND a = :a", params, max_rows=10
    )

    sql, bound = cursor.executed[-1]
    assert sql == "SELECT CNT FROM t WHERE b = :b AND a = :a"
    # 命名绑定：驱动收到的必须是 {name: value}，键与值一一对应，
    # 与占位符顺序无关；tuple("second","first") 的插入序绑定正是 A1 缺陷。
    assert isinstance(bound, dict)
    assert bound == {"b": "second", "a": "first"}


def test_pymssql_placeholder_order_independent_binding():
    """参数值绑定正确性：两个占位符交换位置后，dict 依然按名字绑定。"""
    connector, cursor = _pymssql_connector()
    connector.execute_readonly(
        "SELECT VAL FROM t WHERE a = :a AND b = :b",
        {"a": "first", "b": "second"},
        max_rows=5,
    )
    _, bound = cursor.executed[-1]
    assert isinstance(bound, dict)
    assert bound["a"] == "first"
    assert bound["b"] == "second"


def test_pymssql_empty_params_still_safe():
    """无参数时不因空 dict 报错，行为与 execute(sql) 等价。"""
    connector, cursor = _pymssql_connector()
    connector.execute_readonly("SELECT CNT FROM t", None, max_rows=10)
    sql, bound = cursor.executed[-1]
    assert sql == "SELECT CNT FROM t"
    assert bound in (None, {})


def test_pymssql_row_cap_enforced():
    connector, cursor = _pymssql_connector()
    connector.execute_readonly("SELECT CNT FROM t", {"a": 1}, max_rows=999999)
    # A4：多取 1 行探针（max_rows+1）。
    assert cursor.fetch_size == 10_001


def test_pyodbc_branch_keeps_dict_passthrough():
    """pyodbc 分支维持既有 dict 透传语义（裁决 #5：pyodbc 不动）。"""
    connector = SqlServerConnector(host="unused", port=1433, database="unused")
    connector._conn = FakeSqlServerConnection()
    connector._driver = "pyodbc"
    cursor = connector._conn.cursor_instance
    connector.execute_readonly(
        "SELECT CNT FROM t WHERE a = :a", {"a": "first"}, max_rows=10
    )
    sql, bound = cursor.executed[-1]
    assert sql == "SELECT CNT FROM t WHERE a = :a"
    assert bound == {"a": "first"}


def test_ssh_jump_remote_script_is_valid_python():
    """A4 回归：跳板远程脚本必须可 ast.parse，禁止 try/finally 缩进漂移。"""
    import ast
    import inspect

    from app.services.db_connectors import OracleConnector

    src = inspect.getsource(OracleConnector._run_via_ssh_jump)
    start = src.index('remote_script = r"""') + len('remote_script = r"""')
    end = src.index('"""', start)
    remote = src[start:end]
    ast.parse(remote)
    assert "fetchmany(int(payload.get(\"max_rows\") or 1000) + 1)" in remote


def test_metadata_collector_clamps_probe_row():
    from app.services.metadata_collector import MetadataCollectorAdapter

    rows = [{"n": i} for i in range(6)]
    assert len(MetadataCollectorAdapter._clamp_rows(rows, 5)) == 5
    assert MetadataCollectorAdapter._clamp_rows(rows, 5)[-1] == {"n": 4}
