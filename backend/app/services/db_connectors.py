"""P5.5 数据库连接工厂抽象基类"""

from abc import ABC, abstractmethod
import base64
import json
import os
import re
import subprocess
from typing import Any


MAX_READONLY_ROWS = 10_000
DEFAULT_TIMEOUT_MS = 60_000
# Metadata is not always available before a query is issued. Keep this known
# hundred-million-row HIS table protected by default; callers can add sources
# through the connector's large_tables option.
DEFAULT_LARGE_TABLES = {"HIS.LAB_RESULT"}
_FORBIDDEN_SQL = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|MERGE|UPSERT|CREATE|ALTER|DROP|TRUNCATE|"
    r"GRANT|REVOKE|EXEC(?:UTE)?|CALL|COPY|VACUUM|ANALYZE)\b",
    re.IGNORECASE,
)
_LOCK_SQL = re.compile(r"\b(?:LOCK\s+TABLE|FOR\s+(?:UPDATE|SHARE)|LOCK\s+IN\s+SHARE\s+MODE)\b", re.IGNORECASE)


def validate_readonly_sql(sql: str, large_tables: set[str] | None = None) -> str:
    """Validate one portable, non-locking SELECT statement before it reaches a driver."""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("readonly SQL must not be empty")
    normalized = sql.strip()
    if ";" in normalized:
        raise ValueError("readonly SQL must contain exactly one statement")
    if "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise ValueError("readonly SQL comments are not allowed")
    if not re.match(r"^(?:SELECT|WITH)\b", normalized, re.IGNORECASE):
        raise ValueError("readonly SQL must start with SELECT or WITH")
    if _FORBIDDEN_SQL.search(normalized):
        raise ValueError("readonly SQL contains a forbidden write or DDL keyword")
    if re.search(r"\bSELECT\b[\s\S]*?\bINTO\b", normalized, re.IGNORECASE):
        raise ValueError("readonly SQL must not use SELECT INTO")
    if _LOCK_SQL.search(normalized):
        raise ValueError("readonly SQL must not acquire locks")

    protected_tables = DEFAULT_LARGE_TABLES | {table.upper() for table in (large_tables or set())}
    referenced_tables = {
        match.group(1).upper().strip('"`[]')
        for match in re.finditer(r"\b(?:FROM|JOIN)\s+([\w.$\"`\[\]]+)", normalized, re.IGNORECASE)
    }
    if protected_tables.intersection(referenced_tables) and not re.search(r"\bWHERE\b", normalized, re.IGNORECASE):
        raise ValueError("a WHERE clause is required when querying a configured large table")
    return normalized


class DatabaseConnector(ABC):
    """多数据库连接适配器抽象基类。

    每种数据库类型实现一个子类，提供统一的只读连接接口。
    子类负责处理：thick 模式、连接池、超时、行数限制、驱动差异。
    """

    db_type: str = "unknown"

    def __init__(self, host: str, port: int, database: str, user: str = "", password: str = "",
                 connection_mode: str = "direct", **kwargs):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection_mode = connection_mode
        self.extra = kwargs

    def _safe_max_rows(self, max_rows: int) -> int:
        return max(1, min(int(max_rows or 1000), MAX_READONLY_ROWS))

    def _timeout_ms(self) -> int:
        return max(1, int(self.extra.get("timeout_ms") or DEFAULT_TIMEOUT_MS))

    def _validate_readonly_sql(self, sql: str) -> str:
        configured_tables = self.extra.get("large_tables") or []
        if isinstance(configured_tables, str):
            configured_tables = configured_tables.split(",")
        return validate_readonly_sql(sql, {str(table).strip() for table in configured_tables if str(table).strip()})

    @abstractmethod
    def connect(self) -> Any:
        """建立只读连接，返回驱动原生 connection 对象。"""
        ...
    @abstractmethod
    def close(self) -> None:
        """关闭连接。"""
        ...

    @abstractmethod
    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        """执行只读查询，返回 [{col: val, ...}] 列表。"""
        ...

    @abstractmethod
    def fetch_metadata(self) -> dict:
        """采集元数据，返回 {"schemas": [...], "tables": [...], "columns": [...]} 结构。"""
        ...

    @abstractmethod
    def test_connectivity(self) -> tuple[bool, str, float]:
        """连通性检测，返回 (成功, 错误信息, 耗时ms)。"""
        ...


