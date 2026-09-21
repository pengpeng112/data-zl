"""192 D3: users_sublogin / users_subsign existence checks must not lock rows.

The JHEMR sync account holds SELECT+INSERT only on those two tables. PostgreSQL
(JHEMR is 9.2) requires UPDATE privilege for ``SELECT ... FOR UPDATE``, so the
first real nightly fill (RUN-933bc679ad7f, 2026-09-16) failed with
InsufficientPrivilege on the very first account and rolled back all 36 repairs.

The fake connection below enforces that grant model: any FOR UPDATE that touches
the two child tables raises, exactly like the target database does.
"""

from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

RESTRICTED_TABLES = ("jhemr.users_sublogin", "jhemr.users_subsign")
WAYS = ["0", "2", "4"]


class _InsufficientPrivilege(Exception):
    pass


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=()):
        self._conn.sql_log.append(sql)
        if "FOR UPDATE" in sql and any(t in sql for t in RESTRICTED_TABLES):
            raise _InsufficientPrivilege("permission denied for relation")
        self._rows, self.rowcount = self._conn.respond(sql)

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _FakeConn:
    """Minimal JHEMR stand-in: user exists, control row exists, all ways missing."""

    def __init__(self, emp_no, hospital_no):
        self.emp_no = emp_no
        self.hospital_no = hospital_no
        self.sql_log = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, row_factory=None):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def respond(self, sql):
        if sql.startswith("INSERT") or sql.startswith("UPDATE"):
            return [], 1
        if "FROM jhemr.users_control_mode" in sql:
            if "in_sign_way, login_way, in_pic_mode" in sql:
                return [{"in_sign_way": "", "login_way": "", "in_pic_mode": ""}], 0
            return [{"user_id": self.emp_no}], 0
        if "SELECT sign_way, default_flag FROM jhemr.users_subsign" in sql:
            return [{"sign_way": w, "default_flag": "1" if w == "0" else "0"} for w in WAYS], 0
        if "SELECT sign_way FROM jhemr.users_subsign" in sql:
            return [{"sign_way": w} for w in WAYS], 0
        if "SELECT login_way FROM jhemr.users_sublogin" in sql:
            return [{"login_way": w} for w in WAYS], 0
        if "SELECT user_id FROM jhemr.users_sublogin" in sql or "SELECT user_id FROM jhemr.users_subsign" in sql:
            return [], 0
        if "FROM jhemr.users " in sql:
            return [{"user_id": self.emp_no}], 0
        raise AssertionError(f"unexpected SQL in fake connection: {sql}")


def _adapter_with(conn):
    adapter = JhemrIdentityAdapter(
        credential_ref="test-cred",
        hospital_no=conn.hospital_no,
        jump_key="unused",
        known_hosts="unused",
    )
    adapter._conn = conn
    adapter._dict_row = None
    return adapter


def _repair(emp_no):
    return {
        "user_id": emp_no,
        "insert_control": False,
        "login_ways": list(WAYS),
        "sign_ways": [
            {"sign_way": "0", "default_flag": "1"},
            {"sign_way": "2", "default_flag": "0"},
            {"sign_way": "4", "default_flag": "0"},
        ],
        "fix_default": False,
    }


def test_gap_fill_succeeds_with_select_insert_only_grant():
    conn = _FakeConn("004076", "H1")
    result = _adapter_with(conn).apply_login_sign_gaps([_repair("004076")])

    assert result["status"] == "success"
    assert result["sublogin_inserted"] == 3
    assert result["subsign_inserted"] == 3
    assert result["control_inserted"] == 0
    assert result["default_repaired"] == 0
    assert conn.commits == 1
    assert conn.rollbacks == 0
    inserts = [s for s in conn.sql_log if s.startswith("INSERT")]
    assert sum("jhemr.users_sublogin" in s for s in inserts) == 3
    assert sum("jhemr.users_subsign" in s for s in inserts) == 3


def test_child_table_existence_checks_never_lock_rows_but_parent_still_does():
    conn = _FakeConn("004076", "H1")
    _adapter_with(conn).apply_login_sign_gaps([_repair("004076")])

    child_selects = [
        s for s in conn.sql_log
        if s.startswith("SELECT") and any(t in s for t in RESTRICTED_TABLES)
    ]
    assert child_selects, "existence checks on child tables must still run"
    assert all("FOR UPDATE" not in s for s in child_selects)
    assert any("FROM jhemr.users " in s and "FOR UPDATE" in s for s in conn.sql_log)


def test_multi_account_batch_stays_single_transaction():
    conn = _FakeConn("004076", "H1")
    result = _adapter_with(conn).apply_login_sign_gaps([_repair("004076"), _repair("004077")])

    assert result["status"] == "success"
    assert result["sublogin_inserted"] == 6
    assert result["subsign_inserted"] == 6
    assert conn.commits == 1
    assert conn.rollbacks == 0
