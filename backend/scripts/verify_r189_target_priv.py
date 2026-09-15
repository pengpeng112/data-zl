"""R189 diagnose: which LoginSignSyncError branch fired in _read_target."""

from app.core.config import settings
from app.services.identity_login_sign_sync import _read_target, LoginSignSyncError, _adapter

adapter = _adapter()
adapter.connect()
tenant = settings.identity_sync_jhemr_hospital_no
count_row = adapter._fetch_one(
    "SELECT COUNT(*) AS row_count FROM jhemr.users WHERE hospital_no = %s", (tenant,)
) or {}
print("tenant=", tenant, "user_count=", count_row.get("row_count"))
priv = adapter._fetch_one(
    "SELECT "
    "has_table_privilege(current_user, 'jhemr.users_control_mode', 'SELECT') AS c_sel, "
    "has_table_privilege(current_user, 'jhemr.users_control_mode', 'INSERT') AS c_ins, "
    "has_table_privilege(current_user, 'jhemr.users_sublogin', 'SELECT') AS l_sel, "
    "has_table_privilege(current_user, 'jhemr.users_sublogin', 'INSERT') AS l_ins, "
    "has_table_privilege(current_user, 'jhemr.users_subsign', 'SELECT') AS s_sel, "
    "has_table_privilege(current_user, 'jhemr.users_subsign', 'INSERT') AS s_ins, "
    "has_column_privilege(current_user, 'jhemr.users_subsign', 'default_flag', 'UPDATE') AS s_upd, "
    "has_table_privilege(current_user, 'jhemr.users_pic', 'SELECT') AS p_sel, "
    "has_table_privilege(current_user, 'jhemr.users_pic', 'INSERT') AS p_ins, "
    "has_table_privilege(current_user, 'jhemr.users_pic', 'UPDATE') AS p_upd, "
    "current_user AS who",
    (),
)
print("PRIV=", priv)
adapter.close()
