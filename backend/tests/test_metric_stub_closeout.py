from sqlalchemy import func, select

from app.models.metric_asset import AssetMetricDefinition, AssetMetricVersion
from app.services.metric_stub_import import (
    MISSING_CORE_METRIC_LIMITATIONS,
    MISSING_CORE_METRICS,
    import_missing_metric_stubs,
)


def test_core48_missing_metrics_are_explicitly_blocked_and_idempotent(db_session):
    first = import_missing_metric_stubs(db_session, dry_run=False, created_by="test_plan130")
    assert first["count"] == 20
    definitions = list(db_session.scalars(
        select(AssetMetricDefinition).where(AssetMetricDefinition.metric_code.like("MET_CORE_%"))
    ).all())
    assert len(definitions) == 20
    assert {row.status for row in definitions} == {"blocked"}
    assert all(row.current_version_id is None for row in definitions)

    versions = list(db_session.scalars(select(AssetMetricVersion)).all())
    assert len(versions) == 20
    assert {row.status for row in versions} == {"blocked"}
    assert not any(row.is_active for row in versions)
    metric_48 = next(row for row in versions if row.metric_code == "MET_CORE_48")
    assert metric_48.limitations == MISSING_CORE_METRIC_LIMITATIONS[48]

    second = import_missing_metric_stubs(db_session, dry_run=False, created_by="test_plan130")
    assert {item["status"] for item in second["items"]} == {"exists"}
    assert db_session.scalar(select(func.count()).select_from(AssetMetricVersion)) == 20
    assert set(MISSING_CORE_METRICS) == set(MISSING_CORE_METRIC_LIMITATIONS)
