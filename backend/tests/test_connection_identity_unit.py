from app.services.connection_identity import (
    build_connection_identity_key,
    default_port,
    validate_connection_fields,
)


def test_default_ports():
    assert default_port("oracle") == 1521
    assert default_port("mysql") == 3306
    assert default_port("sqlserver") == 1433
    assert default_port("vastbase") == 5432
    assert default_port("postgresql") == 5432


def test_validate_five_db_types():
    base = {"target_host": "10.0.0.1", "system_code": "X", "write_policy": "readonly"}
    assert not validate_connection_fields({**base, "db_type": "oracle", "port": 1521, "service_mode": "service_name", "service_name": "orcl"})
    assert not validate_connection_fields({**base, "db_type": "mysql", "port": 3306, "database_name": "db"})
    assert not validate_connection_fields({**base, "db_type": "sqlserver", "port": 1433, "database_name": "db"})
    assert not validate_connection_fields({**base, "db_type": "vastbase", "port": 5432, "database_name": "db"})
    assert not validate_connection_fields({**base, "db_type": "postgresql", "port": 5432, "database_name": "db"})


def test_business_write_policy_rejected():
    errors = validate_connection_fields({
        "db_type": "oracle",
        "target_host": "10.0.0.1",
        "port": 1521,
        "service_name": "orcl",
        "system_code": "HIS",
        "write_policy": "platform_controlled",
    })
    assert any("readonly" in e or "platform_controlled" in e for e in errors)


def test_identity_key_stable():
    k1 = build_connection_identity_key("oracle", "10.10.10.15", 1521, "orcl", None, "service_name")
    k2 = build_connection_identity_key("oracle", "10.10.10.15", 1521, "orcl", None, "service_name")
    assert k1 == k2
    assert "oracle" in k1
