import os

import pytest
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.governance_base import GovernAuditLog
from app.models.ops_tool import OpsToolRun, OpsToolTemplate
from app.services.ops_executor import OpsExecutionError, execute_whitelist_dml


PREFIX = "test-executor-"


@pytest.fixture
def db():
    os.environ["PYTEST_ASSET_WRITE"] = "asset_write:secret"
    session = SessionLocal()
    try:
        _cleanup(session)
        yield session
    finally:
        session.rollback()
        _cleanup(session)
        session.close()


def _cleanup(session):
    session.execute(delete(OpsToolRun).where(OpsToolRun.tool_code.like(f"{PREFIX}%")))
    session.execute(delete(OpsToolTemplate).where(OpsToolTemplate.tool_code.like(f"{PREFIX}%")))
    session.commit()


def _config(*, dry_run_sql: str | None = None, max_affected_rows: int = 100, write_credential_ref: str | None = "env:PYTEST_ASSET_WRITE"):
    return {
        "__ops_write_config__": {
            "allowed_tables": ["asset.asset_ops_tool_templates"],
            "allowed_operations": ["UPDATE"],
            "dry_run_sql": dry_run_sql,
            "max_affected_rows": max_affected_rows,
            "require_audit": True,
            "write_credential_ref": write_credential_ref,
        }
    }


def _make_tool_and_run(
    db,
    *,
    suffix: str = "update",
    source_code: str = "asset",
    dry_run_sql: str | None = None,
    max_affected_rows: int = 100,
):
    tool_code = f"{PREFIX}{suffix}"
    tool = OpsToolTemplate(
        tool_code=tool_code,
        tool_name_cn="executor test tool",
        system_code="ASSET_PLATFORM",
        source_code=source_code,
        tool_type="write",
        risk_level="high",
        input_schema=_config(
            dry_run_sql=dry_run_sql
            or "SELECT count(*) FROM asset.asset_ops_tool_templates WHERE tool_code = :target_tool_code",
            max_affected_rows=max_affected_rows,
        ),
        execution_mode="whitelist_dml",
        sql_or_endpoint_ref=(
            "UPDATE asset.asset_ops_tool_templates "
            "SET description_cn = :description "
            "WHERE tool_code = :target_tool_code"
        ),
        require_approval=True,
        require_second_confirm=True,
        enabled=True,
        description_cn="before",
        rollback_note_cn="Submit a new approved request with the previous description.",
    )
    db.add(tool)
    db.flush()
    run = OpsToolRun(
        tool_code=tool_code,
        requested_by="requester-a",
        approved_by="approver-b",
        approval_status="approved",
        input_params_masked={"target_tool_code": tool_code, "description": "after"},
    )
    db.add(run)
    db.commit()
    db.refresh(tool)
    db.refresh(run)
    return tool, run


def test_execute_whitelist_dml_dry_run_returns_risk_and_limit(db):
    tool, run = _make_tool_and_run(db, suffix="dry-run", max_affected_rows=100)

    result = execute_whitelist_dml(tool, run, db, dry_run=True, executed_by="operator-c")

    assert result["dry_run"] is True
    assert result["estimated_count"] == 1
    assert result["max_affected_rows"] == 100
    assert result["would_execute"] is True
    assert result["risk_scan"]["valid"] is True
    assert "sql_template_hash" in result
    assert "dry_run_sql_hash" in result


def test_execute_whitelist_dml_writes_audit_and_hashes(db):
    tool, run = _make_tool_and_run(db, suffix="execute")

    result = execute_whitelist_dml(tool, run, db, executed_by="operator-c")
    db.flush()

    assert result["affected_count"] == 1
    assert result["affected_rows"] == 1
    assert result["estimated_count"] == 1
    assert run.affected_count == 1
    assert run.risk_scan["valid"] is True
    assert run.risk_scan["parsed_summary"]["sql_template_hash"] == result["sql_template_hash"]

    audit = db.scalar(
        select(GovernAuditLog)
        .where(GovernAuditLog.entity_type == "ops_tool_run")
        .where(GovernAuditLog.entity_ref == str(run.id))
        .where(GovernAuditLog.action == "execute_write")
    )
    assert audit is not None
    assert audit.before_data["tool_code"] == tool.tool_code
    assert audit.before_data["estimated_count"] == 1
    assert audit.before_data["max_affected_rows"] == 100
    assert audit.after_data["affected_rows"] == 1
    assert audit.after_data["params_json_masked"]["target_tool_code"] == tool.tool_code


def test_execute_whitelist_dml_rejects_non_asset_source(db):
    tool, run = _make_tool_and_run(db, suffix="bad-source", source_code="his")

    with pytest.raises(OpsExecutionError, match="platform asset source"):
        execute_whitelist_dml(tool, run, db, executed_by="operator-c")


def test_execute_whitelist_dml_requires_dry_run_sql(db):
    tool, run = _make_tool_and_run(db, suffix="missing-dry-run")
    tool.input_schema = _config(dry_run_sql=None)
    tool.input_schema["__ops_write_config__"].pop("dry_run_sql", None)
    db.commit()

    with pytest.raises(OpsExecutionError, match="dry_run_sql is required"):
        execute_whitelist_dml(tool, run, db, executed_by="operator-c")



def test_execute_whitelist_dml_rejects_missing_write_credential(db):
    tool, run = _make_tool_and_run(db, suffix="missing-credential")
    tool.input_schema = _config(write_credential_ref="env:PYTEST_MISSING_ASSET_WRITE")
    db.commit()

    with pytest.raises(OpsExecutionError, match="write credential env is missing"):
        execute_whitelist_dml(tool, run, db, executed_by="operator-c")
def test_execute_whitelist_dml_rejects_estimated_count_over_limit(db):
    tool, run = _make_tool_and_run(
        db,
        suffix="over-limit",
        dry_run_sql="SELECT 101",
        max_affected_rows=100,
    )

    with pytest.raises(OpsExecutionError, match="estimated_count 101 exceeds max_affected_rows 100"):
        execute_whitelist_dml(tool, run, db, executed_by="operator-c")

    db.rollback()
    current = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == tool.tool_code))
    assert current.description_cn == "before"