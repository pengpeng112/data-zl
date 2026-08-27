"""plan144 S4 DB-integration: metric engine + dimension/batch isolation (A15/A16) + bind reaching connector (A01).

Runs against the isolated test database via root conftest (APP_TEST_DB_URL).
No business source is contacted — the connector is faked at the factory.
"""
from __future__ import annotations

import pytest

from app.models.metric_asset import AssetMetricDefinition, AssetMetricResult, AssetMetricVersion
from app.models.query_asset import AssetQueryDefinition, AssetQueryVersion
from app.services import quality_sql_runner
from app.services.metric_calculation_orchestrator import calculate_metric_version


class FakeConnector:
    """Records bind params and returns deterministic aggregation rows."""

    calls: list[dict] = []

    def __init__(self, source):
        self.source = source

    def execute_readonly(self, sql, params=None, max_rows=1000):
        FakeConnector.calls.append({"sql": sql, "params": dict(params or {})})
        code = "NUM" if "NUM" in sql else ("DEN" if "DEN" in sql else "MAIN")
        if getattr(FakeConnector, "fail", None) == code:
            raise RuntimeError(f"simulated failure for {code}")
        rows = getattr(FakeConnector, "rows", {"NUM": [{"CNT": 1}], "DEN": [{"CNT": 3}], "MAIN": [{"CNT": 42}]})
        return list(rows.get(code, []))

    def close(self):
        pass


@pytest.fixture()
def fake_connector(monkeypatch):
    FakeConnector.calls = []
    FakeConnector.fail = None
    FakeConnector.rows = {"NUM": [{"CNT": 1}], "DEN": [{"CNT": 3}], "MAIN": [{"CNT": 42}]}
    monkeypatch.setattr(quality_sql_runner, "_build_connector", lambda source: FakeConnector(source))
    return FakeConnector


@pytest.fixture()
def seeded_metric(db_session):
    qd = AssetQueryDefinition(
        query_code="QRY_P144_T", title="plan144 metric test", source_code="ods_8_216", status="active"
    )
    db_session.add(qd)
    db_session.flush()
    num = AssetQueryVersion(
        query_id=qd.id, query_code="QRY_P144_T", version=1, status="active", is_active=True,
        dialect="oracle", sql_text="SELECT :p_num AS NUM_MARKER, 1 AS CNT FROM DUAL",
        sql_sha256="x" * 64, parameter_schema={"type": "object", "properties": {"p_num": {"type": "string"}}},
        certification_status="certified",
    )
    den = AssetQueryVersion(
        query_id=qd.id, query_code="QRY_P144_T", version=2, status="active", is_active=False,
        dialect="oracle", sql_text="SELECT 3 AS CNT FROM DUAL", sql_sha256="y" * 64,
    )
    # separate active version used as denominator via its own definition
    qd2 = AssetQueryDefinition(
        query_code="QRY_P144_D", title="plan144 denominator", source_code="ods_8_216", status="active"
    )
    db_session.add(qd2)
    db_session.flush()
    den2 = AssetQueryVersion(
        query_id=qd2.id, query_code="QRY_P144_D", version=1, status="active", is_active=True,
        dialect="oracle", sql_text="SELECT 3 AS DEN_CNT FROM DUAL", sql_sha256="z" * 64,
    )
    db_session.add_all([num, den, den2])
    db_session.flush()
    md = AssetMetricDefinition(metric_code="MET_P144_T", title="plan144 ratio")
    db_session.add(md)
    db_session.flush()
    mv = AssetMetricVersion(
        metric_id=md.id, metric_code="MET_P144_T", version=1, status="active", is_active=True,
        numerator_query_code="QRY_P144_T", numerator_query_version=1,
        denominator_query_code="QRY_P144_D", denominator_query_version=1,
        calculation_type="ratio", precision=2, rounding_mode="half_up",
        definition_text="num/den", certification_status="certified",
    )
    db_session.add(mv)
    db_session.commit()
    return {"metric_code": "MET_P144_T", "version": 1}


def test_calculation_computes_decimal_ratio_and_registers(db_session, fake_connector, seeded_metric):
    result = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1,
        period_key="2026-08", parameters={"p_num": "x1"}, triggered_by="t",
    )
    assert result["status"] == "success"
    assert result["metric_value"] == "0.33"
    assert result["run_batch"].startswith("20")
    row = db_session.get(AssetMetricResult, result["result_id"])
    assert row.metric_num is not None
    from decimal import Decimal

    assert row.metric_num == Decimal("0.33")  # NUMERIC(20,6) storage compares by value
    assert row.numerator_num == 1
    assert row.denominator_num == 3


def test_bind_parameters_reach_connector(db_session, fake_connector, seeded_metric):
    calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1,
        period_key="2026-08", parameters={"p_num": "x9"}, triggered_by="t",
    )
    sent = [c for c in fake_connector.calls if "NUM_MARKER" in c["sql"]]
    assert sent and sent[0]["params"] == {"p_num": "x9"}


def test_same_period_different_dimensions_not_overwritten(db_session, fake_connector, seeded_metric):
    r1 = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1, period_key="2026-08",
        parameters={"p_num": "x"}, dimensions={"dept": "内科"}, triggered_by="t",
    )
    r2 = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1, period_key="2026-08",
        parameters={"p_num": "x"}, dimensions={"dept": "外科"}, triggered_by="t",
    )
    assert r1["result_id"] != r2["result_id"]
    rows = (
        db_session.query(AssetMetricResult)
        .filter(AssetMetricResult.metric_code == "MET_P144_T")
        .all()
    )
    assert len(rows) == 2
    assert {(r.dimensions or {}).get("dept") for r in rows} == {"内科", "外科"}


def test_recalc_same_dimensions_keeps_history(db_session, fake_connector, seeded_metric):
    r1 = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1, period_key="2026-08",
        parameters={"p_num": "x"}, dimensions={"dept": "内科"}, triggered_by="t",
    )
    r2 = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1, period_key="2026-08",
        parameters={"p_num": "x"}, dimensions={"dept": "内科"}, triggered_by="t",
    )
    assert r2["run_batch"] != r1["run_batch"]
    assert r2["result_id"] != r1["result_id"]
    rows = (
        db_session.query(AssetMetricResult)
        .filter(AssetMetricResult.metric_code == "MET_P144_T")
        .order_by(AssetMetricResult.id)
        .all()
    )
    assert len(rows) == 2
    assert rows[1].is_recalc is True
    assert rows[1].prev_result_id == rows[0].id


def test_denominator_failure_yields_partial_not_number(db_session, fake_connector, seeded_metric):
    fake_connector.fail = "DEN"
    result = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1,
        period_key="2026-08", parameters={"p_num": "x"}, triggered_by="t",
    )
    assert result["status"] in {"partial", "unavailable"}
    assert result["metric_value"] is None


def test_denominator_zero_yields_unavailable(db_session, fake_connector, seeded_metric):
    fake_connector.rows = {"NUM": [{"CNT": 5}], "DEN": [{"CNT": 0}], "MAIN": [{"CNT": 0}]}
    result = calculate_metric_version(
        db_session, metric_code="MET_P144_T", version=1,
        period_key="2026-08", parameters={"p_num": "x"}, triggered_by="t",
    )
    assert result["status"] == "unavailable"
    assert result["metric_value"] is None
