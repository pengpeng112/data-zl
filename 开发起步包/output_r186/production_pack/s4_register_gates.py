"""186 v1.10 S4：受控登记已批准门禁（平台库写，全部带治理审计）。

依据用户批准（§12.4/§12.8）：
- 用途绑定 identity_account_sync × {jhemr_vastbase_10_10_8_177, paperless_cdms_oracle_10_10_10_93}
  （沿用服务器已登记写凭据引用；不覆盖字典推送策略）
- 启用 JHEMR_ACCOUNT_DISABLE / CDMS_ACCOUNT_DISABLE（两个 enable 保持 disabled）
- 试点批准范围 003740 / 001554（approval_ref=186-20260909-disable-only）

幂等：重复执行不重复插入、不重复启用。每步写 GovernAuditLog。
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset_system import AssetSourcePurposeBinding
from app.models.governance_base import AssetActionExecutor, GovernAuditLog
from app.models.identity_sync import IdentityApprovedScope, IdentityApprovedScopeMember

APPROVAL = "186-20260909-disable-only"
OPERATOR = "ai-186-v110-s4-registration"

BINDINGS = [
    ("jhemr_vastbase_10_10_8_177", "file:///etc/data-asset/credentials/jhemr_identity_sync.write"),
    ("paperless_cdms_oracle_10_10_10_93", "file:///etc/data-asset/credentials/cdms_identity_sync.write"),
]
ENABLE_EXECUTORS = ["JHEMR_ACCOUNT_DISABLE", "CDMS_ACCOUNT_DISABLE"]
KEEP_DISABLED = ["JHEMR_ACCOUNT_ENABLE", "CDMS_ACCOUNT_ENABLE"]
PILOT_PERSONS = ["003740", "001554"]

db = SessionLocal()
now = datetime.now(timezone.utc)
results = {"bindings": [], "executors": [], "pilot_scope": None}

for source_code, cred_ref in BINDINGS:
    row = db.scalar(select(AssetSourcePurposeBinding).where(
        AssetSourcePurposeBinding.source_code == source_code,
        AssetSourcePurposeBinding.purpose == "identity_account_sync",
    ))
    before = None
    if row is None:
        row = AssetSourcePurposeBinding(
            source_code=source_code, purpose="identity_account_sync",
            write_policy="identity_account_sync",
            credential_status="unconfigured", enabled=False,
        )
        db.add(row)
    else:
        before = {"enabled": bool(row.enabled), "has_ref": bool(row.write_credential_ref)}
    row.write_credential_ref = cred_ref
    row.credential_status = "configured"
    row.enabled = True
    row.approval_ref = APPROVAL
    row.description = "186 §12.4-4 批准：身份状态同步用途绑定（不改变字典推送策略）"
    row.updated_at = now
    db.add(GovernAuditLog(
        module="systems", entity_type="asset_source_purpose_binding",
        entity_ref=f"{source_code}:identity_account_sync", action="purpose_binding_upsert",
        operator=OPERATOR, before_data=before,
        after_data={"enabled": True, "credential_status": "configured",
                    "write_credential_ref": cred_ref, "approval_ref": APPROVAL},
    ))
    results["bindings"].append({"source": source_code, "enabled": True, "credential_status": "configured"})

for code in ENABLE_EXECUTORS + KEEP_DISABLED:
    row = db.scalar(select(AssetActionExecutor).where(AssetActionExecutor.executor_code == code))
    if row is None:
        print(f"ERROR executor not registered: {code}")
        raise SystemExit(2)
    target_enabled = code in ENABLE_EXECUTORS
    before = {"enabled": bool(row.enabled)}
    if bool(row.enabled) != target_enabled:
        row.enabled = target_enabled
        row.updated_at = now
        db.add(GovernAuditLog(
            module="governance", entity_type="asset_action_executor", entity_ref=code,
            action="executor_patch", operator=OPERATOR, before_data=before,
            after_data={"enabled": target_enabled, "approval_ref": APPROVAL,
                        "reason": "186 §12.4/§12.8 已批准：仅启用两个 disable；enable 未批准"},
        ))
    results["executors"].append({"code": code, "enabled": bool(row.enabled)})

scope = db.scalar(select(IdentityApprovedScope).where(
    IdentityApprovedScope.approval_ref == APPROVAL,
    IdentityApprovedScope.action == "disable",
    IdentityApprovedScope.scope_type == "pilot",
))
if scope is None:
    scope = IdentityApprovedScope(
        scope_type="pilot", approval_ref=APPROVAL, action="disable", status="active",
        description="186 §12.4-3 试点：003740(仅USER停用) / 001554(仅EMPLOYEE停用)",
        created_by=OPERATOR,
    )
    db.add(scope)
    db.flush()
    for person in PILOT_PERSONS:
        db.add(IdentityApprovedScopeMember(
            scope_id=scope.id, person_code=person, frozen_reason="pilot",
        ))
    db.add(GovernAuditLog(
        module="governance", entity_type="identity_action_scope",
        entity_ref=f"pilot:{APPROVAL}", action="scope_register", operator=OPERATOR,
        after_data={"members": PILOT_PERSONS, "approval_ref": APPROVAL},
    ))
    results["pilot_scope"] = {"scope_id": scope.id, "members": PILOT_PERSONS}
else:
    results["pilot_scope"] = {"scope_id": scope.id, "already_registered": True}

db.commit()

# 回读核验（登记后立即回读，不等于目标写）
for code in ENABLE_EXECUTORS + KEEP_DISABLED:
    row = db.scalar(select(AssetActionExecutor).where(AssetActionExecutor.executor_code == code))
    print("EXECUTOR", code, "enabled=", bool(row.enabled))
for source_code, _ in BINDINGS:
    row = db.scalar(select(AssetSourcePurposeBinding).where(
        AssetSourcePurposeBinding.source_code == source_code,
        AssetSourcePurposeBinding.purpose == "identity_account_sync"))
    print("BINDING", source_code, "enabled=", bool(row.enabled), "status=", row.credential_status,
          "ref_set=", bool(row.write_credential_ref))
members = db.scalars(select(IdentityApprovedScopeMember.person_code).where(
    IdentityApprovedScopeMember.scope_id == scope.id)).all()
print("PILOT_SCOPE", scope.id, sorted(members), "status=", scope.status)
db.close()
print("S4_REGISTRATION_DONE")
