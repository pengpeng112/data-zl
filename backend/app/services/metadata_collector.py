"""P5.5-T5/P5.9-T8: 元数据采集适配器抽象基类"""

from abc import ABC, abstractmethod
from typing import Any


class MetadataCollectorAdapter(ABC):
    """元数据采集适配器抽象基类。

    每种数据库实现一个子类，负责从该数据库采集 schema/owner、表、字段、类型、注释。
    P14/F46 的 diff 引擎依赖此接口产出的标准化结构。
    """

    db_type: str = "unknown"

    def __init__(self, connector: Any):
        self.connector = connector

    @staticmethod
    def _clamp_rows(rows: list, max_rows: int) -> list:
        """A4：连接器可能多返回 1 行探针；采集入口按声明上限夹紧。"""
        limit = max(1, int(max_rows))
        return list(rows)[:limit]

    @abstractmethod
    def list_schemas(self) -> list[dict]:
        """返回 [{"name": "HIS", "type": "schema"|"owner"}, ...]"""
        ...

    @abstractmethod
    def list_tables(self, schema_name: str) -> list[dict]:
        """返回 [{"table_name": "...", "row_count": N, "comment": "..."}, ...]"""
        ...

    @abstractmethod
    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        """返回 [{"column_name": "...", "data_type": "...", "length": N,
                   "nullable": "Y"|"N", "comment": "...", "is_primary_key": bool}, ...]"""
        ...

    def collect_all(self, schema_filter: list[str] | None = None) -> dict:
        """全量采集：schemas → tables → columns 三层结构。

        若传入 schema_filter，优先直接使用（不依赖 list_schemas 的抽样），
        避免 Oracle ROWNUM 截断导致业务 owner 被漏掉。
        """
        if schema_filter:
            schemas = [{"name": name, "type": "owner"} for name in schema_filter if name]
        else:
            schemas = self.list_schemas()
        result: dict[str, list] = {"schemas": [], "tables": [], "columns": []}
        for schema in schemas:
            schema_name = schema["name"]
            result["schemas"].append(schema)
            tables = self.list_tables(schema_name)
            for table in tables:
                table["schema_name"] = schema_name
                result["tables"].append(table)
                columns = self.list_columns(schema_name, table["table_name"])
                for col in columns:
                    col["schema_name"] = schema_name
                    col["table_name"] = table["table_name"]
                result["columns"].extend(columns)
        return result


class OracleMetadataCollector(MetadataCollectorAdapter):
    """Oracle 元数据采集适配器。"""

    db_type = "oracle"
    _BATCH_TABLES = 40

    def list_schemas(self) -> list[dict]:
        # 用 all_users 列举 owner，避免 all_tables + ROWNUM 截断漏掉业务 schema
        rows = self.connector.execute_readonly(
            "SELECT username AS owner FROM all_users WHERE username NOT IN "
            "('SYS','SYSTEM','XDB','MDSYS','CTXSYS','OLAPSYS','ORDSYS','ORDPLUGINS','OUTLN','WMSYS',"
            "'DBSNMP','APPQOSSYS','ORACLE_OCM','DIP','ANONYMOUS','XS$NULL','SPATIAL_CSW_ADMIN_USR',"
            "'SPATIAL_WFS_ADMIN_USR','SI_INFORMTN_SCHEMA','ORDDATA','APEX_030200','FLOWS_FILES','OWBSYS') "
            "ORDER BY username",
            max_rows=500,
        )
        rows = self._clamp_rows(rows, 500)
        return [{"name": r.get("OWNER") or r.get("owner"), "type": "owner"} for r in rows if r.get("OWNER") or r.get("owner")]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT table_name, num_rows FROM all_tables WHERE owner = :owner ORDER BY table_name",
            {"owner": schema_name},
            max_rows=5000,
        )
        rows = self._clamp_rows(rows, 5000)
        return [
            {
                "table_name": r.get("TABLE_NAME") or r.get("table_name"),
                "row_count": r.get("NUM_ROWS") if "NUM_ROWS" in r else r.get("num_rows"),
                "comment": "",
            }
            for r in rows
        ]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT column_name, data_type, data_length, nullable "
            "FROM all_tab_columns WHERE owner = :owner AND table_name = :table "
            "ORDER BY column_id",
            {"owner": schema_name, "table": table_name},
            max_rows=10000,
        )
        rows = self._clamp_rows(rows, 10000)
        return [self._column_row(r) for r in rows]

    @staticmethod
    def _column_row(r: dict) -> dict:
        col = r.get("COLUMN_NAME") or r.get("column_name")
        dtype = r.get("DATA_TYPE") or r.get("data_type")
        length = r.get("DATA_LENGTH") if "DATA_LENGTH" in r else r.get("data_length")
        nullable = r.get("NULLABLE") if "NULLABLE" in r else r.get("nullable")
        return {
            "column_name": col,
            "data_type": dtype,
            "length": length,
            "nullable": "Y" if nullable == "Y" else "N",
            "comment": "",
            "is_primary_key": False,
        }

    def collect_all(self, schema_filter: list[str] | None = None) -> dict:
        """Oracle 按 owner 批量采列，避免每表一查过慢，并绕开 ROWNUM 漏 schema。"""
        if schema_filter:
            schemas = [{"name": name, "type": "owner"} for name in schema_filter if name]
        else:
            schemas = self.list_schemas()
        result: dict[str, list] = {"schemas": [], "tables": [], "columns": []}
        for schema in schemas:
            schema_name = schema["name"]
            result["schemas"].append(schema)
            tables = self.list_tables(schema_name)
            for table in tables:
                table["schema_name"] = schema_name
                result["tables"].append(table)
            names = [t["table_name"] for t in tables if t.get("table_name")]
            for i in range(0, len(names), self._BATCH_TABLES):
                batch = names[i : i + self._BATCH_TABLES]
                # 绑定 IN 列表（只读元数据）
                binds = {f"t{j}": name for j, name in enumerate(batch)}
                in_list = ", ".join(f":t{j}" for j in range(len(batch)))
                sql = (
                    "SELECT table_name, column_name, data_type, data_length, nullable "
                    f"FROM all_tab_columns WHERE owner = :owner AND table_name IN ({in_list}) "
                    "ORDER BY table_name, column_id"
                )
                binds["owner"] = schema_name
                rows = self._clamp_rows(
                    self.connector.execute_readonly(sql, binds, max_rows=10000), 10000
                )
                for r in rows:
                    col = self._column_row(r)
                    col["schema_name"] = schema_name
                    col["table_name"] = r.get("TABLE_NAME") or r.get("table_name")
                    result["columns"].append(col)
        return result


