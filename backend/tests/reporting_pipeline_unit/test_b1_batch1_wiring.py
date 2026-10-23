# -*- coding: utf-8 -*-
"""批1-1/1-2a/1-2b 单元测试：冻结运行配置、源工厂查询构建、目标工厂。

纯逻辑与 SQL 文本断言；无数据库依赖。Oracle 方言的集成验证如实
NOT_RUN（不以 SQLite/PG 冒充）。
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.runtime_config import (
    RuntimeConfigError,
    build_freeze_document,
    build_table_document,
    compute_config_fingerprint,
    compute_table_fingerprint,
    load_frozen_runtime_config,
)


def compute_table_fingerprint_safe(table_doc: dict) -> str:
    return compute_table_fingerprint(table_doc)
from app.services.reporting_pipeline.source_factory import (
    DualSourceRouter,
    OracleProjectionQueryBuilder,
    PgProjectionQueryBuilder,
    SourceFactoryError,
)
from app.services.reporting_pipeline.target_factory import (
    TargetFactoryError,
    _wall_clock,
)


def _projection(n: int = 3):
    return [
        {"name": f"C{i}", "target_type": "VARCHAR2(100)", "source_expression": f"C{i}"}
        for i in range(n)
    ]


_TABLE_KWARGS = dict(
    canonical_table="EMR_TEST",
    business_name="测试表",
    engine="PYTHON",
    modes=["T1"],
    source_group="ods_8_216",
    dialect="oracle",
    source_object="ODS.V_TEST",
    credential_ref="container-credentials:ods_8_216",
    target_instance="10.10.8.74:1521/orcl",
    tenant="DBOPER",
    target_table="EMR_TEST",
    stable_key=["ID"],
    anchor_column="DATETIME",
    anchor_inherited_from_parent=False,
    projection=[
        {"name": "ID", "target_type": "VARCHAR2(100)", "source_expression": "ID"},
        {"name": "V1", "target_type": "NUMBER", "source_expression": "V1"},
    ],
    change_mode="SNAPSHOT_DIFF",
    budget={"max_rows_per_slice": 50000, "max_bytes_per_slice": 268435456, "max_attempts": 3},
)


def _table_doc(**overrides) -> dict:
    kwargs = dict(_TABLE_KWARGS)
    kwargs.update(overrides)
    return build_table_document(**kwargs)


class TestRuntimeConfigFreeze(unittest.TestCase):
    def test_freeze_roundtrip_and_fingerprint(self):
        doc = build_freeze_document(
            environment="production",
            tables={"EMR_TEST": _table_doc()},
            source_inputs=[{"path": "a.json", "sha256": "x", "role": "r"}],
            frozen_at="2026-10-23T00:00:00+08:00",
        )
        self.assertTrue(doc["config_fingerprint"])
        path = Path(sys.argv[0]).parent / "_tmp_freeze_test.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            loaded = load_frozen_runtime_config(path)
            self.assertEqual(loaded.environment, "production")
            spec = loaded.table("EMR_TEST")
            self.assertEqual(spec.stable_key, ("ID",))
            self.assertEqual(len(spec.projection), 2)
            self.assertFalse(spec.enabled)
            self.assertEqual(spec.write_columns(), ("ID", "V1"))
        finally:
            path.unlink(missing_ok=True)

    def test_drift_rejected(self):
        doc = build_freeze_document(
            environment="production",
            tables={"EMR_TEST": _table_doc()},
            source_inputs=[],
            frozen_at="t",
        )
        doc["tables"]["EMR_TEST"]["budget"]["max_rows_per_slice"] = 99999
        path = Path(sys.argv[0]).parent / "_tmp_freeze_drift.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            with self.assertRaises(RuntimeConfigError) as ctx:
                load_frozen_runtime_config(path)
            self.assertIn("REFUSED_CONFIG_DRIFT", str(ctx.exception))
        finally:
            path.unlink(missing_ok=True)

    def test_enabled_true_rejected_candidate_stays_disabled(self):
        # 冻结件 enabled 必须为 false：伪造 enabled=true 的文档装载即拒绝
        table = _table_doc()
        table["enabled"] = True
        table["fingerprint"] = compute_table_fingerprint_safe(table)
        doc = build_freeze_document(
            environment="production",
            tables={},
            source_inputs=[],
            frozen_at="t",
        )
        doc["tables"] = {"EMR_TEST": table}
        doc["config_fingerprint"] = compute_config_fingerprint(doc)
        path = Path(sys.argv[0]).parent / "_tmp_freeze_enabled.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        try:
            with self.assertRaises(RuntimeConfigError):
                load_frozen_runtime_config(path)
        finally:
            path.unlink(missing_ok=True)

    def _load_should_fail(self, table: dict) -> None:
        doc = build_freeze_document(
            environment="production", tables={}, source_inputs=[], frozen_at="t",
        )
        doc["tables"] = {"EMR_TEST": table}
        doc["config_fingerprint"] = compute_config_fingerprint(doc)
        path = Path(sys.argv[0]).parent / "_tmp_freeze_invalid.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        try:
            with self.assertRaises(RuntimeConfigError):
                load_frozen_runtime_config(path)
        finally:
            path.unlink(missing_ok=True)

    def test_projection_traceability_required(self):
        self._load_should_fail(_table_doc(projection=[]))
        self._load_should_fail(_table_doc(stable_key=["NOT_IN_PROJ"]))
        self._load_should_fail(_table_doc(
            system_time_column="SYSTEM_TIME",
            projection=[
                {"name": "ID", "target_type": "VARCHAR2(100)", "source_expression": "ID"},
                {"name": "V1", "target_type": "NUMBER", "source_expression": "V1"},
                {"name": "SYSTEM_TIME", "target_type": "TIMESTAMP", "source_expression": "SYSTEM_TIME"},
            ],
        ))

    def test_parent_key_column_must_be_in_projection(self):
        self._load_should_fail(_table_doc(parent={"table": "EMR_ICH", "key_column": "NOPE"}))


class _FakeRuntimeTable:
    """查询构建器所需的最小 TableRuntimeSpec 形状。"""

    def __init__(self, keys=("ID",), anchor="DATETIME"):
        self.canonical_table = "EMR_TEST"
        self.source_object = "ODS.V_TEST"
        self.projection = [
            type("F", (), {"source_expression": "ID", "name": "ID"})(),
            type("F", (), {"source_expression": "V1", "name": "V1"})(),
        ]
        self.anchor_column = anchor
        self.stable_key = keys


class TestOracleQueryBuilder(unittest.TestCase):
    def test_window_rownum_positional_binds(self):
        builder = OracleProjectionQueryBuilder(_FakeRuntimeTable())
        start = datetime(2026, 10, 22, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        start + timedelta(days=1)
        sql, params = builder(_win(start), None, 501)
        self.assertIn("ROWNUM <= :3", sql)
        self.assertIn("DATETIME >= :1", sql)
        self.assertIn("DATETIME < :2", sql)
        self.assertIn("ORDER BY ID", sql)
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0], datetime(2026, 10, 22, 0, 0))  # naive 院区墙钟
        self.assertEqual(params[1], datetime(2026, 10, 23, 0, 0))
        self.assertEqual(params[2], 501)

    def test_keyset_predicate_matches_stable_key_only(self):
        builder = OracleProjectionQueryBuilder(_FakeRuntimeTable())
        from app.services.reporting_pipeline.planner import KeysetCursor

        cursor = KeysetCursor(("ID",), ("K9",), unique_verified=True)
        sql, params = builder(_win(), cursor, 100)
        self.assertIn("ID > :3", sql)
        self.assertEqual(params[2], "K9")
        with self.assertRaises(SourceFactoryError):
            builder(_win(), KeysetCursor(("OTHER",), ("x",), unique_verified=True), 100)

    def test_no_fetch_first_used(self):
        builder = OracleProjectionQueryBuilder(_FakeRuntimeTable())
        sql, _ = builder(_win(), None, 10)
        self.assertNotIn("FETCH FIRST", sql.upper())


class TestPgQueryBuilder(unittest.TestCase):
    def test_limit_and_keyset(self):
        builder = PgProjectionQueryBuilder(_FakeRuntimeTable())
        sql, params = builder(_win(), None, 101)
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(params[-1], 101)
        from app.services.reporting_pipeline.planner import KeysetCursor

        cursor = KeysetCursor(("ID",), ("K5",), unique_verified=True)
        sql, params = builder(_win(), cursor, 101)
        self.assertIn('"ID" > %s', sql)


def _win(start=None):
    from app.services.reporting_pipeline.planner import TimeWindow

    begin = start or datetime(2026, 10, 22, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    return TimeWindow(begin, begin + timedelta(days=1))


class TestDualSourceRouter(unittest.TestCase):
    def test_route_segments_and_fallback(self):
        router = DualSourceRouter(
            "lis_primary",
            [
                {"source_group": "lis_hist", "key_from": "A", "key_to": "M"},
                {"source_group": "lis_new", "key_from": "N", "key_to": None},
            ],
        )
        self.assertEqual(router.route("B")[0], "lis_hist")
        self.assertEqual(router.route("Z")[0], "lis_new")
        self.assertEqual(router.route("0000"), ("lis_primary", False))  # 段外回主源+标记


class TestTargetFactoryEnvRefusal(unittest.TestCase):
    def test_pg_target_requires_env(self):
        from app.services.reporting_pipeline.target_factory import (
            build_target_connection_factory,
        )

        with self.assertRaises(TargetFactoryError):
            build_target_connection_factory(dialect="pg", url_env="APP_TEST_DB_URL_B1")

    def test_unknown_dialect_rejected(self):
        from app.services.reporting_pipeline.target_factory import (
            build_target_connection_factory,
        )

        with self.assertRaises(TargetFactoryError):
            build_target_connection_factory(dialect="mysql_target", url_env="X")

    def test_wall_clock_conversion_not_utc(self):
        utc_time = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)  # 北京 10-23 00:00
        wall = _wall_clock(utc_time)
        self.assertIsNone(wall.tzinfo)
        self.assertEqual((wall.year, wall.month, wall.day, wall.hour), (2026, 10, 23, 0))
        self.assertEqual(_wall_clock(datetime(2026, 1, 1)), datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
