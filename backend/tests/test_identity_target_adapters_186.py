"""186 v1.10 S1 专项：目标适配器恢复归因 CAS + P0-10 判定纯逻辑测试。

覆盖（fake cursor/connection 驱动**真实**适配器方法，不 mock 适配器内部）：

- T51/P0-16：CDMS ``_fetch_user_state`` 大小写不敏感 → 规范小写键全链
  （lock_user 0→1、read-back、commit、条件更新 SQL；already_locked 零
  UPDATE；missing_target；read-back 不符回滚）。
- P0-17：CDMS unlock_user CAS（origin raw 匹配成功且绑定 expected_changed；
  origin 缺失 attribution_unknown；人工改时间 attribution_target_changed
  零 UPDATE；CAS rowcount=0 blocked+rollback；状态非 1 unexpected_state）。
- P0-4/P0-9：JHEMR lock_account 返回 locked_time_raw；unlock_account 精确
  比对（目标值哪怕变化 1 秒 → blocked；±300 容差已删除）；两侧缺值 →
  attribution_unknown；CAS rowcount!=1 重读分类。
- P0-10：sys_user_row_in_scope fail-closed（TYPE NULL/非 1 一律不在范围）、
  多账号聚合（任一停用→disabled_multi；其余→unknown multi_account）、
  target_time_unchanged None/True/False 三态。
- T50：适配器层只做变更检测（同值重锁允许通过），不承担锁所有权判断
  ——所有权证据在编排/门禁层关闭（本文件用注释与断言固化该边界）。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.cdms_identity_adapter import (
    _SQL_LOCK_USER,
    _SQL_UNLOCK_USER_CAS,
    CdmsIdentityAdapter,
)
from app.services.identity_account_state import (
    aggregate_user_state,
    sys_user_row_in_scope,
    target_time_unchanged,
)
from app.services.jhemr_identity_adapter import (
    JhemrIdentityAdapter,
    JhemrIdentityError,
    _normalize_raw_time,
)

LOCK_TS = datetime(2026, 9, 2, 3, 4, 5)
LOCK_TS_RAW = "2026-09-02T03:04:05"

ORIGIN_DISABLE = {
    "attempt_id": 77,
    "target_raw_time": LOCK_TS_RAW,
    "target_account_fingerprint": "fp-target-186",
    "rule_version": "dual_source_v1",
}


@pytest.fixture(autouse=True)
def clean_test_database():
    """覆盖根 conftest 的数据库 autouse fixture（与本仓库纯逻辑子目录
    conftest 的 no-op 模式一致）：本文件全部用 fake 连接/纯逻辑驱动，
    不创建、不连接 APP_TEST_DB_URL 指向的任何数据库。"""
    yield


# ---------------------------------------------------------------------------
# Fake infrastructure（description + execute 记录 + fetchone 队列 + rowcount
# + commit/rollback 记录；两个真实适配器方法在这些假连接上全链运行）
# ---------------------------------------------------------------------------


class FakeResultSet:
    """One scripted statement outcome: description columns + rows + rowcount."""

    def __init__(self, description=None, rows=None, rowcount=0):
        self.description = description
        self.rows = list(rows or [])
        self.rowcount = rowcount


class FakeOracleConnection:
    """Oracle 风格假连接：cursor() 无参；行是 tuple（description 对齐）。"""

    def __init__(self, results):
        self.results = list(results)
        self.executed: list[tuple[str, dict | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, *args, **kwargs):
        return FakeOracleCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeOracleCursor:
    def __init__(self, conn: FakeOracleConnection):
        self._conn = conn
        self.rowcount = -1
        self.description = None
        self._rows: list[tuple] = []
        self.closed = False

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        result = self._conn.results.pop(0) if self._conn.results else FakeResultSet()
        self.description = result.description
        self.rowcount = result.rowcount
        self._rows = list(result.rows)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows

    def close(self):
        self.closed = True


class FakePgConnection:
    """psycopg 风格假连接：cursor(row_factory=...)；SELECT 行是 dict。"""

    def __init__(self, results):
        self.results = list(results)
        self.executed: list[tuple[str, tuple | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, row_factory=None):
        return FakePgCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakePgCursor:
    def __init__(self, conn: FakePgConnection):
        self._conn = conn
        self.rowcount = -1
        self.description = None
        self._rows: list[dict] = []
        self.closed = False

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        result = self._conn.results.pop(0) if self._conn.results else FakeResultSet()
        self.description = result.description
        self.rowcount = result.rowcount
        self._rows = list(result.rows)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows

    def close(self):
        self.closed = True


def _make_cdms_adapter(results) -> tuple[CdmsIdentityAdapter, FakeOracleConnection]:
    adapter = CdmsIdentityAdapter(
        credential_ref="file:///tmp/fake-cred-186",
        jump_host="127.0.0.1",
        jump_port=22,
        jump_user="u",
        jump_key=None,
        oracle_client_lib="/opt/oracle",
    )
    conn = FakeOracleConnection(results)
    adapter._conn = conn  # 绕过 connect()：不建隧道、不碰真实驱动
    return adapter, conn


def _make_jhemr_adapter(results) -> tuple[JhemrIdentityAdapter, FakePgConnection]:
    adapter = JhemrIdentityAdapter(credential_ref="file:///tmp/fake-cred-186")
    conn = FakePgConnection(results)
    adapter._conn = conn
    adapter._dict_row = None  # 正常由 _open_db_connection 设置；假连接忽略
    return adapter, conn


def _cdms_row(state, changedate=LOCK_TS, columns=("FLOGINNAME", "FUSERSTATE", "FCHANGEDATE")):
    """真实 Oracle cursor.description 报大写列名；行是 tuple。"""
    return FakeResultSet(
        description=[(name,) for name in columns],
        rows=[("E001", state, changedate)],
    )


def _update_result(rowcount):
    return FakeResultSet(rowcount=rowcount)


def _update_calls(conn):
    # 注意 "FOR UPDATE" 读行也含 UPDATE 字样，只匹配以 UPDATE 开头的语句
    return [entry for entry in conn.executed if entry[0].upper().startswith("UPDATE")]


# ---------------------------------------------------------------------------
# 1. T51 / P0-16：CDMS 大小写全链（lock_user + _fetch_user_state 规范小写键）
# ---------------------------------------------------------------------------


class TestT51CdmsCaseInsensitiveLock:
    def test_lock_user_full_chain_success_with_uppercase_columns(self):
        adapter, conn = _make_cdms_adapter([
            _cdms_row("0"),            # FOR UPDATE 读（大写 description）
            _update_result(1),         # 条件 UPDATE 0→1
            _cdms_row("1"),            # read-back
        ])
        result = adapter.lock_user("E001")

        assert result["status"] == "success"
        assert result["rows_affected"] == 1
        assert result["changed_at_raw"] == LOCK_TS_RAW
        assert result["changed_at"] == str(LOCK_TS)  # 兼容键保留
        assert conn.commits == 1 and conn.rollbacks == 0
        # 写路径读取必须走 FOR UPDATE 变体
        assert "FOR UPDATE" in conn.executed[0][0]
        # 条件更新：只从 FUSERSTATE='0' 出发
        updates = _update_calls(conn)
        assert len(updates) == 1
        assert updates[0][0] == _SQL_LOCK_USER
        assert "FUSERSTATE = '0'" in updates[0][0]

    def test_fetch_user_state_maps_uppercase_description_to_canonical_keys(self):
        adapter, _ = _make_cdms_adapter([
            FakeResultSet(
                description=[("FLOGINNAME",), ("FUSERSTATE",), ("FCHANGEDATE",)],
                rows=[("E001", "0", LOCK_TS)],
            )
        ])
        state = adapter.read_account_state("E001")
        # P0-16 全链修复：调用方读规范小写键，绝不再出现大写键
        assert set(state.keys()) == {"floginname", "fuserstate", "fchangedate"}
        assert state["fuserstate"] == "0"
        assert state["fchangedate"] == LOCK_TS

    def test_fetch_user_state_ignores_unknown_columns(self):
        adapter, _ = _make_cdms_adapter([
            FakeResultSet(
                description=[("FLOGINNAME",), ("EXTRA_COL",), ("FUSERSTATE",), ("FCHANGEDATE",)],
                rows=[("E001", "noise", "1", LOCK_TS)],
            )
        ])
        state = adapter.read_account_state("E001")
        assert set(state.keys()) == {"floginname", "fuserstate", "fchangedate"}

    def test_already_locked_skips_with_zero_updates(self):
        adapter, conn = _make_cdms_adapter([_cdms_row("1")])
        result = adapter.lock_user("E001")
        assert result == {"status": "skipped", "reason": "already_locked", "emp_no": "E001"}
        assert _update_calls(conn) == []
        assert conn.commits == 0 and conn.rollbacks == 0

    def test_missing_target_reported_not_created(self):
        adapter, conn = _make_cdms_adapter([FakeResultSet(
            description=[("FLOGINNAME",), ("FUSERSTATE",), ("FCHANGEDATE",)], rows=[],
        )])
        result = adapter.lock_user("E404")
        assert result["status"] == "missing_target"
        assert _update_calls(conn) == []

    def test_readback_mismatch_fails_and_rolls_back(self):
        adapter, conn = _make_cdms_adapter([
            _cdms_row("0"),
            _update_result(1),
            _cdms_row("0"),  # read-back 仍是 0 → 不符
        ])
        result = adapter.lock_user("E001")
        assert result["status"] == "failed"
        assert "read-back" in result["reason"]
        assert conn.rollbacks == 1 and conn.commits == 0


# ---------------------------------------------------------------------------
# 2. P0-17：CDMS unlock_user（变更检测 CAS）
# ---------------------------------------------------------------------------


class TestCdmsUnlockCas:
    def test_origin_raw_match_success_binds_expected_changed(self):
        adapter, conn = _make_cdms_adapter([
            _cdms_row("1", LOCK_TS),   # FOR UPDATE 读
            _update_result(1),         # CAS UPDATE
            _cdms_row("0"),            # read-back
        ])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)

        assert result["status"] == "success"
        assert result["lock_attribution"] == "by_this_rule"
        assert result["origin_disable_attempt_id"] == 77
        assert conn.commits == 1
        updates = _update_calls(conn)
        assert len(updates) == 1 and updates[0][0] == _SQL_UNLOCK_USER_CAS
        assert "FCHANGEDATE = :expected_changed" in updates[0][0]
        # 绑定值是 datetime（与 Oracle FCHANGEDATE 可比），从 origin raw 解析
        assert updates[0][1]["expected_changed"] == LOCK_TS

    def test_origin_disable_missing_blocks_attribution_unknown(self):
        adapter, conn = _make_cdms_adapter([_cdms_row("1", LOCK_TS)])
        result = adapter.unlock_user("E001", origin_disable=None)
        assert result["status"] == "blocked"
        assert result["reason"] == "attribution_unknown"
        assert result["lock_attribution"] == "manual_or_unknown"
        assert _update_calls(conn) == []

    def test_origin_raw_time_none_blocks_attribution_unknown(self):
        origin = dict(ORIGIN_DISABLE, target_raw_time=None)
        adapter, conn = _make_cdms_adapter([_cdms_row("1", LOCK_TS)])
        result = adapter.unlock_user("E001", origin_disable=origin)
        assert result["reason"] == "attribution_unknown"
        assert _update_calls(conn) == []

    def test_current_changedate_null_blocks_attribution_unknown(self):
        adapter, conn = _make_cdms_adapter([_cdms_row("1", None)])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)
        assert result["reason"] == "attribution_unknown"
        assert _update_calls(conn) == []

    def test_unparsable_origin_raw_blocks_attribution_unknown(self):
        origin = dict(ORIGIN_DISABLE, target_raw_time="not-a-timestamp")
        # 当前行 FCHANGEDATE 与 origin 字符串相等 → 比对通过，但解析失败
        adapter, conn = _make_cdms_adapter([_cdms_row("1", "not-a-timestamp")])
        result = adapter.unlock_user("E001", origin_disable=origin)
        assert result["reason"] == "attribution_unknown"
        assert _update_calls(conn) == []

    def test_manually_changed_time_blocks_with_zero_updates(self):
        # 人工改时间（哪怕 1 秒）→ 变更检测失败；±300 容差已删除
        adapter, conn = _make_cdms_adapter([
            _cdms_row("1", datetime(2026, 9, 2, 3, 4, 6)),
        ])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "blocked"
        assert result["reason"] == "attribution_target_changed"
        assert _update_calls(conn) == []
        assert conn.commits == 0

    def test_cas_rowcount_zero_blocks_and_rolls_back(self):
        # 预比对通过但 CAS UPDATE 抢不到行（并发改动）→ blocked + rollback
        adapter, conn = _make_cdms_adapter([
            _cdms_row("1", LOCK_TS),
            _update_result(0),
        ])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "blocked"
        assert result["reason"] == "attribution_target_changed"
        assert conn.rollbacks == 1 and conn.commits == 0

    def test_unexpected_state_blocks(self):
        adapter, conn = _make_cdms_adapter([_cdms_row("2", LOCK_TS)])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "blocked"
        assert result["reason"] == "unexpected_state"
        assert _update_calls(conn) == []

    def test_already_enabled_skips(self):
        adapter, conn = _make_cdms_adapter([_cdms_row("0", LOCK_TS)])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_enabled"
        assert _update_calls(conn) == []

    def test_missing_target(self):
        adapter, conn = _make_cdms_adapter([FakeResultSet(
            description=[("FLOGINNAME",), ("FUSERSTATE",), ("FCHANGEDATE",)], rows=[],
        )])
        result = adapter.unlock_user("E404", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "missing_target"


# ---------------------------------------------------------------------------
# 3. P0-4/P0-9：JHEMR lock_account / unlock_account
# ---------------------------------------------------------------------------


def _jhemr_read_row(status, locked_time=LOCK_TS, for_update=False):
    row = {"user_id": "E001", "account_status": status, "locked_time": locked_time}
    return FakeResultSet(description=[("USER_ID",), ("ACCOUNT_STATUS",), ("LOCKED_TIME",)],
                         rows=[row])


class TestJhemrLockUnlock:
    def test_lock_account_returns_locked_time_raw(self):
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row(0, None),          # FOR UPDATE 读：启用、未锁
            _update_result(1),                 # UPDATE → 8 + CURRENT_TIMESTAMP
            _jhemr_read_row(8, LOCK_TS),       # read-back：锁定时间真实值
        ])
        result = adapter.lock_account("E001")
        assert result["status"] == "success"
        assert result["account_status"] == 8
        assert result["locked_time_raw"] == LOCK_TS_RAW  # datetime → isoformat
        assert conn.commits == 1

    def test_lock_account_readback_null_locked_time_fails_closed(self):
        # 既有活库契约（103：锁定必须伴随非空 locked_time）不放宽：
        # read-back locked_time 为 NULL → 异常回滚，locked_time_raw=None
        # 只在规范化层出现（见 test_raw_time_normalization_variants）。
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row(0, None),
            _update_result(1),
            _jhemr_read_row(8, None),   # read-back：locked_time 仍 NULL
        ])
        with pytest.raises(JhemrIdentityError):
            adapter.lock_account("E001")
        assert conn.rollbacks == 1 and conn.commits == 0

    def test_unlock_origin_match_success(self):
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row("8", LOCK_TS),     # FOR UPDATE 读
            _update_result(1),                 # 条件 UPDATE 8→0
            _jhemr_read_row("0", LOCK_TS),     # read-back
        ])
        result = adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "success"
        assert result["account_status"] == 0
        assert result["lock_attribution"] == "by_this_rule"
        assert result["origin_disable_attempt_id"] == 77
        assert conn.commits == 1 and conn.rollbacks == 0
        updates = _update_calls(conn)
        assert len(updates) == 1
        assert "CAST(account_status AS TEXT) = %s" in updates[0][0]

    def test_unlock_target_changed_by_one_second_blocks(self):
        # ±300 容差已删除：1 秒差异（旧实现会放行）必须 blocked
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row("8", datetime(2026, 9, 2, 3, 4, 6)),
        ])
        result = adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "blocked"
        assert result["reason"] == "attribution_target_changed"
        assert _update_calls(conn) == []
        assert conn.commits == 0

    @pytest.mark.parametrize(
        "origin,current_locked",
        [
            (None, LOCK_TS),                    # origin_disable=None
            (dict(ORIGIN_DISABLE, target_raw_time=None), LOCK_TS),  # origin raw 缺失
            (ORIGIN_DISABLE, None),             # 当前行 locked_time 为 NULL
        ],
        ids=["no_origin_disable", "origin_raw_none", "current_raw_none"],
    )
    def test_unlock_attribution_unknown_paths(self, origin, current_locked):
        adapter, conn = _make_jhemr_adapter([_jhemr_read_row("8", current_locked)])
        result = adapter.unlock_account("E001", origin_disable=origin)
        assert result["status"] == "blocked"
        assert result["reason"] == "attribution_unknown"
        assert _update_calls(conn) == []

    def test_unlock_rowcount_zero_recheck_already_enabled_skips(self):
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row("8", LOCK_TS),
            _update_result(0),                    # 并发已恢复
            _jhemr_read_row("0", LOCK_TS),        # 重读：已是 0
        ])
        result = adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_enabled"

    def test_unlock_rowcount_zero_recheck_still_locked_raises(self):
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row("8", LOCK_TS),
            _update_result(0),
            _jhemr_read_row("8", LOCK_TS),        # 重读：仍 8 → raise 回滚
        ])
        with pytest.raises(JhemrIdentityError):
            adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert conn.rollbacks == 1 and conn.commits == 0

    def test_unlock_already_enabled_skips(self):
        adapter, conn = _make_jhemr_adapter([_jhemr_read_row("0", LOCK_TS)])
        result = adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_enabled"

    def test_unlock_unexpected_state_blocks(self):
        adapter, conn = _make_jhemr_adapter([_jhemr_read_row("5", LOCK_TS)])
        result = adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "blocked"
        assert result["reason"] == "unexpected_state"

    def test_unlock_missing_target(self):
        adapter, _ = _make_jhemr_adapter([FakeResultSet(rows=[])])
        result = adapter.unlock_account("E404", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "missing_target"

    def test_raw_time_normalization_variants(self):
        # 同一规范化在比对两侧一致：datetime 与等价 isoformat 字符串全等
        assert _normalize_raw_time(LOCK_TS) == LOCK_TS_RAW
        assert _normalize_raw_time(f"  {LOCK_TS_RAW}  ") == LOCK_TS_RAW
        assert _normalize_raw_time(None) is None
        assert _normalize_raw_time(8) == "8"
        # JHEMR unlock：origin 传带空格字符串与当前 datetime 应比对通过
        origin = dict(ORIGIN_DISABLE, target_raw_time=f"  {LOCK_TS_RAW}  ")
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row("8", LOCK_TS),
            _update_result(1),
            _jhemr_read_row("0", LOCK_TS),
        ])
        result = adapter.unlock_account("E001", origin_disable=origin)
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# 4. P0-10：判定纯逻辑（范围 fail-closed / 多账号聚合 / target_time_unchanged）
# ---------------------------------------------------------------------------


class TestP010ScopeFailClosed:
    def test_null_type_row_out_of_scope_even_with_empl_code(self):
        # 旧实现的 EMPL_CODE 回退分支已删除：NULL TYPE 一律不在范围
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": None}) is False
        assert sys_user_row_in_scope({"EMPL_CODE": "E001"}) is False  # 键缺失同理

    def test_blank_type_out_of_scope(self):
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": ""}) is False
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": "  "}) is False

    def test_non_employee_type_out_of_scope(self):
        assert sys_user_row_in_scope({"EMPL_CODE": "X", "TYPE": "100", "USERFLAG": "P"}) is False
        assert sys_user_row_in_scope({"EMPL_CODE": "X", "TYPE": 100}) is False

    def test_employee_type_in_scope(self):
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": "1"}) is True

    def test_null_type_rows_excluded_from_aggregation(self):
        # 全部行 TYPE NULL → 无范围内行 → unknown（fail-closed，不凭空聚合）
        state, reason = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": None},
        ])
        assert state == "unknown"
        assert reason == "sys_user_missing_or_out_of_scope"


class TestP010MultiAccountAggregation:
    def test_two_enabled_rows_are_unknown_not_enabled(self):
        # 多账号未证实范围不得聚合为 enabled
        state, reason = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
        ])
        assert state == "unknown"
        assert reason == "sys_user_multi_account_unconfirmed"

    def test_two_rows_one_disabled_is_disabled_multi(self):
        state, reason = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
            {"EMPL_CODE": "E001", "STATUS": "1", "TYPE": "1"},
        ])
        assert state == "disabled"
        assert reason == "sys_user_status_disabled_multi"

    def test_two_rows_one_unknown_is_unknown_multi(self):
        state, reason = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
            {"EMPL_CODE": "E001", "STATUS": None, "TYPE": "1"},
        ])
        assert state == "unknown"
        assert reason == "sys_user_multi_account_unconfirmed"

    def test_single_row_keeps_direct_semantics(self):
        assert aggregate_user_state(
            [{"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"}]
        ) == ("enabled", "sys_user_status_enabled")
        assert aggregate_user_state(
            [{"EMPL_CODE": "E001", "STATUS": "1", "TYPE": "1"}]
        ) == ("disabled", "sys_user_status_disabled")


class TestTargetTimeUnchanged:
    def test_none_tri_state_when_either_side_missing(self):
        assert target_time_unchanged(None, LOCK_TS_RAW) is None
        assert target_time_unchanged(LOCK_TS, None) is None
        assert target_time_unchanged(None, None) is None

    def test_true_on_exact_match(self):
        assert target_time_unchanged(LOCK_TS, LOCK_TS_RAW) is True
        assert target_time_unchanged(LOCK_TS_RAW, LOCK_TS) is True
        assert target_time_unchanged(f" {LOCK_TS_RAW} ", LOCK_TS_RAW) is True

    def test_false_on_any_difference(self):
        # 无容差：1 秒、1 微秒、时区后缀差异都判定为“目标已变化”
        one_second = datetime(2026, 9, 2, 3, 4, 6)
        one_micro = datetime(2026, 9, 2, 3, 4, 5, 1)
        assert target_time_unchanged(one_second, LOCK_TS_RAW) is False
        assert target_time_unchanged(one_micro, LOCK_TS_RAW) is False
        assert target_time_unchanged(f"{LOCK_TS_RAW}+00:00", LOCK_TS_RAW) is False


# ---------------------------------------------------------------------------
# 5. T50：适配器层只做变更检测，不承担锁所有权判断
# ---------------------------------------------------------------------------


class TestT50AdapterChangeDetectionNotOwnership:
    """停用后“人工同秒重锁”（目标 raw 与 origin 相同）在适配器层允许通过。

    这是刻意设计（186 v1.10 §13.3）：时间一致不是锁所有权证明；适配器
    只负责“目标行未被再次修改”的变更检测。人工同秒重锁、平台停用证据
    伪造等所有权风险由编排/门禁层（平台持久停用证据 + attempt 指纹 +
    rule_version）关闭。下方断言固化该职责边界：同值 → 适配器放行。
    """

    def test_jhemr_same_raw_relock_passes_adapter_layer(self):
        # 目标 raw 与 origin 完全相同（人工同秒重锁的不可区分场景）
        adapter, conn = _make_jhemr_adapter([
            _jhemr_read_row("8", LOCK_TS),
            _update_result(1),
            _jhemr_read_row("0", LOCK_TS),
        ])
        result = adapter.unlock_account("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "success"
        assert result["lock_attribution"] == "by_this_rule"
        assert conn.commits == 1

    def test_cdms_same_raw_relock_passes_adapter_layer(self):
        adapter, conn = _make_cdms_adapter([
            _cdms_row("1", LOCK_TS),
            _update_result(1),
            _cdms_row("0"),
        ])
        result = adapter.unlock_user("E001", origin_disable=ORIGIN_DISABLE)
        assert result["status"] == "success"
        assert result["lock_attribution"] == "by_this_rule"

    def test_adapters_do_not_judge_ownership_only_change(self):
        # 反证边界：目标值一旦变化（哪怕 1 秒）适配器必拦 —— 适配器的全部
        # 判断依据只有“原始值精确不变”，不存在时间所有权推断。
        jhemr, jconn = _make_jhemr_adapter([_jhemr_read_row("8", datetime(2026, 9, 2, 3, 4, 6))])
        assert jhemr.unlock_account("E001", origin_disable=ORIGIN_DISABLE)["reason"] == \
            "attribution_target_changed"
        cdms, cconn = _make_cdms_adapter([_cdms_row("1", datetime(2026, 9, 2, 3, 4, 6))])
        assert cdms.unlock_user("E001", origin_disable=ORIGIN_DISABLE)["reason"] == \
            "attribution_target_changed"
        assert _update_calls(jconn) == [] and _update_calls(cconn) == []
