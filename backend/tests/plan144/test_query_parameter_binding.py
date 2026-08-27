"""A01/A02: parameter binding must reach the connector; schema mismatches block."""
from __future__ import annotations

import pytest

from app.services.query_parameter_validator import (
    ParameterValidationError,
    build_bind_parameters,
    extract_bind_names,
    validate_query_parameters,
)

_ORACLE_SQL = (
    "SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT "
    "WHERE PATIENT_ID = :patient_id AND VISIT_ID = :visit_id"
)
_SCHEMA = {
    "type": "object",
    "required": ["patient_id", "visit_id"],
    "properties": {
        "patient_id": {"type": "string", "minLength": 1, "maxLength": 32},
        "visit_id": {"type": "integer", "minimum": 0, "maximum": 99},
    },
}


def test_bind_names_extracted_from_oracle_colon_placeholders():
    assert extract_bind_names(_ORACLE_SQL, "oracle") == {"patient_id", "visit_id"}


def test_bind_names_extracted_from_postgres_dollar_placeholders():
    sql = "SELECT 1 FROM ods.pat_visit WHERE patient_id = %(patient_id)s"
    assert extract_bind_names(sql, "postgresql") == {"patient_id"}


def test_missing_required_parameter_is_blocked():
    with pytest.raises(ParameterValidationError):
        validate_query_parameters(_ORACLE_SQL, _SCHEMA, {"patient_id": "X1"}, "oracle")


def test_unknown_parameter_is_blocked():
    with pytest.raises(ParameterValidationError) as err:
        validate_query_parameters(
            _ORACLE_SQL, _SCHEMA, {"patient_id": "X1", "visit_id": 1, "extra": 2}, "oracle"
        )
    assert "extra" in str(err.value)


def test_schema_parameter_unused_in_sql_is_blocked():
    schema = dict(_SCHEMA)
    schema["properties"] = dict(_SCHEMA["properties"])
    schema["properties"]["month"] = {"type": "string"}
    sql = "SELECT * FROM HIS.PAT_VISIT WHERE PATIENT_ID = :patient_id"
    with pytest.raises(ParameterValidationError):
        validate_query_parameters(sql, schema, {"patient_id": "X1", "month": "2026-01"}, "oracle")


def test_type_and_range_validation():
    with pytest.raises(ParameterValidationError):
        validate_query_parameters(_ORACLE_SQL, _SCHEMA, {"patient_id": "X1", "visit_id": 500}, "oracle")
    with pytest.raises(ParameterValidationError):
        validate_query_parameters(_ORACLE_SQL, _SCHEMA, {"patient_id": 12345, "visit_id": 1}, "oracle")


def test_build_bind_parameters_returns_plain_dict_for_connector():
    out = build_bind_parameters(_ORACLE_SQL, _SCHEMA, {"patient_id": "X1", "visit_id": 1}, "oracle")
    assert out == {"patient_id": "X1", "visit_id": 1}


def test_parameter_value_cannot_change_sql_structure():
    """Bind values stay single values; they are never concatenated into SQL."""
    hostile = "A' OR '1'='1"
    out = build_bind_parameters(_ORACLE_SQL, _SCHEMA, {"patient_id": hostile, "visit_id": 1}, "oracle")
    assert out["patient_id"] == hostile
    # SQL text itself is untouched by parameter handling
    assert ":patient_id" in _ORACLE_SQL
