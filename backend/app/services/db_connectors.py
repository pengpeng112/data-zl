"""P5.5 数据库连接工厂抽象基类"""

from abc import ABC, abstractmethod
from typing import Any


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

    def connect(self) -> Any:
        import oracledb
        # Oracle 11g thick 模式：必须初始化 Instant Client
        lib_dir = self.extra.get("oracle_client_lib_dir") or "/opt/oracle/instantclient_21"
        try:
            oracledb.init_oracle_client(lib_dir=lib_dir)
        except Exception:
            pass  # 已初始化或路径无效，继续尝试连接
        dsn = f"{self.host}:{self.port}/{self.database}"
        self._conn = oracledb.connect(
            user=self.user, password=self.password, dsn=dsn,
        )
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or {})
            rows = cursor.fetchmany(max_rows)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]
        finally:
            cursor.close()

    def fetch_metadata(self) -> dict:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
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
        )
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        import psycopg.rows
        if not self._conn:
            self.connect()
        safe_limit = max(1, min(int(max_rows), 10000))
        cursor = self._conn.cursor(row_factory=psycopg.rows.dict_row)
        try:
            cursor.execute(sql + " LIMIT %s", [safe_limit])
            return cursor.fetchall()
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
        )
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        if not self._conn:
            self.connect()
        safe_limit = max(1, min(int(max_rows), 10000))
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql + " LIMIT %s", [safe_limit])
            return cursor.fetchall()
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
    """SQL Server 数据库连接器（使用 pyodbc）。"""

    db_type = "sqlserver"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conn = None

    def connect(self):
        import pyodbc
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.user};PWD={self.password};"
            f"TrustServerCertificate=yes"
        )
        self._conn = pyodbc.connect(conn_str)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_readonly(self, sql: str, params: dict | None = None, max_rows: int = 1000) -> list[dict]:
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or {})
            rows = cursor.fetchmany(max_rows)
            cols = [d[0] for d in cursor.description]
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
            self._conn.cursor().execute("SELECT 1")
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return True, "connected", elapsed
        except Exception as e:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return False, str(e)[:200], elapsed
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
