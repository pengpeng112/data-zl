"""S5 预检（只读）：290 名 disabled 决策组成分析 + 试点 dry-run。

不写任何表、不开窗口、不预留名额（reserve_budget=False）。
"""
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.identity_sync_orchestrator import select_account_state_actions

db = SessionLocal()
print("phase_d:", getattr(settings, "identity_phase_d_approval_version", "")[:12] + "…")

print("=== disabled 决策组成（employee_state × user_state） ===")
rows = db.execute(text(
    "SELECT employee_state, user_state, COUNT(*) FROM asset.asset_identity_account_state_decisions "
    "WHERE rule_version='dual_source_v1' AND desired_state='disabled' "
    "GROUP BY 1, 2 ORDER BY 3 DESC")).fetchall()
for r in rows:
    print(f"  emp={r[0]} user={r[1]} : {r[2]}")

print("=== 230类目（emp=enabled 且 user=disabled，即批准的'人员有效+账号停用'） ===")
cat = db.execute(text(
    "SELECT COUNT(*) FROM asset.asset_identity_account_state_decisions "
    "WHERE rule_version='dual_source_v1' AND desired_state='disabled' "
    "AND employee_state='enabled' AND user_state='disabled' AND source_complete AND execution_allowed")).scalar()
print("  count:", cat)

print("=== 两试点当前判定 ===")
for p in ("001554", "003740"):
    r = db.execute(text(
        "SELECT employee_state, user_state, desired_state, transition_seq, source_complete "
        "FROM asset.asset_identity_account_state_decisions WHERE person_code=:p "
        "ORDER BY id DESC LIMIT 1"), {"p": p}).fetchone()
    print(f"  {p}: emp={r[0]} user={r[1]} desired={r[2]} seq={r[3]} complete={r[4]}")

print("=== 试点 dry-run（disable_only 视角，零预留零执行） ===")
settings.identity_run_mode = "disable_only"
settings.identity_sync_enabled = True
actions = select_account_state_actions(db, reserve_budget=False)
print("  disables:", [e["person_code"] for e in actions["disables"]])
print("  enables:", len(actions["enables"]))
print("  window(now):", actions.get("window"))
print("  population:", actions.get("population"))

# 基线未冻结时若已能选出 18 人则说明冻结遗漏；应只见两试点
db.close()
print("PRECHECK_DONE")
