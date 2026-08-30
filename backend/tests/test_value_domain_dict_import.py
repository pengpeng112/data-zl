"""163 R2-E3（151 E3）：两字典表值域批量导入专项测试。

覆盖：幂等收敛 / dry-run 零写 / confirmed 不被覆盖只置冲突 / 规模门禁 / 强制 pending / 审计一条。
测试用小型合成 payload（结构同 151 结果文件 circled 段），不依赖大 JSON 与外部库。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.models.governance_base import GovernAuditLog
from app.models.value_domain import AssetColumnValueDomain
from scripts.import_dict_value_domains import build_items, run_import


def _payload(rows_per_field: int = 2) -> dict:
    jhemr_rows = [
        {"field_name": "OPERATION_TYPE", "item_value": f"手术{ix}", "item_text": str(ix),
         "boh_code": None, "boh_name": None, "default_flag": "0"}
        for ix in range(1, rows_per_field + 1)
    ]
    return {
        "circled": {
            "portal": {
                "types_selected": [
                    {"type_code": "T1", "type_name": "测试类型一",
                     "target": {"system_code": "HIS_SOURCE", "source_code": "his_source_10_10_10_15",
                                "schema_name": "MEDREC", "table_name": "PAT_VISIT",
                                "column_name": "DISCHARGE_DISPOSITION"}},
                ],
                "rows": [
                    {"type_code": "T1", "type_name": "测试类型一", "dict_code": "1",
                     "dict_name": "自行离开", "gb_code": "1", "gb_name": "1", "enable_state": "Y"},
                ],
            },
            "jhemr": {
                "fields_selected": [
                    {"field_name": "OPERATION_TYPE",
                     "target": {"system_code": "JHEMR_VASTBASE", "source_code": "jhemr_vastbase_10_10_8_177",
                                "schema_name": "report", "table_name": "r_operation_doct",
                                "column_name": "operation_type"}},
                ],
                "rows": jhemr_rows,
            },
        }
    }


def _count(db) -> int:
    return len(db.query(AssetColumnValueDomain).all())


def test_dry_run_writes_nothing(db_session):
    payload = _payload()
    stats = run_import(db_session, payload, "portal", dry_run=True)
    assert stats["created"] == 1
    assert _count(db_session) == 0


def test_import_creates_pending_and_is_idempotent(db_session):
    payload = _payload()
    first = run_import(db_session, payload, "portal")
    assert first["created"] == 1
    rows = db_session.query(AssetColumnValueDomain).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].meaning == "自行离开"

    second = run_import(db_session, payload, "portal")
    assert second["created"] == 0
    assert second["attached"] == 0
    assert second["refreshed"] == 0
    assert second["already_current"] == 1
    assert _count(db_session) == 1


def test_jhemr_meaning_carries_paired_code(db_session):
    payload = _payload()
    run_import(db_session, payload, "jhemr")
    rows = db_session.query(AssetColumnValueDomain).order_by(AssetColumnValueDomain.code).all()
    assert len(rows) == 2
    assert rows[0].code == "手术1"
    assert rows[0].meaning == "手术1（对照码 1）"
    assert rows[0].status == "pending"


def test_confirmed_conflict_marks_without_overwrite(db_session):
    existing = AssetColumnValueDomain(
        system_code="HIS_SOURCE", source_code="his_source_10_10_10_15",
        schema_name="MEDREC", table_name="PAT_VISIT", column_name="DISCHARGE_DISPOSITION",
        code="1", meaning="医嘱离院", domain_kind="enum", status="confirmed",
        conflict_status="none", confirmed_by="manual", confirmed_at=datetime(2026, 1, 1),
    )
    db_session.add(existing)
    db_session.flush()

    stats = run_import(db_session, _payload(), "portal")
    assert stats["confirmed_conflicts"] == 1
    db_session.refresh(existing)
    assert existing.meaning == "医嘱离院"  # 不改写
    assert existing.status == "confirmed"
    assert existing.conflict_status == "conflicted"  # 只置位
    assert stats["conflicts"] and "自行离开" in stats["conflicts"][0]


def test_scale_gate_rejects_over_200(db_session):
    payload = _payload(rows_per_field=201)
    with pytest.raises(ValueError, match="规模门禁"):
        run_import(db_session, payload, "jhemr")
    assert _count(db_session) == 0


def test_scope_builder_rejects_unknown(db_session):
    with pytest.raises(ValueError, match="unknown scope"):
        build_items(_payload(), "nope")


def test_batch_audit_single_row(db_session):
    run_import(db_session, _payload(), "portal")
    audits = db_session.query(GovernAuditLog).filter(
        GovernAuditLog.action == "seed_import",
        GovernAuditLog.entity_ref == "import:dict:portal",
    ).all()
    assert len(audits) == 1
    assert audits[0].module == "value_domain"
