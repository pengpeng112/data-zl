"""46 人名单只读核实：平台判定 + attempt 状态 + JHEMR 实时状态（零写）。"""
from sqlalchemy import text

from app.core.db import SessionLocal
from app.services.identity_sync_executor_bridge import execute_jhemr_state_read, execute_cdms_state_read

PERSONS = [
    "003740", "002494", "001336", "001162", "003745", "002151", "002518", "002543",
    "003172", "001703", "001331", "002506", "002487", "001702", "001321", "001681",
    "002551", "001328", "002651", "002491", "001755", "002134", "002919", "001590",
    "000051", "001534", "002216", "002032", "001165", "002559", "002502", "002713",
    "001747", "001684", "001114", "002336", "001710", "001424", "001337", "003627",
    "001561", "001647", "001436", "001638", "001759", "001677",
]

db = SessionLocal()
in_baseline = {
    r[0] for r in db.execute(text(
        "SELECT m.person_code FROM asset.asset_identity_action_scope_members m "
        "JOIN asset.asset_identity_action_scopes s ON s.id = m.scope_id "
        "WHERE s.scope_type='baseline' AND s.status='active'")).fetchall()
}
rows = db.execute(text(
    "SELECT person_code, employee_state, user_state, desired_state, source_complete "
    "FROM asset.asset_identity_account_state_decisions d "
    "WHERE d.rule_version='dual_source_v1' AND d.id IN ("
    "  SELECT MAX(id) FROM asset.asset_identity_account_state_decisions "
    "  GROUP BY person_code)")).fetchall()
decision = {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}
attempts = db.execute(text(
    "SELECT DISTINCT person_code FROM asset.asset_identity_account_state_attempts "
    "WHERE status='executed'")).fetchall()
done_by_platform = {r[0] for r in attempts}

print(f"{'工号':<8} {'基线':<4} {'判定(emp/user=>期望)':<28} {'平台已执行':<6} JHEMR实时")
missing_in_decisions = []
for p in PERSONS:
    dec = decision.get(p)
    if dec is None:
        missing_in_decisions.append(p)
        print(f"{p:<8} {'?':<4} {'无决策记录':<28} {'-':<6} 跳过")
        continue
    emp, usr, want, complete = dec
    j = execute_jhemr_state_read(p)
    js = (j.get("state") or {}) if j.get("status") == "ok" else {}
    jstat = f"{j.get('status')}/{js.get('account_status')}"
    print(f"{p:<8} {'是' if p in in_baseline else '否':<4} {emp}/{usr}=>{want:<10} {'是' if p in done_by_platform else '否':<6} {jstat}")

print("MISSING_IN_DECISIONS:", missing_in_decisions)
db.close()
print("VERIFY_DONE")
