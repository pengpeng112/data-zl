"""S5：冻结 230 基线（批准类目=emp enabled + user disabled；带治理审计）。"""
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.governance_base import GovernAuditLog
from app.services.identity_sync_action_gate import freeze_baseline_scope

APPROVAL = "186-20260909-disable-only"
OPERATOR = "ai-186-s5-baseline-freeze"

db = SessionLocal()
rows = db.execute(text(
    "SELECT d.person_code, d.decision_reason FROM asset.asset_identity_account_state_decisions d "
    "WHERE d.rule_version='dual_source_v1' AND d.desired_state='disabled' "
    "AND d.employee_state='enabled' AND d.user_state='disabled' "
    "AND d.source_complete AND d.execution_allowed "
    "ORDER BY d.person_code")).fetchall()

# 剔除无人员主档/冲突人员（与 selector 同口径；被剔除者在报告中如实计数）
from app.models.identity import IdentityPerson
excluded_no_person = 0
excluded_conflict = 0
members: list[tuple[str, str | None]] = []
for code, reason in rows:
    p = db.query(IdentityPerson).filter(IdentityPerson.person_code == code).first()
    if p is None:
        excluded_no_person += 1
        continue
    if p.conflict_flag:
        excluded_conflict += 1
        continue
    members.append((code, reason))

print(f"候选(230类目)={len(rows)} 剔除无主档={excluded_no_person} 剔除冲突={excluded_conflict} 实际冻结={len(members)}")

scope = freeze_baseline_scope(
    db, approval_ref=APPROVAL, members=members, created_by=OPERATOR,
    description="186 §12.4-2 批准基线：人员有效+SYS_USER账号停用（230类目，冻结于2026-09-10新鲜观测；不含员工侧停用60人）",
)
db.add(GovernAuditLog(
    module="governance", entity_type="identity_action_scope",
    entity_ref=f"baseline:{APPROVAL}", action="scope_freeze", operator=OPERATOR,
    after_data={"members": len(members), "excluded_no_person": excluded_no_person,
                "excluded_conflict": excluded_conflict, "scope_fingerprint": scope.scope_fingerprint,
                "category": "employee_enabled+user_disabled", "approval_ref": APPROVAL},
))
db.commit()
print("scope_id:", scope.id, "| fingerprint:", scope.scope_fingerprint[:16], "…")
print("FREEZE_DONE")
