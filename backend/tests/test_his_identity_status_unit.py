"""103 复核修复的纯逻辑回归测试：状态归一与人员组科室来源。

活库口径（2026-07-31 只读核实）：
- COMM.STAFF_DICT.STATUS：1=在用（2462 人），0=停用（1802 人）
- FXHIS.SYS_EMPLOYEE.VALIDSTATE：1=有效（2425），0=无效（86）
- COMM.DEPT_DICT.STOP_FLAG：NULL/'0'=有效（595），'1'=停用（221）
- COMM.STAFF_GROUP_DICT.DEPT_CODE：569/569 全部为 NULL，不可用作科室来源
- COMM.STAFF_VS_GROUP.GROUP_CODE：9449/9449 命中 COMM.DEPT_DICT，本身即科室/病区编码
"""

from app.services import his_identity_sync as his
from app.services import identity_source_collector as collector


class TestHisIdentitySyncStatus:
    def test_staff_status_active(self):
        assert his._normalize_status("1") == "active"
        assert his._normalize_status(1) == "active"

    def test_staff_status_inactive(self):
        assert his._normalize_status("0") == "inactive"
        assert his._normalize_status(0) == "inactive"

    def test_staff_status_unknown_not_active(self):
        # 空值/未知值禁止默认归一为 active，避免停用人员被当作在用
        assert his._normalize_status(None) == "unknown"
        assert his._normalize_status("") == "unknown"
        assert his._normalize_status("Y") == "unknown"

    def test_deleted_employee_is_inactive(self):
        assert his._employee_employment_status({"ISDELETED": 1, "VALIDSTATE": 1}) == "inactive"
        assert his._employee_employment_status({"ISDELETED": "0", "VALIDSTATE": 0}) == "inactive"
        assert his._employee_employment_status({"ISDELETED": 0, "VALIDSTATE": 1}) == "active"

    def test_stop_flag(self):
        assert his._normalize_stop_flag(None) == "active"
        assert his._normalize_stop_flag("0") == "active"
        assert his._normalize_stop_flag("1") == "inactive"


class TestCollectorStatus:
    def test_staff_status_not_inverted(self):
        # 修复前 _normalize_status 将 STATUS=1（在用）错误归一为 inactive
        assert collector._normalize_staff_status("1") == "active"
        assert collector._normalize_staff_status("0") == "inactive"
        assert collector._normalize_staff_status(None) == "unknown"

    def test_stop_flag(self):
        assert collector._normalize_status(None) == "active"
        assert collector._normalize_status("0") == "active"
        assert collector._normalize_status("1") == "inactive"


class TestSourceTableConstants:
    def test_sys_employee_owner_is_fxhis(self):
        # 活库实测 SYS_EMPLOYEE 仅存在于 FXHIS，COMM.SYS_EMPLOYEE 会 ORA-00942
        assert collector.EMPLOYEE_SOURCE_TABLE == "FXHIS.SYS_EMPLOYEE"
        assert his.EMPLOYEE_TABLE == "FXHIS.SYS_EMPLOYEE"
