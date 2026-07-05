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
        """全量采集：schemas → tables → columns 三层结构。"""
        schemas = self.list_schemas()
        if schema_filter:
            schemas = [s for s in schemas if s["name"] in schema_filter]
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

    def list_schemas(self) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT DISTINCT owner FROM all_tables WHERE owner NOT IN "
            "('SYS','SYSTEM','XDB','MDSYS','CTXSYS','OLAPSYS','ORDSYS','ORDPLUGINS','OUTLN','WMSYS') "
            "AND ROWNUM <= 500"
        )
        return [{"name": r["OWNER"], "type": "owner"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT table_name, num_rows FROM all_tables WHERE owner = :owner AND ROWNUM <= 5000",
            {"owner": schema_name},
        )
        return [{"table_name": r["TABLE_NAME"], "row_count": r.get("NUM_ROWS"), "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT column_name, data_type, data_length, nullable "
            "FROM all_tab_columns WHERE owner = :owner AND table_name = :table",
            {"owner": schema_name, "table": table_name},
        )
        return [
            {
                "column_name": r["COLUMN_NAME"],
                "data_type": r["DATA_TYPE"],
                "length": r.get("DATA_LENGTH"),
                "nullable": "Y" if r.get("NULLABLE") == "Y" else "N",
                "comment": "",
                "is_primary_key": False,
            }
            for r in rows
        ]


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
        return [{"name": r["table_schema"], "type": "schema"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type='BASE TABLE'",
            {"schema": schema_name}, max_rows=5000,
        )
        return [{"table_name": r["table_name"], "row_count": None, "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT column_name, data_type, character_maximum_length, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table",
            {"schema": schema_name, "table": table_name},
        )
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
        return [{"name": r["TABLE_SCHEMA"], "type": "schema"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE='BASE TABLE'",
            {"schema": schema_name}, max_rows=5000,
        )
        return [{"table_name": r["TABLE_NAME"], "row_count": None, "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table",
            {"schema": schema_name, "table": table_name},
        )
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
        return [{"name": r["TABLE_SCHEMA"], "type": "schema"} for r in rows]

    def list_tables(self, schema_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_TYPE='BASE TABLE'",
            {"schema": schema_name}, max_rows=5000,
        )
        return [{"table_name": r["TABLE_NAME"], "row_count": None, "comment": ""} for r in rows]

    def list_columns(self, schema_name: str, table_name: str) -> list[dict]:
        rows = self.connector.execute_readonly(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
            {"schema": schema_name, "table": table_name},
        )
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
