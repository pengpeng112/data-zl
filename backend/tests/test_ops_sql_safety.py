from app.services.ops_sql_safety import validate_writable_sql


def _validate(sql: str, params: dict | None = None, ops: list[str] | None = None):
    return validate_writable_sql(
        sql,
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=ops or ["UPDATE"],
        params=params or {"owner_name": "owner-a", "full_table_name": "HIS.PAT_VISIT"},
    )


def test_parameterized_update_template_is_allowed():
    result = _validate(
        """
        UPDATE asset.asset_table_owners
        SET owner_name = :owner_name,
            updated_at = now()
        WHERE full_table_name = :full_table_name
        """
    )

    assert result["valid"] is True
    assert result["parsed_summary"]["operation"] == "UPDATE"
    assert result["parsed_summary"]["target_table"] == "asset.asset_table_owners"


def test_parameterized_insert_values_template_is_allowed():
    result = validate_writable_sql(
        """
        INSERT INTO asset.asset_table_owners (full_table_name, owner_name)
        VALUES (:full_table_name, :owner_name)
        """,
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["INSERT"],
        params={"full_table_name": "HIS.PAT_VISIT", "owner_name": "owner-a"},
    )

    assert result["valid"] is True
    assert result["parsed_summary"]["operation"] == "INSERT"


def test_rejects_delete_and_ddl_even_when_whitelisted():
    delete_result = validate_writable_sql(
        "DELETE FROM asset.asset_table_owners WHERE full_table_name = :full_table_name",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["DELETE"],
        params={"full_table_name": "HIS.PAT_VISIT"},
    )
    ddl_result = validate_writable_sql(
        "ALTER TABLE asset.asset_table_owners ADD COLUMN owner_phone text",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["ALTER"],
        params={},
    )

    assert delete_result["valid"] is False
    assert any("forbidden keyword: DELETE" in item for item in delete_result["errors"])
    assert ddl_result["valid"] is False
    assert any("forbidden keyword: ALTER" in item for item in ddl_result["errors"])


def test_rejects_multi_statement_comments_and_unqualified_table():
    multi = _validate(
        "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name;"
    )
    commented = _validate(
        "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name --x"
    )
    unqualified = validate_writable_sql(
        "UPDATE asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["UPDATE"],
        params={"owner_name": "owner-a", "full_table_name": "HIS.PAT_VISIT"},
    )

    assert multi["valid"] is False
    assert any("semicolon" in item for item in multi["errors"])
    assert commented["valid"] is False
    assert any("comments" in item for item in commented["errors"])
    assert unqualified["valid"] is False
    assert any("asset schema" in item for item in unqualified["errors"])


def test_rejects_non_asset_schema_and_update_without_where_bind():
    non_asset = validate_writable_sql(
        "UPDATE his.staff_dict SET name = :name WHERE emp_no = :emp_no",
        allowed_tables=["his.staff_dict"],
        allowed_ops=["UPDATE"],
        params={"name": "x", "emp_no": "1"},
    )
    literal_where = _validate(
        "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = 'HIS.PAT_VISIT'",
        params={"owner_name": "owner-a"},
    )

    assert non_asset["valid"] is False
    assert any("asset schema" in item for item in non_asset["errors"])
    assert literal_where["valid"] is False
    assert any("WHERE must use bind parameters" in item for item in literal_where["errors"])


def test_rejects_non_parameterized_templates():
    result = validate_writable_sql(
        "UPDATE asset.asset_table_owners SET owner_name = 'owner-a' WHERE full_table_name = 'HIS.PAT_VISIT'",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["UPDATE"],
        params={},
    )

    assert result["valid"] is False
    assert any("bind parameters" in item for item in result["errors"])


def test_rejects_dangerous_functions_and_insert_select():
    dangerous = _validate(
        "UPDATE asset.asset_table_owners SET owner_name = dblink(:conn, :sql) WHERE full_table_name = :full_table_name",
        params={"conn": "x", "sql": "select 1", "full_table_name": "HIS.PAT_VISIT"},
    )
    insert_select = validate_writable_sql(
        "INSERT INTO asset.asset_table_owners (full_table_name, owner_name) SELECT :full_table_name, :owner_name",
        allowed_tables=["asset.asset_table_owners"],
        allowed_ops=["INSERT"],
        params={"full_table_name": "HIS.PAT_VISIT", "owner_name": "owner-a"},
    )

    assert dangerous["valid"] is False
    assert any("forbidden function: dblink" in item for item in dangerous["errors"])
    assert insert_select["valid"] is False
    assert any("INSERT ... SELECT" in item for item in insert_select["errors"])