class PostgresMetadataCollector(MetadataCollectorAdapter):
    """PostgreSQL 元数据采集适配器。"""

    db_type = "postgresql"

    def list_schemas(self) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT DISTINCT table_schema FROM information_schema.tables "
            "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
            "AND table_type='BASE TABLE'",
            max_rows=500,
        )
        rows = self._clamp_rows(rows, 500)
        return [{"name": r["table_schema"], "type": "schema"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type='BASE TABLE'",
            {"schema": schema_name}, max_rows=5000,
        )
        rows = self._clamp_rows(rows, 5000)
        return [{"table_name": r["table_name"], "row_count": None, "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT column_name, data_type, character_maximum_length, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table",
            {"schema": schema_name, "table": table_name},
            max_rows=10000,
        )
        rows = self._clamp_rows(rows, 10000)
        return [{
            "column_name": r["column_name"], "data_type": r["data_type"],
            "length": r.get("character_maximum_length"),
            "nullable": "Y" if r.get("is_nullable") == "YES" else "N",
            "comment": "", "is_primary_key": False,
        } for r in rows]


class MysqlMetadataCollector(MetadataCollectorAdapter):
    """MySQL 元数据采集适配器。"""

    db_type = "mysql"

    def list_schemas(self) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT DISTINCT TABLE_SCHEMA FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'",
            max_rows=500,
        )
        rows = self._clamp_rows(rows, 500)
        return [{"name": r["TABLE_SCHEMA"], "type": "schema"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE='BASE TABLE'",
            {"schema": schema_name}, max_rows=5000,
        )
        rows = self._clamp_rows(rows, 5000)
        return [{"table_name": r["TABLE_NAME"], "row_count": None, "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table",
            {"schema": schema_name, "table": table_name},
            max_rows=10000,
        )
        rows = self._clamp_rows(rows, 10000)
        return [{
            "column_name": r["COLUMN_NAME"], "data_type": r["DATA_TYPE"],
            "length": r.get("CHARACTER_MAXIMUM_LENGTH"),
            "nullable": "Y" if r.get("IS_NULLABLE") == "YES" else "N",
            "comment": "", "is_primary_key": False,
        } for r in rows]


class SqlServerMetadataCollector(MetadataCollectorAdapter):
    """SQL Server 元数据采集适配器。"""

    db_type = "sqlserver"

    def list_schemas(self) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT DISTINCT TABLE_SCHEMA FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'",
            max_rows=500,
        )
        rows = self._clamp_rows(rows, 500)
        return [{"name": r["TABLE_SCHEMA"], "type": "schema"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_TYPE='BASE TABLE'",
            {"schema": schema_name}, max_rows=5000,
        )
        rows = self._clamp_rows(rows, 5000)
        return [{"table_name": r["TABLE_NAME"], "row_count": None, "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
            {"schema": schema_name, "table": table_name},
            max_rows=10000,
        )
        rows = self._clamp_rows(rows, 10000)
        return [{
            "column_name": r["COLUMN_NAME"], "data_type": r["DATA_TYPE"],
            "length": r.get("CHARACTER_MAXIMUM_LENGTH"),
            "nullable": "Y" if r.get("IS_NULLABLE") == "YES" else "N",
            "comment": "", "is_primary_key": False,
        } for r in rows]


METADATA_COLLECTOR_MAP = {
    "oracle": OracleMetadataCollector,
    "postgresql": PostgresMetadataCollector,
    "mysql": MysqlMetadataCollector,
    "sqlserver": SqlServerMetadataCollector,
}