class OracleConnector(DatabaseConnector):
    """Oracle 数据库连接器（thick 模式）。"""

    db_type = "oracle"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conn = None

    def _ssh_options(self) -> dict:
        return {
            "jump_host": self.extra.get("jump_host") or os.environ.get("APP_SSH_JUMP_HOST") or "10.10.8.53",
            "jump_port": str(self.extra.get("jump_port") or os.environ.get("APP_SSH_JUMP_PORT") or "40022"),
            "jump_user": self.extra.get("jump_user") or os.environ.get("APP_SSH_JUMP_USER") or "dataasset",
            "jump_key": self.extra.get("jump_key") or os.environ.get("APP_SSH_JUMP_KEY") or os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519_ai"),
            "known_hosts": self.extra.get("known_hosts") or os.environ.get("APP_SSH_KNOWN_HOSTS") or os.path.join(os.path.expanduser("~"), ".ssh", "known_hosts"),
            # 8.83 容器内客户端在 /opt/oracle（含 19.1）；跳板机历史路径为 instantclient_21
            "oracle_client_lib_dir": self.extra.get("oracle_client_lib_dir")
            or os.environ.get("APP_ORACLE_CLIENT_LIB_DIR")
            or ("/opt/oracle" if os.path.isdir("/opt/oracle") else "/opt/oracle/instantclient_21"),
        }

    def _run_via_ssh_jump(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        sql = self._validate_readonly_sql(sql)
        safe_limit = self._safe_max_rows(max_rows)
        remote_script = r"""
import datetime
import decimal
import json
import sys

import oracledb


def normalize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


payload = json.loads(sys.stdin.read())
oracledb.init_oracle_client(lib_dir=payload["oracle_client_lib_dir"])
conn = oracledb.connect(
    user=payload["user"],
    password=payload["password"],
    dsn=f'{payload["host"]}:{payload["port"]}/{payload["database"]}',
)
conn.call_timeout = int(payload.get("timeout_ms") or 60000)
cur = None
try:
    cur = conn.cursor()
    cur.execute("SET TRANSACTION READ ONLY")
    cur.execute(payload["sql"], payload.get("params") or {})
    rows = cur.fetchmany(int(payload.get("max_rows") or 1000))
    cols = [d[0] for d in cur.description]
    print(json.dumps([
        {col: normalize(value) for col, value in zip(cols, row)}
        for row in rows
    ], ensure_ascii=False))
finally:
    if cur is not None:
        cur.close()
    conn.close()
"""
        opts = self._ssh_options()
        encoded_script = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
        remote_cmd = f"python3 -c \"import base64; exec(base64.b64decode('{encoded_script}'))\""
        cmd = [
            "ssh",
            "-p", opts["jump_port"],
            "-i", opts["jump_key"],
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={opts['known_hosts']}",
            "-o", "ConnectTimeout=10",
            f"{opts['jump_user']}@{opts['jump_host']}",
            remote_cmd,
        ]
        payload = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "sql": sql,
            "params": params or {},
            "max_rows": safe_limit,
            "timeout_ms": self._timeout_ms(),
            "oracle_client_lib_dir": opts["oracle_client_lib_dir"],
        }
        completed = subprocess.run(
            cmd,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=int(self.extra.get("timeout") or os.environ.get("APP_ORACLE_SSH_TIMEOUT") or "60"),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "ssh oracle query failed")[:500])
        stdout = completed.stdout.strip()
        if not stdout:
            return []
        return json.loads(stdout.splitlines()[-1])
    def connect(self) -> Any:
        if self.connection_mode == "ssh_jump":
            return None
        import oracledb
        # Oracle 11g thick 模式：必须初始化 Instant Client
        lib_dir = (
            self.extra.get("oracle_client_lib_dir")
            or os.environ.get("APP_ORACLE_CLIENT_LIB_DIR")
            or ("/opt/oracle" if os.path.isdir("/opt/oracle") else "/opt/oracle/instantclient_21")
        )
        try:
            oracledb.init_oracle_client(lib_dir=lib_dir)
        except Exception:
            pass  # 已初始化或路径无效，继续尝试连接
        # Bound the TCP handshake as well as statement execution. Without this,
        # an unreachable business source can hang a read-only inventory run.
        dsn = oracledb.ConnectParams(
            host=self.host,
            port=self.port,
            service_name=self.database,
            tcp_connect_timeout=max(1.0, self._timeout_ms() / 1000),
            retry_count=0,
        )
        self._conn = oracledb.connect(
            user=self.user, password=self.password, params=dsn,
        )
        self._conn.call_timeout = self._timeout_ms()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        if self.connection_mode == "ssh_jump":
            return self._run_via_ssh_jump(sql, params=params, max_rows=max_rows)
        sql = self._validate_readonly_sql(sql)
        safe_limit = self._safe_max_rows(max_rows)
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            self._conn.call_timeout = self._timeout_ms()
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(sql, params or {})
            rows = cursor.fetchmany(safe_limit)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]
        finally:
            cursor.close()
            # End the read-only transaction so the next query can begin one.
            self._conn.rollback()

    def fetch_metadata(self) -> dict:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            self._conn.call_timeout = self._timeout_ms()
            cursor.execute("SET TRANSACTION READ ONLY")
            tables = []
            cursor.execute(
                "SELECT owner, table_name, num_rows FROM all_tables WHERE owner NOT IN "
                "('SYS','SYSTEM','XDB','MDSYS','CTXSYS','OLAPSYS','ORDSYS','ORDPLUGINS','OUTLN','WMSYS') "
                "AND ROWNUM <= 5000"
            )
            for row in cursor.fetchall():
                tables.append({"owner": row[0], "table_name": row[1], "num_rows": row[2]})
            columns = []
            cursor.execute(
                "SELECT owner, table_name, column_name, data_type, data_length, nullable "
                "FROM all_tab_columns WHERE owner NOT IN ('SYS','SYSTEM') AND ROWNUM <= 100000"
            )
            for row in cursor.fetchall():
                columns.append({
                    "owner": row[0], "table_name": row[1], "column_name": row[2],
                    "data_type": row[3], "data_length": row[4], "nullable": row[5],
                })
            return {"tables": tables, "columns": columns}
        finally:
            cursor.close()
            self._conn.rollback()

    def test_connectivity(self) -> tuple[bool, str, float]:
        import time
        start = time.perf_counter()
        try:
            if self.connection_mode == "ssh_jump":
                self._run_via_ssh_jump("SELECT 1 AS OK FROM dual", max_rows=1)
            else:
                self.connect()
                self._conn.ping()
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return True, "connected", elapsed
        except Exception as e:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return False, str(e)[:200], elapsed
        finally:
            self.close()


