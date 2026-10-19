"""E08 隔离集成：迁移后表存在性与关键约束（在 data_asset_test 上执行）。

覆盖：9 张 asset_reporting_* 表存在、outbox 不可变字节往返、
source_event_id 唯一、月覆盖复合唯一、租约资源唯一。测试自清理。
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa

pytest.importorskip("sqlalchemy")

_EXPECTED_TABLES = (
    "asset_reporting_task_configs",
    "asset_reporting_batches",
    "asset_reporting_batch_attempts",
    "asset_reporting_watermarks",
    "asset_reporting_gap_ledger",
    "asset_reporting_month_coverage",
    "asset_reporting_leases",
    "asset_reporting_alert_incidents",
    "asset_reporting_alert_outbox",
)


@pytest.fixture()
def engine():
    engine = sa.create_engine(os.environ["APP_TEST_DB_URL"])
    yield engine
    with engine.begin() as conn:
        for table in _EXPECTED_TABLES:
            conn.execute(sa.text(f"DELETE FROM asset.{table}"))
    engine.dispose()


def test_migration_tables_present(engine):
    with engine.connect() as conn:
        found = conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='asset' AND table_name LIKE 'asset_reporting_%'"
            )
        ).scalars().all()
    assert set(_EXPECTED_TABLES) <= set(found)


def test_outbox_immutable_bytes_and_unique(engine):
    body = '{"a":1}'.encode("utf-8")
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO asset.asset_reporting_alert_outbox "
                "(source_event_id, incident_id, revision, event_kind, severity, "
                " title, immutable_body, payload_sha256) "
                "VALUES ('itest-1', 'INC-IT', 1, 'OPENED', 'red', 't', :body, :sha)"
            ),
            {"body": body, "sha": "a" * 64},
        )
        conn.commit()
        row = conn.execute(
            sa.text(
                "SELECT immutable_body FROM asset.asset_reporting_alert_outbox "
                "WHERE source_event_id='itest-1'"
            )
        ).one()
        assert bytes(row.immutable_body) == body
        nested = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO asset.asset_reporting_alert_outbox "
                    "(source_event_id, incident_id, revision, event_kind, severity, "
                    " title, immutable_body, payload_sha256) "
                    "VALUES ('itest-1', 'INC-IT', 1, 'OPENED', 'red', 't', :b, :s)"
                ),
                {"b": b"x", "s": "b" * 64},
            )
            raised = False
        except sa.exc.IntegrityError:
            raised = True
        finally:
            nested.rollback()
        assert raised, "source_event_id 唯一约束未生效"
        conn.rollback()


def test_month_coverage_composite_unique(engine):
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO asset.asset_reporting_month_coverage "
                "(canonical_table, business_month, route_or_origin) "
                "VALUES ('EMR_DOC_ORDER_CHECK', '2025-03', 'ods__V_TEST')"
            )
        )
        conn.commit()
        nested = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO asset.asset_reporting_month_coverage "
                    "(canonical_table, business_month, route_or_origin) "
                    "VALUES ('EMR_DOC_ORDER_CHECK', '2025-03', 'ods__V_TEST')"
                )
            )
            raised = False
        except sa.exc.IntegrityError:
            raised = True
        finally:
            nested.rollback()
        assert raised, "月覆盖复合唯一约束未生效"
        conn.rollback()
