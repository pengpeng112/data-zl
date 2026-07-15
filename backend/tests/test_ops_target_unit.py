from app.services.ops_sql_safety import validate_writable_sql


def test_platform_asset_write_ok():
    r = validate_writable_sql(
        "UPDATE asset.asset_table_owners SET owner_name = :n WHERE full_table_name = :t",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["UPDATE"],
        params={"n": "a", "t": "x"},
    )
    assert r["valid"] is True


def test_business_schema_write_rejected():
    r = validate_writable_sql(
        "UPDATE his.staff_dict SET name = :n WHERE emp_no = :e",
        allowed_tables=["his.staff_dict"],
        allowed_ops=["UPDATE"],
        params={"n": "a", "e": "1"},
    )
    assert r["valid"] is False
    assert any("asset schema" in e for e in r["errors"])
