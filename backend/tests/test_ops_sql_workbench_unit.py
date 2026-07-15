"""Unit tests for SQL workbench safety helpers (no DB)."""
from app.services.ops_sql_safety import validate_dry_run_sql, validate_writable_sql


def test_insert_and_update_templates_ok():
    upd = validate_writable_sql(
        "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["UPDATE", "INSERT"],
        params={"owner_name": "a", "full_table_name": "HIS.X"},
    )
    assert upd["valid"] is True
    ins = validate_writable_sql(
        "INSERT INTO asset.asset_table_owners (full_table_name, owner_name) VALUES (:full_table_name, :owner_name)",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["UPDATE", "INSERT"],
        params={"full_table_name": "HIS.X", "owner_name": "a"},
    )
    assert ins["valid"] is True


def test_rejects_business_schema_and_delete():
    his = validate_writable_sql(
        "UPDATE his.staff_dict SET name = :n WHERE emp_no = :e",
        allowed_tables=["his.staff_dict"],
        allowed_ops=["UPDATE"],
        params={"n": "x", "e": "1"},
    )
    assert his["valid"] is False
    assert any("asset schema" in e for e in his["errors"])

    delete = validate_writable_sql(
        "DELETE FROM asset.asset_table_owners WHERE full_table_name = :t",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["DELETE", "UPDATE"],
        params={"t": "HIS.X"},
    )
    assert delete["valid"] is False


def test_dry_run_consistency_for_workbench():
    ok = validate_dry_run_sql(
        "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name",
        "SELECT count(*) FROM asset.asset_table_owners WHERE full_table_name = :full_table_name",
    )
    assert ok["valid"] is True

    bad_table = validate_dry_run_sql(
        "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name",
        "SELECT count(*) FROM asset.other_table WHERE full_table_name = :full_table_name",
    )
    assert bad_table["valid"] is False
