"""扩表A1：freeze_batch 生成器 + sqlserver/mysql 源工厂扩展（纯逻辑）。

覆盖 2026-10-24 扩表工程项：
- SqlServer/MySQL 投影查询构建（TOP/LIMIT 限量 + 序内 keyset）；
- 连接工厂 dsn/凭据校验拒绝语义；
- B01 v1.3 逐表批冻结：字段约定与首组 v4 同构、装载即验指纹；
- 拒绝语义：工单表/未核目标身份/缺源绑定/键不在投影/ODS 视图覆盖缺口。
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.freeze_batch import (  # noqa: E402
    DEFAULT_BUDGET,
    FreezeBatchError,
    build_batch_freeze,
)
from app.services.reporting_pipeline.runtime_config import (  # noqa: E402
    load_frozen_runtime_config,
)
from app.services.reporting_pipeline.source_factory import (  # noqa: E402
    MySqlProjectionQueryBuilder,
    SqlServerProjectionQueryBuilder,
    SourceFactoryError,
    build_connection_factory,
)


@dataclass
class _FakeField:
    name: str
    source_expression: str
    target_type: str = "VARCHAR2(50)"
    order: int = 0


@dataclass
class _FakeSpec:
    canonical_table: str
    source_object: str
    projection: list = field(default_factory=list)
    anchor_column: str = "DATETIME"
    stable_key: tuple = ("ID",)
    dialect: str = "sqlserver"


def _spec(dialect: str) -> _FakeSpec:
    return _FakeSpec(
        canonical_table="T1",
        source_object="dbo.T1" if dialect == "sqlserver" else "v_t1",
        dialect=dialect,
        projection=[
            _FakeField("ID", "ID", "VARCHAR2(50)", 1),
            _FakeField("NAME", "NAME", "VARCHAR2(100)", 2),
            _FakeField("DATETIME", "DATETIME", "DATE", 3),
        ],
    )


def _window():
    tz = timezone(timedelta(hours=8))
    return (
        datetime(2026, 10, 23, 0, 0, tzinfo=tz),
        datetime(2026, 10, 24, 0, 0, tzinfo=tz),
    )


class _FakeWindow:
    def __init__(self) -> None:
        start, end = _window()
        self.start = start
        self.end_exclusive = end


class TestSqlServerQueryBuilder(unittest.TestCase):
    def test_top_first_param_limit_then_window(self):
        sql, params = SqlServerProjectionQueryBuilder(_spec("sqlserver"))(
            _FakeWindow(), None, 500
        )
        self.assertTrue(sql.startswith("SELECT TOP (%s) ID, NAME, DATETIME FROM dbo.T1"))
        self.assertIn("WHERE DATETIME >= %s AND DATETIME < %s", sql)
        self.assertTrue(sql.endswith("ORDER BY ID"))
        self.assertEqual(params, [500, datetime(2026, 10, 23, 0, 0), datetime(2026, 10, 24, 0, 0)])

    def test_keyset_predicate_appended(self):
        from app.services.reporting_pipeline.planner import KeysetCursor

        keyset = KeysetCursor(order_columns=("ID",), last_values=("A10",), unique_verified=True)
        sql, params = SqlServerProjectionQueryBuilder(_spec("sqlserver"))(
            _FakeWindow(), keyset, 100
        )
        self.assertIn("(ID > %s)", sql)
        self.assertEqual(params[-1], "A10")
        self.assertEqual(len(params), 4)

    def test_keyset_mismatch_refused(self):
        from app.services.reporting_pipeline.planner import KeysetCursor

        keyset = KeysetCursor(order_columns=("OTHER",), last_values=("A10",), unique_verified=True)
        with self.assertRaises(SourceFactoryError):
            SqlServerProjectionQueryBuilder(_spec("sqlserver"))(_FakeWindow(), keyset, 100)


class TestMySqlQueryBuilder(unittest.TestCase):
    def test_limit_last_param(self):
        sql, params = MySqlProjectionQueryBuilder(_spec("mysql"))(
            _FakeWindow(), None, 500
        )
        self.assertTrue(sql.startswith("SELECT ID, NAME, DATETIME FROM v_t1"))
        self.assertTrue(sql.endswith("ORDER BY ID LIMIT %s"))
        self.assertEqual(params[-1], 500)
        self.assertEqual(params[:2], [datetime(2026, 10, 23, 0, 0), datetime(2026, 10, 24, 0, 0)])

    def test_keyset_predicate(self):
        from app.services.reporting_pipeline.planner import KeysetCursor

        keyset = KeysetCursor(order_columns=("ID",), last_values=("K9",), unique_verified=True)
        sql, params = MySqlProjectionQueryBuilder(_spec("mysql"))(
            _FakeWindow(), keyset, 10
        )
        self.assertIn("(ID > %s)", sql)
        self.assertEqual(params[-2], "K9")


class TestConnectionFactoryDialects(unittest.TestCase):
    def test_sqlserver_requires_dsn_database(self):
        with self.assertRaises(SourceFactoryError):
            build_connection_factory(
                dialect="sqlserver", dsn="10.10.9.41:1433", credential_ref="container-credentials:x"
            )

    def test_mysql_requires_dsn_database(self):
        with self.assertRaises(SourceFactoryError):
            build_connection_factory(
                dialect="mysql", dsn="10.10.10.50:3306", credential_ref="container-credentials:x"
            )

    def test_sqlserver_missing_credential_ref_refused(self):
        with self.assertRaises(SourceFactoryError):
            build_connection_factory(dialect="sqlserver", dsn="10.10.9.41:1433/pitaya")

    def test_unknown_dialect_refused(self):
        with self.assertRaises(SourceFactoryError):
            build_connection_factory(dialect="mongodb", dsn="x", credential_ref="y")


# -- 批冻结生成器 ------------------------------------------------------------


def _b01_item(name: str, **overrides) -> dict:
    item = {
        "canonical_table": name,
        "business_name": f"{name}业务名",
        "source_candidates": [{
            "object_id": f"src__{name}", "role": "primary", "source_group": "infection",
            "host": "10.10.9.45", "port": 1521, "database_hint": "orcl",
            "owner_hint": "C##FXPT", "object_name_candidates": [name], 
        }],
        "target_candidate": {
            "host": "10.10.8.74", "port": 1521, "service": "orcl",
            "owner": "DBOPER", "table": name, "current_identity_verified": True,
        },
        "stable_key": {"candidate": ["ID"], "verified": True},
        "declared_parent_candidates": [],
        "b01_verification": {
            "target_identity": {"verified": True},
            "anchor": [{"column": "DATETIME", "verified": True, "views": [name]}],
            "stable_key": {"candidate": ["ID"], "verified": True},
            "engine_disposition": "PYTHON_PLANNED",
        },
    }
    item.update(overrides)
    return item


def _target_cols() -> dict:
    return {
        "T_SRC_A": [
            {"name": "ID", "target_type": "VARCHAR2(50)", "nullable": False, "data_length": 50},
            {"name": "NAME", "target_type": "VARCHAR2(100)", "nullable": True, "data_length": 100},
            {"name": "DATETIME", "target_type": "DATE", "nullable": True, "data_length": 7},
            {"name": "SYSTEM_TIME", "target_type": "DATE", "nullable": True, "data_length": 7},
        ],
    }


def _bindings() -> dict:
    return {
        "infection": {
            "dialect": "oracle",
            "dsn": "10.10.9.45:1521/orcl",
            "credential_ref": "container-credentials:infection_oracle_10_10_9_45.readonly",
            "source_objects": {"T_SRC_A": "C##FXPT.T_SRC_A"},
        },
    }


class TestBuildBatchFreeze(unittest.TestCase):
    def _run(self, **kwargs):
        defaults = dict(
            environment="production",
            batch_label="批UT",
            b01_items=[_b01_item("T_SRC_A")],
            table_names=["T_SRC_A"],
            target_columns=_target_cols(),
            source_bindings=_bindings(),
            target_overrides={},
            frozen_at="2026-10-24T15:00:00+08:00",
        )
        defaults.update(kwargs)
        return build_batch_freeze(**defaults)

    def test_happy_path_loads_and_matches_v4_convention(self):
        import json
        import tempfile

        document, report = self._run()
        table = document["tables"]["T_SRC_A"]
        self.assertEqual(table["source"]["dialect"], "oracle")
        self.assertEqual(table["source"]["object"], "C##FXPT.T_SRC_A")
        self.assertEqual(table["anchor"]["column"], "DATETIME")
        self.assertEqual(table["system_time_column"], "SYSTEM_TIME")
        # SYSTEM_TIME 剔出装载投影；稳定键在投影内
        names = {p["name"] for p in table["projection"]}
        self.assertNotIn("SYSTEM_TIME", names)
        self.assertIn("ID", names)
        self.assertEqual(table["target"]["charset"], "ZHS16GBK")
        self.assertEqual(table["budget"], dict(DEFAULT_BUDGET))
        self.assertEqual(
            report["tables"]["T_SRC_A"]["source_object"], "C##FXPT.T_SRC_A"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(document, handle, ensure_ascii=False)
            path = handle.name
        loaded = load_frozen_runtime_config(path)
        self.assertIn("T_SRC_A", loaded.tables)
        Path(path).unlink()

    def test_ticket_table_refused(self):
        with self.assertRaises(FreezeBatchError) as ctx:
            self._run(
                b01_items=[_b01_item("EMR_NURSE_PLAN")],
                table_names=["EMR_NURSE_PLAN"],
                target_columns={"EMR_NURSE_PLAN": _target_cols()["T_SRC_A"]},
                source_bindings={
                    "infection": {
                        **_bindings()["infection"],
                        "source_objects": {"EMR_NURSE_PLAN": "C##FXPT.EMR_NURSE_PLAN"},
                    }
                },
            )
        self.assertIn("T-B01-61", str(ctx.exception))

    def test_unverified_target_identity_refused(self):
        item = _b01_item("T_SRC_A")
        item["b01_verification"]["target_identity"] = {"verified": False}
        with self.assertRaises(FreezeBatchError):
            self._run(b01_items=[item])

    def test_missing_source_binding_refused(self):
        with self.assertRaises(FreezeBatchError):
            self._run(source_bindings={})

    def test_stable_key_outside_projection_refused(self):
        cols = {
            "T_SRC_A": [
                {"name": "NAME", "target_type": "VARCHAR2(100)", "nullable": True, "data_length": 100},
            ],
        }
        with self.assertRaises(FreezeBatchError) as ctx:
            self._run(target_columns=cols)
        self.assertIn("稳定键列不在投影中", str(ctx.exception))

    def test_parent_key_must_be_in_projection(self):
        item = _b01_item("T_SRC_A")
        item["declared_parent_candidates"] = [{
            "parent": "EMR_ICH", "child_key": "ICH_ID", "parent_key": "ID",
        }]
        with self.assertRaises(FreezeBatchError) as ctx:
            self._run(b01_items=[item])
        self.assertIn("父键列不在投影中", str(ctx.exception))

    def test_ods_view_coverage_gap_refused_and_allow_gap_notes(self):
        item = _b01_item("T_SRC_A")
        item["source_candidates"][0]["source_group"] = "ods_8_216"
        bindings = {
            "ods_8_216": {
                "dialect": "oracle",
                "dsn": "10.10.8.216:1521/orcl",
                "credential_ref": "container-credentials:ods_8_216",
                "source_objects": {"T_SRC_A": "ODS.V_T_SRC_A"},
                "view_by_table": {"T_SRC_A": "V_T_SRC_A"},
            },
        }
        # 视图别名缺 NAME → 覆盖缺口默认拒绝
        with self.assertRaises(FreezeBatchError) as ctx:
            self._run(b01_items=[item], source_bindings=bindings, view_aliases_by_name={"V_T_SRC_A": {"ID", "DATETIME"}})
        self.assertIn("覆盖", str(ctx.exception))
        # allow_view_gap 强制冻结并留痕
        document, report = self._run(
            b01_items=[item],
            source_bindings=bindings,
            view_aliases_by_name={"V_T_SRC_A": {"ID", "DATETIME"}},
            allow_view_gap=True,
        )
        self.assertTrue(report["coverage_problems"])
        table = document["tables"]["T_SRC_A"]
        self.assertIn("missing=1", table["notes"]["view_column_coverage"])

    def test_ods_view_without_ddl_evidence_refused(self):
        item = _b01_item("T_SRC_A")
        item["source_candidates"][0]["source_group"] = "ods_8_216"
        bindings = {
            "ods_8_216": {
                "dialect": "oracle",
                "dsn": "10.10.8.216:1521/orcl",
                "credential_ref": "container-credentials:ods_8_216",
                "source_objects": {"T_SRC_A": "ODS.V_T_SRC_A"},
                "view_by_table": {"T_SRC_A": "V_T_SRC_A"},
            },
        }
        with self.assertRaises(FreezeBatchError) as ctx:
            self._run(b01_items=[item], source_bindings=bindings)
        self.assertIn("别名证据", str(ctx.exception))

    def test_measured_budget_overrides_default(self):
        document, _ = self._run(
            budgets_by_table={"T_SRC_A": {"max_rows_per_slice": 10000}}
        )
        self.assertEqual(
            document["tables"]["T_SRC_A"]["budget"]["max_rows_per_slice"], 10000
        )


if __name__ == "__main__":
    unittest.main()