class PostgresConnector(DatabaseConnector):
    """PostgreSQL 数据库连接器。"""

    db_type = "postgresql"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conn = None

    def connect(self):
        import psycopg
        self._conn = psycopg.connect(
            host=self.host, port=self.port, dbname=self.database,
            user=self.user, password=self.password,
            options=f"-c statement_timeout={self._timeout_ms()}",
        )
        self._conn.execute("BEGIN READ ONLY")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        import psycopg.rows
        sql = self._validate_readonly_sql(sql)
        if not self._conn:
            self.connect()
        safe_limit = self._safe_max_rows(max_rows)
        cursor = self._conn.cursor(row_factory=psycopg.rows.dict_row)
        try:
            cursor.execute(sql, params or {})
            return cursor.fetchmany(safe_limit)
        finally:
            cursor.close()

    def fetch_metadata(self) -> dict:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
                "AND table_type='BASE TABLE' LIMIT 5000"
            )
            tables = [{"owner": r[0], "table_name": r[1]} for r in cursor.fetchall()]
            cursor.execute(
                "SELECT table_schema, table_name, column_name, data_type, character_maximum_length, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema') LIMIT 100000"
            )
            columns = [{
                "owner": r[0], "table_name": r[1], "column_name": r[2],
                "data_type": r[3], "data_length": r[4], "nullable": r[5],
            } for r in cursor.fetchall()]
            return {"tables": tables, "columns": columns}
        finally:
            cursor.close()

    def test_connectivity(self) -> tuple[bool, str, float]:
        import time
        start = time.perf_counter()
        try:
            self.connect()
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return True, "connected", elapsed
        except Exception as e:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return False, str(e)[:200], elapsed
        finally:
            self.close()


