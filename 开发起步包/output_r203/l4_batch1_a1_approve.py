# -*- coding: utf-8 -*-
"""L4 治理第一小批：198 A1 组 20 条草稿 approve（203 §21 AUTHORIZED_CONDITIONAL；用户"按建议来"二次授权）。
条件核验：live 在位 ✅ / 自然键与 195 零碰撞 ✅ / P2A 探针 r198 live 全过 ✅ / source 修订核验（空则补）。
写动作：每项 UPDATE review_status draft→approved + system/source 补齐（若空）+ 逐项审计；单事务；幂等可重放。
approve ≠ 进正式关系（formal 1329 不动，后续仍需人工 candidate→formal）。"""
import json
from datetime import datetime, timezone

from sqlalchemy import text
from app.core.db import SessionLocal

IDS = [686, 709, 711, 721, 729, 730, 735, 742, 744, 762,
       765, 766, 767, 777, 792, 793, 808, 815, 817, 832]
OP = "ai:r203-l4"
SYS, SRC = "HIS", "his_source_10_10_10_15"

out = {"batch": "L4-198-A1-approve", "executed_at": datetime.now(timezone.utc).isoformat(), "items": []}

db = SessionLocal()
try:
    rows = db.execute(text(
        "SELECT id, review_status, from_system_code, from_source_code, to_system_code, to_source_code "
        "FROM asset.asset_relation_reviews WHERE id = ANY(:ids)"), {"ids": IDS}).fetchall()
    assert len(rows) == 20, f"expected 20 rows, got {len(rows)}"
    by_id = {r[0]: r for r in rows}
    not_draft = [i for i in IDS if by_id[i][1] != "draft"]
    if not_draft:
        out["skip_not_draft"] = not_draft  # 幂等：非 draft 跳过并记录

    for i in IDS:
        r = by_id[i]
        if r[1] != "draft":
            out["items"].append({"id": i, "action": "skip", "before_status": r[1]})
            continue
        before = {"review_status": r[1], "from_system_code": r[2], "from_source_code": r[3],
                  "to_system_code": r[4], "to_source_code": r[5]}
        db.execute(text(
            "UPDATE asset.asset_relation_reviews SET "
            "from_system_code = COALESCE(from_system_code, :sys), "
            "to_system_code = COALESCE(to_system_code, :sys), "
            "from_source_code = COALESCE(from_source_code, :src), "
            "to_source_code = COALESCE(to_source_code, :src), "
            "review_status = 'approved', reviewer = :op, reviewed_at = now(), "
            "review_note = COALESCE(review_note || E'\\n', '') || "
            "'L4 A1 approve：r198 P2A 双端唯一性探针通过；source 补齐 HIS/his_source_10_10_10_15；授权=203 §21+用户按建议来' "
            "WHERE id = :i"), {"sys": SYS, "src": SRC, "op": OP, "i": i})
        db.execute(text(
            "INSERT INTO asset.asset_govern_audit_logs (module, entity_type, entity_ref, action, operator, after_data) "
            "VALUES ('governance', 'relation_review', :ref, 'approve_a1_batch1', :op, :data)"),
            {"ref": str(i), "op": OP,
             "data": json.dumps({"before": before,
                                 "after": {"review_status": "approved", "reviewer": OP,
                                           "system": SYS, "source": SRC},
                                 "evidence": "r198 human_review_queue A1; probe P2A-" + str(i)},
                                ensure_ascii=False)})
        out["items"].append({"id": i, "action": "approve", "before": before})
    db.commit()
    out["committed"] = True
finally:
    db.close()

# 回读 after
db2 = SessionLocal()
try:
    after = db2.execute(text(
        "SELECT id, review_status, reviewer, from_system_code FROM asset.asset_relation_reviews "
        "WHERE id = ANY(:ids) ORDER BY id"), {"ids": IDS}).fetchall()
    out["readback"] = [{"id": r[0], "status": r[1], "reviewer": r[2], "sys": r[3]} for r in after]
    out["readback_approved_count"] = sum(1 for r in after if r[1] == "approved")
    n_formal = db2.execute(text("SELECT count(*) FROM asset.asset_relations")).scalar()
    out["formal_relations_unchanged"] = n_formal
finally:
    db2.close()
print(json.dumps(out, ensure_ascii=False, indent=1))
