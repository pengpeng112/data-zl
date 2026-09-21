"""试点前置状态读取（只读，无门禁的状态读端点）。"""
from app.services.identity_sync_executor_bridge import execute_jhemr_state_read, execute_cdms_state_read

for emp in ("003740", "001554"):
    j = execute_jhemr_state_read(emp)
    c = execute_cdms_state_read(emp)
    js = j.get("state") or {}
    cs = c.get("state") or {}
    print(f"{emp} | JHEMR: status={j.get('status')} account_status={js.get('account_status')} "
          f"locked_time={js.get('locked_time')} | CDMS: status={c.get('status')} "
          f"fuserstate={cs.get('fuserstate')} fchangedate={cs.get('fchangedate')}")
print("BEFORE_STATE_DONE")