class MysqlConnector(DatabaseConnector):
    """MySQL 数据库连接器（使用 pymysql）。"""

    db_type = "mysql"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conn = None

    def connect(self):
        import pymysql
        self._conn = pymysql.connect(
            host=self.host, port=self.port, database=self.database,
            user=self.user, password=self.password,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=max(1, self._timeout_ms() // 1000),
            read_timeout=max(1, self._timeout_ms() // 1000),
            write_timeout=max(1, self._timeout_ms() // 1000),
        )
        cursor = self._conn.cursor()
        try:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("SET SESSION MAX_EXECUTION_TIME = %s", (self._timeout_ms(),))
            cursor.execute("START TRANSACTION READ ONLY")
        finally:
            cursor.close()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        sql = self._validate_readonly_sql(sql)
        if not self._conn:
            self.connect()
        safe_limit = self._safe_max_rows(max_rows)
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or {})
            return cursor.fetchmany(safe_limit)
        finally:
            cursor.close()

    def fetch_metadata(self) -> dict:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' LIMIT 5000")
            tables = [{"owner": r["TABLE_SCHEMA"], "table_name": r["TABLE_NAME"]} for r in cursor.fetchall()]
            cursor.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
                "FROM INFORMATION_SCHEMA.COLUMNS LIMIT 100000"
            )
            columns = [{
                "owner": r["TABLE_SCHEMA"], "table_name": r["TABLE_NAME"], "column_name": r["COLUMN_NAME"],
                "data_type": r["DATA_TYPE"], "data_length": r["CHARACTER_MAXIMUM_LENGTH"], "nullable": r["IS_NULLABLE"],
            } for r in cursor.fetchall()]
            return {"tables": tables, "columns": columns}
        finally:
            cursor.close()

    def test_connectivity(self) -> tuple[bool, str, float]:
        import time
        start = time.perf_counter()
        try:
            self.connect()
            self._conn.ping()
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return True, "connected", elapsed
        except Exception as e:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return False, str(e)[:200], elapsed
        finally:
            self.close()


class SqlServerConnector(DatabaseConnector):
    """SQL Server 连接器：优先 pyodbc(ODBC)，无驱动时回退 pymssql（只读探测）。"""

    db_type = "sqlserver"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conn = None
        self._driver = None  # "pyodbc" | "pymssql"

    def connect(self):
        timeout_s = max(1, self._timeout_ms() // 1000)
        # 1) pyodbc + ODBC Driver 17/18
        try:
            import pyodbc

            drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
            driver = drivers[0] if drivers else "ODBC Driver 17 for SQL Server"
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={self.host},{self.port};"
                f"DATABASE={self.database};"
                f"UID={self.user};PWD={self.password};"
                f"TrustServerCertificate=yes;"
                f"ApplicationIntent=ReadOnly;"
                f"Connection Timeout={timeout_s}"
            )
            self._conn = pyodbc.connect(conn_str)
            self._driver = "pyodbc"
            cursor = self._conn.cursor()
            try:
                cursor.timeout = timeout_s
                try:
                    cursor.execute("SET LOCK_TIMEOUT ?", (self._timeout_ms(),))
                except Exception:
                    pass
                try:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
                except Exception:
                    pass
            finally:
                cursor.close()
            return self._conn
        except Exception as pyodbc_err:
            # 2) pymssql fallback for environments without ODBC (plan 85 F8)
            try:
                import pymssql

                options = dict(
                    server=self.host,
                    port=str(self.port),
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    login_timeout=timeout_s,
                    timeout=timeout_s,
                    appname="data-asset-readonly",
                )
                try:
                    self._conn = pymssql.connect(**options)
                except Exception:
                    # Some legacy SQL Server installations only negotiate TDS 7.0.
                    # Keep this as a narrow connectivity fallback; all executed SQL
                    # remains subject to the same read-only validator and row limits.
                    self._conn = pymssql.connect(**options, tds_version="7.0")
                self._driver = "pymssql"
                return self._conn
            except Exception as pymssql_err:
                raise RuntimeError(
                    "sqlserver connector unavailable: install ODBC Driver + pyodbc "
                    f"or pymssql. pyodbc={type(pyodbc_err).__name__}; "
                    f"pymssql={type(pymssql_err).__name__}"
                ) from pymssql_err

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        sql = self._validate_readonly_sql(sql)
        if not self._conn:
            self.connect()
        safe_limit = self._safe_max_rows(max_rows)
        cursor = self._conn.cursor()
        try:
            if self._driver == "pyodbc":
                try:
                    cursor.timeout = max(1, self._timeout_ms() // 1000)
                except Exception:
                    pass
                cursor.execute(sql, params or {})
            else:
                # pymssql: only simple param tuples; prefer no named params for SELECT 1
                if params:
                    cursor.execute(sql, tuple(params.values()))
                else:
                    cursor.execute(sql)
            rows = cursor.fetchmany(safe_limit) if hasattr(cursor, "fetchmany") else cursor.fetchall()[:safe_limit]
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in rows]
        finally:
            cursor.close()

    def fetch_metadata(self) -> dict:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
            )
            tables = [{"owner": r[0], "table_name": r[1]} for r in cursor.fetchall()]
            cursor.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
                "FROM INFORMATION_SCHEMA.COLUMNS"
            )
            columns = [{
                "owner": r[0], "table_name": r[1], "column_name": r[2],
                "data_type": r[3], "data_length": r[4], "nullable": r[5],
            } for r in cursor.fetchall()]
            return {"tables": tables, "columns": columns}
        finally:
            cursor.close()

    def test_connectivity(self) -> tuple[bool, str, float]:
        import time
        start = time.perf_counter()
        try:
            self.connect()
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return True, f"connected via {self._driver}", elapsed
        except Exception as e:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            msg = str(e)[:200]
            for secret in filter(None, [self.password, self.user]):
                if secret and secret in msg:
                    msg = "sqlserver connectivity failed"
                    break
            return False, msg, elapsed
        finally:
            self.close()


class VastbaseConnector(PostgresConnector):
    """海量数据 Vastbase G100 连接器。

    Vastbase G100 兼容 PostgreSQL 协议，复用 psycopg 驱动。
    JDBC 驱动 (Vastbase-G100-2.15_pg) 存档于 drivers/ 供 Java 程序使用。
    """

    db_type = "vastbase"


DB_CONNECTOR_MAP = {
    "oracle": OracleConnector,
    "postgresql": PostgresConnector,
    "vastbase": VastbaseConnector,
    "mysql": MysqlConnector,
    "sqlserver": SqlServerConnector,
}
