"""JHEMR (Vastbase / PostgreSQL-compatible) identity account adapter.

Creates a missing account or idempotently aligns an existing account across
``users``, ``user_dept``, ``jhauth_user_vs_role_group``,
``users_control_mode``, ``users_sublogin`` and ``users_subsign`` for tenant
``49557032X``.

Hard rules:
- Existing department and role bindings are additive: never DELETE and never
  remove or replace historical bindings.
- New-account creation and an explicitly requested existing-account password
  reset use the controlled SM4 secret path and the password-write gate.
- Never write ``jhauth_user_vs_role`` or ``jhauth_user_vs_permission``.
- One transaction per operation; read-back before COMMIT and full ROLLBACK on
  any failure.
- All SQL is parameterized (``%s``); no string interpolation of values.
- Audit-safe: passwords and personal identifiers are masked before any row
  leaves this module; credential file contents are never logged.

Connection: the database is only reachable through the platform SSH jump host
(``root@10.10.8.83`` by default, public-key auth). ``connect()`` opens a local
``ssh -L`` forward and psycopg connects to ``127.0.0.1:<local_port>``.

Live schema note: ``user_dept`` and ``jhauth_user_vs_role_group`` are keyed by
``user_id`` (FK -> ``users.user_id``), not by ``db_user``. The adapter therefore
resolves ``db_user -> user_id`` from ``users`` first and uses ``user_id`` for
all child-table reads and inserts.
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

try:  # reuse the platform credential_ref resolver when running inside the app
    from .credentials import resolve as _resolve_credential_ref
except Exception:  # pragma: no cover - standalone use without the app package
    _resolve_credential_ref = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

from .identity_password import compute_password_fields, get_shanghai_date_str

JHEMR_HOSPITAL_NO = "49557032X"

# Classification -> role group. 药师 (pharmacist) reuses the doctor group per
# user-confirmed policy (no pharmacist-specific role exists in JHEMR).
ROLE_GROUP_MAP = {"doctor": "001", "pharmacist": "001", "nurse": "002"}

# Verified authorization chain (doc 103 §13):
#   001 -> role 25  临床医疗      -> DOCTOR/0 住院医师
#   002 -> role 101 临床护理-护士 -> NURSE/1  责任护士
ROLE_CHAIN = {
    "001": {
        "role_id": "25",
        "role_name": "临床医疗",
        "default_role": "DOCTOR/0",
        "default_name": "住院医师",
    },
    "002": {
        "role_id": "101",
        "role_name": "临床护理-护士",
        "default_role": "NURSE/1",
        "default_name": "责任护士",
    },
}

WRITE_POLICY = "identity_account_sync"

TEMPLATE_VERSION = "jhemr-login-v1"

# Never written by this adapter (documented guardrail).
FORBIDDEN_WRITE_TABLES = (
    "jhauth_user_vs_role",
    "jhauth_user_vs_permission",
    "user_pwd",
    "user_pwd_sm",
)

CONTROL_MODE_DEFAULTS = {
    "in_sign_way": "0,2,4",
    "login_way": "0,2,4",
    "in_pic_mode": "2,2,2",
    "sign_box": "0",
    "default_loginway": "",
    "double_login": "-1",
}

SUBLOGIN_DEFAULTS = [
    {"file_visit_type": "2", "login_way": "0"},
    {"file_visit_type": "2", "login_way": "2"},
    {"file_visit_type": "2", "login_way": "4"},
]

SUBSIGN_DEFAULTS = [
    {"file_visit_type": "2", "sign_way": "0", "picmode": "2", "default_flag": "1"},
    {"file_visit_type": "2", "sign_way": "2", "picmode": "2", "default_flag": "0"},
    {"file_visit_type": "2", "sign_way": "4", "picmode": "2", "default_flag": "0"},
]

# users columns that must never appear in plaintext in snapshots/audit/logs.
SENSITIVE_USER_FIELDS = {
    "user_pwd",
    "user_pwd_sm",
    "is_sm",
    "identification",
    "phonenumber",
    "ca_no",
    "user_pki",
    "expiry_date_user_pki",
    "expired_time_user_pki",
    "mailbox",
    "wechat",
}

_DEFAULT_DB_HOST = "10.10.8.177"
_DEFAULT_DB_PORT = 5432
_DEFAULT_DB_NAME = "jhemr"
_DEFAULT_JUMP_KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519_ai")
_DEFAULT_KNOWN_HOSTS = os.path.join(os.path.expanduser("~"), ".ssh", "known_hosts")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_credentials(credential_ref: str) -> tuple[str, str]:
    """Resolve ``credential_ref`` to ``(username, password)``.

    Accepts ``file://<path>``, ``env:<VAR>`` (via the platform resolver) or a
    bare filesystem path. The file format is a single ``username:password``
    line. Contents are never logged.
    """
    user: str | None = None
    password: str | None = None
    if _resolve_credential_ref is not None:
        user, password = _resolve_credential_ref(credential_ref)
    if not user or not password:
        raw_ref = (credential_ref or "").strip()
        path_str = raw_ref[7:] if raw_ref.startswith("file://") else raw_ref
        try:
            content = Path(path_str).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise JhemrIdentityError(
                f"cannot read JHEMR write credential file for ref '{raw_ref}': "
                f"{type(exc).__name__}"
            ) from exc
        if ":" in content:
            user, password = content.split(":", 1)
    if not user or not password:
        raise JhemrIdentityError(
            "JHEMR write credential could not be resolved "
            "(expected 'username:password')"
        )
    return user, password


def _mask(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class JhemrIdentityError(RuntimeError):
    """Raised for JHEMR identity-sync failures (connection, schema, policy)."""


class JhemrIdentityAdapter:
    """Idempotent, insert-only JHEMR identity account adapter.

    The adapter is a context manager::

        with JhemrIdentityAdapter(credential_ref="file:///etc/.../jhemr_identity_sync.write") as jhemr:
            plan = jhemr.dry_run_single_user(emp_no, "doctor", ["A001"], "001")
    """

    HOSPITAL_NO_DEFAULT = JHEMR_HOSPITAL_NO
    WRITE_POLICY = WRITE_POLICY

    def __init__(
        self,
        credential_ref: str,
        hospital_no: str = JHEMR_HOSPITAL_NO,
        jump_host: str = "10.10.8.83",
        jump_port: int = 22,
        jump_user: str = "root",
        jump_key: str | None = None,
        *,
        db_host: str | None = None,
        db_port: int | None = None,
        db_name: str | None = None,
        known_hosts: str | None = None,
        connect_timeout: int = 10,
        statement_timeout_ms: int = 30_000,
        password_secret_ref: str = "",
        password_write_enabled: bool = False,
        sync_operator_id: str = "IDENTITY_SYNC",
    ) -> None:
        self.credential_ref = credential_ref
        self.hospital_no = hospital_no or JHEMR_HOSPITAL_NO
        self.jump_host = jump_host
        self.jump_port = int(jump_port)
        self.jump_user = jump_user
        self.jump_key = jump_key or os.environ.get("APP_SSH_JUMP_KEY") or _DEFAULT_JUMP_KEY
        self.db_host = db_host or os.environ.get("APP_JHEMR_DB_HOST") or _DEFAULT_DB_HOST
        self.db_port = int(db_port or os.environ.get("APP_JHEMR_DB_PORT") or _DEFAULT_DB_PORT)
        self.db_name = db_name or os.environ.get("APP_JHEMR_DB_NAME") or _DEFAULT_DB_NAME
        self.known_hosts = known_hosts or os.environ.get("APP_SSH_KNOWN_HOSTS") or _DEFAULT_KNOWN_HOSTS
        self.connect_timeout = int(connect_timeout)
        self.statement_timeout_ms = int(statement_timeout_ms)
        self.password_secret_ref = password_secret_ref
        self.password_write_enabled = bool(password_write_enabled)
        self.sync_operator_id = sync_operator_id

        self._conn: Any = None
        self._driver: str | None = None
        self._tunnel: subprocess.Popen | None = None
        self._local_port: int | None = None
        self._lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------------

    def connect(self) -> Any:
        """Open the SSH tunnel (if needed) and the psycopg connection."""
        with self._lock:
            if self._conn is not None:
                return self._conn
            direct = os.environ.get("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "").strip().lower() in {"1", "true", "yes"}
            if not direct and self._tunnel is None:
                self._start_tunnel()
            try:
                self._open_db_connection(direct=direct)
            except Exception:
                self._stop_tunnel()
                raise
            return self._conn

    def close(self) -> None:
        """Close the database connection and tear down the SSH tunnel."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
                self._driver = None
            self._stop_tunnel()

    def __enter__(self) -> "JhemrIdentityAdapter":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _free_local_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _start_tunnel(self) -> None:
        local_port = self._free_local_port()
        cmd = [
            "ssh",
            "-N",
            "-p", str(self.jump_port),
            "-i", self.jump_key,
            "-L", f"127.0.0.1:{local_port}:{self.db_host}:{self.db_port}",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={self.known_hosts}",
            "-o", f"ConnectTimeout={self.connect_timeout}",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            f"{self.jump_user}@{self.jump_host}",
        ]
        creationflags = 0
        if os.name == "nt":  # keep the helper console hidden on Windows
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            stderr = ""
            try:
                stderr = (proc.stderr.read() or b"").decode("utf-8", "replace")
            except Exception:
                pass
            raise JhemrIdentityError(
                f"SSH tunnel to {self.jump_host}:{self.jump_port} exited early: "
                f"{stderr.strip()[:300]}"
            )
        self._tunnel = proc
        self._local_port = local_port

    def _stop_tunnel(self) -> None:
        proc = self._tunnel
        self._tunnel = None
        self._local_port = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass

    def _open_db_connection(self, *, direct: bool = False) -> None:
        user, password = _resolve_credentials(self.credential_ref)
        options = f"-c statement_timeout={self.statement_timeout_ms}"
        try:
            import psycopg
            from psycopg.rows import dict_row

            conn = psycopg.connect(
                host=self.db_host if direct else "127.0.0.1",
                port=self.db_port if direct else self._local_port,
                dbname=self.db_name,
                user=user,
                password=password,
                options=options,
                connect_timeout=self.connect_timeout,
            )
            self._driver = "psycopg"
            self._dict_row = dict_row
        except ImportError:
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(
                host=self.db_host if direct else "127.0.0.1",
                port=self.db_port if direct else self._local_port,
                dbname=self.db_name,
                user=user,
                password=password,
                options=options,
                connect_timeout=self.connect_timeout,
            )
            conn.autocommit = False
            self._driver = "psycopg2"
            self._dict_row = psycopg2.extras.RealDictCursor
        self._conn = conn

    def _ensure_conn(self) -> Any:
        if self._conn is None:
            self.connect()
        return self._conn

    def _fetch_all(self, sql: str, params: tuple) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        cur = conn.cursor(row_factory=self._dict_row)
        try:
            cur.execute(sql, params)
            # Vastbase may expose unquoted column labels in upper case even
            # through a PostgreSQL-compatible driver. Internal adapter logic
            # uses canonical lower-case schema names.
            return [
                {str(key).lower(): value for key, value in dict(row).items()}
                for row in cur.fetchall()
            ]
        finally:
            cur.close()

    def _fetch_one(self, sql: str, params: tuple) -> dict[str, Any] | None:
        rows = self._fetch_all(sql, params)
        return rows[0] if rows else None

    # -- snapshots (read-only) ----------------------------------------------

    def snapshot_user(self, emp_no: str) -> dict | None:
        row = self._fetch_user(emp_no)
        if row is None:
            return None
        return self._mask_user_row(row)

    def user_exists(self, emp_no: str) -> bool:
        row = self._fetch_one(
            "SELECT db_user FROM jhemr.users WHERE db_user = %s AND hospital_no = %s",
            (str(emp_no).strip(), self.hospital_no),
        )
        return row is not None

    def snapshot_user_dept(self, emp_no: str) -> list[dict]:
        user = self._fetch_user(emp_no)
        if user is None:
            return []
        rows = self._fetch_all(
            "SELECT user_id, user_dept, hospital_no, default_dept_flag, state, "
            "start_date, end_date FROM jhemr.user_dept "
            "WHERE user_id = %s AND hospital_no = %s ORDER BY user_dept",
            (user["user_id"], self.hospital_no),
        )
        return [self._jsonable(row) for row in rows]

    def snapshot_role_groups(self, emp_no: str) -> list[dict]:
        user = self._fetch_user(emp_no)
        if user is None:
            return []
        rows = self._fetch_all(
            "SELECT user_id, role_group_id, hospital_no "
            "FROM jhemr.jhauth_user_vs_role_group "
            "WHERE user_id = %s AND hospital_no = %s ORDER BY role_group_id",
            (user["user_id"], self.hospital_no),
        )
        return [self._jsonable(row) for row in rows]

    def snapshot_control_mode(self, emp_no: str) -> dict | None:
        user = self._fetch_user(emp_no)
        if user is None:
            return None
        return self._fetch_one(
            "SELECT * FROM jhemr.users_control_mode WHERE user_id = %s AND hospital_no = %s",
            (user["user_id"], self.hospital_no),
        )

    def snapshot_sublogin(self, emp_no: str) -> list[dict]:
        user = self._fetch_user(emp_no)
        if user is None:
            return []
        return self._fetch_all(
            "SELECT * FROM jhemr.users_sublogin WHERE user_id = %s AND hospital_no = %s",
            (user["user_id"], self.hospital_no),
        )

    def snapshot_subsign(self, emp_no: str) -> list[dict]:
        user = self._fetch_user(emp_no)
        if user is None:
            return []
        return self._fetch_all(
            "SELECT * FROM jhemr.users_subsign WHERE user_id = %s AND hospital_no = %s",
            (user["user_id"], self.hospital_no),
        )

    def get_baseline_accounts(self, classification: str, limit: int = 3) -> list[dict]:
        role_group = ROLE_GROUP_MAP.get(classification, "001")
        rows = self._fetch_all(
            "SELECT u.db_user, u.account_status, u.user_type, u.is_sm "
            "FROM jhemr.users u "
            "JOIN jhemr.jhauth_user_vs_role_group rg "
            "ON u.user_id = rg.user_id AND u.hospital_no = rg.hospital_no "
            "WHERE rg.role_group_id = %s AND u.hospital_no = %s "
            "AND u.account_status = '0' ORDER BY u.db_user LIMIT %s",
            (role_group, self.hospital_no, limit),
        )
        return [self._mask_user_row(r) for r in rows]


    # -- full user creation (plan 107 section 6) ----------------------------

    def create_user_full(
        self,
        emp_no: str,
        display_name: str,
        classification: str,
        primary_dept: str,
        additional_depts: list[str],
        date_str: str | None = None,
        job_title: str | None = None,
    ) -> dict:
        """Create a complete JHEMR user in ONE transaction across 6 tables.

        Tables: users, user_dept, jhauth_user_vs_role_group,
                users_control_mode, users_sublogin, users_subsign.
        Plus password initialization (user_pwd_sm via SM4).

        Any failure rolls back the ENTIRE transaction. No half-accounts.
        Pre-commit read-back verifies all inserts before COMMIT.

        Fail-closed: account creation REQUIRES password initialization to be
        enabled and a resolvable password secret (plan 107 §5.1/§5.2 — an
        account without a valid password is a half-account). Column names and
        nullability verified against the live schema on 2026-08-03:
        users.user_dept exists; users_sublogin/users_subsign only have
        last_modify_time (no last_modify_date / last_modify_user_id);
        users_control_mode has both. LAST_MODIFY_* uses the target DB server
        time (CURRENT_TIMESTAMP) per plan 107 §2.1.
        """
        from .identity_password import compute_password_fields, get_shanghai_date_str

        classification_key = (classification or "").strip().lower()
        if classification_key not in ROLE_GROUP_MAP:
            raise JhemrIdentityError(f"unsupported classification '{classification}'")

        role_group_code = ROLE_GROUP_MAP[classification_key]
        emp_no = str(emp_no).strip()
        if not emp_no:
            raise JhemrIdentityError("emp_no must not be empty")
        if not primary_dept or not str(primary_dept).strip():
            raise JhemrIdentityError("primary_dept must not be empty")
        primary_dept = str(primary_dept).strip()

        if not self.password_write_enabled:
            raise JhemrIdentityError(
                "password write is disabled (APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED=false); "
                "account creation requires password initialization in the same transaction"
            )
        if not self.password_secret_ref:
            raise JhemrIdentityError("password_secret_ref is required for account creation")

        if self.user_exists(emp_no):
            return {"status": "already_exists", "actions": [], "note": "User already exists"}

        if date_str is None:
            date_str = get_shanghai_date_str()

        all_depts = [primary_dept] + [d for d in additional_depts if d != primary_dept]
        password_fields = compute_password_fields(emp_no, self.password_secret_ref, date_str)

        conn = self._ensure_conn()
        actions: list[dict] = []
        try:
            # 1. INSERT users（显式列白名单；user_dept=HIS 主科室，107 §5.4）
            self._execute_write(
                "INSERT INTO jhemr.users "
                "(db_user, user_id, user_login_name, user_name, user_dept, account_status, "
                "user_type, hospital_no, is_sm, user_pwd_sm, education_title, pwd_modify_time, create_date, start_date) "
                "VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (emp_no, emp_no, emp_no, display_name, primary_dept, self.hospital_no,
                 int(password_fields.get("is_sm", "2")),
                 password_fields.get("user_pwd_sm", ""), job_title or None),
            )
            actions.append({"action": "insert", "table": "users", "target_key": emp_no})

            user_id = emp_no

            # 2. INSERT user_dept (primary=default, others not)
            for idx, dept_code in enumerate(all_depts):
                default_flag = 1 if idx == 0 else 0
                self._execute_write(
                    "INSERT INTO jhemr.user_dept "
                    "(user_id, user_dept, hospital_no, default_dept_flag, state, synchro_flag, start_date) "
                    "VALUES (%s, %s, %s, %s, 0, 1, CURRENT_TIMESTAMP)",
                    (user_id, dept_code, self.hospital_no, default_flag),
                )
                actions.append({"action": "insert", "table": "user_dept", "target_key": f"{user_id}:{dept_code}"})

            # 3. INSERT jhauth_user_vs_role_group
            self._execute_write(
                "INSERT INTO jhemr.jhauth_user_vs_role_group "
                "(user_id, role_group_id, hospital_no) VALUES (%s, %s, %s)",
                (user_id, role_group_code, self.hospital_no),
            )
            actions.append({"action": "insert", "table": "jhauth_user_vs_role_group", "target_key": f"{user_id}:{role_group_code}"})

            # 4. INSERT users_control_mode
            self._execute_write(
                "INSERT INTO jhemr.users_control_mode "
                "(user_id, hospital_no, in_sign_way, login_way, in_pic_mode, "
                "sign_box, default_loginway, double_login, "
                "last_modify_date, last_modify_user_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)",
                (user_id, self.hospital_no,
                 CONTROL_MODE_DEFAULTS["in_sign_way"],
                 CONTROL_MODE_DEFAULTS["login_way"],
                 CONTROL_MODE_DEFAULTS["in_pic_mode"],
                 CONTROL_MODE_DEFAULTS["sign_box"],
                 CONTROL_MODE_DEFAULTS["default_loginway"],
                 CONTROL_MODE_DEFAULTS["double_login"],
                 self.sync_operator_id),
            )
            actions.append({"action": "insert", "table": "users_control_mode", "target_key": user_id})

            # 5. INSERT users_sublogin (3 rows; live schema: only last_modify_time)
            for sub in SUBLOGIN_DEFAULTS:
                self._execute_write(
                    "INSERT INTO jhemr.users_sublogin "
                    "(user_id, hospital_no, file_visit_type, login_way, last_modify_time) "
                    "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (user_id, self.hospital_no, sub["file_visit_type"], sub["login_way"]),
                )
            actions.append({"action": "insert", "table": "users_sublogin", "target_key": user_id, "rows": len(SUBLOGIN_DEFAULTS)})

            # 6. INSERT users_subsign (3 rows, exactly one default_flag=1)
            for sub in SUBSIGN_DEFAULTS:
                self._execute_write(
                    "INSERT INTO jhemr.users_subsign "
                    "(user_id, hospital_no, file_visit_type, sign_way, picmode, "
                    "default_flag, last_modify_time) "
                    "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (user_id, self.hospital_no, sub["file_visit_type"], sub["sign_way"],
                     sub["picmode"], sub["default_flag"]),
                )
            actions.append({"action": "insert", "table": "users_subsign", "target_key": user_id, "rows": len(SUBSIGN_DEFAULTS)})

            # Pre-commit read-back verification
            self._verify_creation(user_id, role_group_code, all_depts)

            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return {
                "status": "failed",
                "actions": actions,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                "rolled_back": True,
            }

        return {
            "status": "success",
            "actions": actions,
            "user_id": emp_no,
            "role_group": role_group_code,
            "dept_count": len(all_depts),
            "template_version": TEMPLATE_VERSION,
            "password_initialized": bool(password_fields),
            "pwd_set_date": date_str,
        }

    def _execute_write(self, sql: str, params: tuple) -> int:
        conn = self._ensure_conn()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            return int(cur.rowcount or 0)
        finally:
            cur.close()

    def _verify_creation(self, user_id: str, role_group_code: str, expected_depts: list[str]) -> None:
        """Pre-commit read-back: verify all 6 tables have correct data."""
        user = self._fetch_one(
            "SELECT db_user, account_status FROM jhemr.users WHERE user_id = %s AND hospital_no = %s",
            (user_id, self.hospital_no),
        )
        if user is None:
            raise JhemrIdentityError("read-back failed: users row not found after insert")
        if user["account_status"] not in ("0", 0):
            raise JhemrIdentityError(f"read-back failed: account_status={user['account_status']}")

        rg = self._fetch_one(
            "SELECT role_group_id FROM jhemr.jhauth_user_vs_role_group "
            "WHERE user_id = %s AND role_group_id = %s AND hospital_no = %s",
            (user_id, role_group_code, self.hospital_no),
        )
        if rg is None:
            raise JhemrIdentityError(f"read-back failed: role group {role_group_code} not found")

        depts = self._fetch_all(
            "SELECT user_dept, default_dept_flag FROM jhemr.user_dept WHERE user_id = %s AND hospital_no = %s",
            (user_id, self.hospital_no),
        )
        dept_set = {str(d["user_dept"]) for d in depts}
        missing = [d for d in expected_depts if d not in dept_set]
        if missing:
            raise JhemrIdentityError(f"read-back failed: missing depts {missing}")
        default_count = sum(1 for d in depts if str(d.get("default_dept_flag")) == "1")
        if default_count != 1:
            raise JhemrIdentityError(f"read-back failed: default_dept_flag count={default_count}")

        cm = self._fetch_one(
            "SELECT user_id FROM jhemr.users_control_mode WHERE user_id = %s AND hospital_no = %s",
            (user_id, self.hospital_no),
        )
        if cm is None:
            raise JhemrIdentityError("read-back failed: users_control_mode not found")

        sl = self._fetch_all(
            "SELECT login_way FROM jhemr.users_sublogin WHERE user_id = %s AND hospital_no = %s",
            (user_id, self.hospital_no),
        )
        if len(sl) < len(SUBLOGIN_DEFAULTS):
            raise JhemrIdentityError(f"read-back failed: sublogin count={len(sl)}")

        ss = self._fetch_all(
            "SELECT sign_way, default_flag FROM jhemr.users_subsign WHERE user_id = %s AND hospital_no = %s",
            (user_id, self.hospital_no),
        )
        if len(ss) < len(SUBSIGN_DEFAULTS):
            raise JhemrIdentityError(f"read-back failed: subsign count={len(ss)}")
        default_signs = sum(1 for s in ss if str(s.get("default_flag")) == "1")
        if default_signs != 1:
            raise JhemrIdentityError(f"read-back failed: subsign default count={default_signs}")


    # -- idempotent alignment for existing accounts -------------------------

    def align_existing_user(
        self,
        emp_no: str,
        classification: str,
        dept_codes: list[str],
        role_group_code: str,
        job_title: str | None = None,
    ) -> dict:
        """Idempotently align an existing user and overwrite a changed HIS title."""
        classification_key, role_group_code, dept_codes = self._normalize_inputs(
            classification, dept_codes, role_group_code
        )
        user = self._fetch_user(emp_no)
        if user is None:
            raise JhemrIdentityError(f"user {emp_no} not found; creation required separately")
        user_id = user["user_id"]

        conn = self._ensure_conn()
        actions: list[dict] = []
        try:
            normalized_title = str(job_title or "").strip()
            current_title = str(user.get("education_title") or "").strip()
            if normalized_title and normalized_title != current_title:
                affected = self._execute_write(
                    "UPDATE jhemr.users SET education_title = %s "
                    "WHERE user_id = %s AND hospital_no = %s",
                    (normalized_title, user_id, self.hospital_no),
                )
                if affected != 1:
                    raise JhemrIdentityError(
                        f"education_title update affected {affected} rows; expected 1"
                    )
                verified_title = self._fetch_one(
                    "SELECT education_title FROM jhemr.users "
                    "WHERE user_id = %s AND hospital_no = %s",
                    (user_id, self.hospital_no),
                )
                if not verified_title or str(verified_title.get("education_title") or "").strip() != normalized_title:
                    raise JhemrIdentityError("education_title read-back mismatch")
                actions.append({"action": "overwrite_education_title", "table": "users"})
            existing_rg = self._fetch_one(
                "SELECT role_group_id FROM jhemr.jhauth_user_vs_role_group "
                "WHERE user_id = %s AND role_group_id = %s AND hospital_no = %s",
                (user_id, role_group_code, self.hospital_no),
            )
            if existing_rg is None:
                self._execute_write(
                    "INSERT INTO jhemr.jhauth_user_vs_role_group "
                    "(user_id, role_group_id, hospital_no) VALUES (%s, %s, %s)",
                    (user_id, role_group_code, self.hospital_no),
                )
                actions.append({"action": "insert", "table": "jhauth_user_vs_role_group", "role_group_code": role_group_code})
            else:
                actions.append({"action": "skip_exists", "table": "jhauth_user_vs_role_group"})

            existing_depts = self._existing_dept_codes(user_id)
            for dept_code in dept_codes:
                if dept_code in existing_depts:
                    actions.append({"action": "skip_exists", "table": "user_dept", "dept_code": dept_code})
                    continue
                self._execute_write(
                    "INSERT INTO jhemr.user_dept (user_id, user_dept, hospital_no, default_dept_flag, state, synchro_flag) "
                    "VALUES (%s, %s, %s, 0, 0, 1)",
                    (user_id, dept_code, self.hospital_no),
                )
                actions.append({"action": "insert", "table": "user_dept", "dept_code": dept_code})

            existing_cm = self._fetch_one(
                "SELECT user_id FROM jhemr.users_control_mode WHERE user_id = %s AND hospital_no = %s",
                (user_id, self.hospital_no),
            )
            if existing_cm is None:
                self._execute_write(
                    "INSERT INTO jhemr.users_control_mode "
                    "(user_id, hospital_no, in_sign_way, login_way, in_pic_mode, "
                    "sign_box, default_loginway, double_login, "
                    "last_modify_date, last_modify_user_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)",
                    (user_id, self.hospital_no,
                     CONTROL_MODE_DEFAULTS["in_sign_way"],
                     CONTROL_MODE_DEFAULTS["login_way"],
                     CONTROL_MODE_DEFAULTS["in_pic_mode"],
                     CONTROL_MODE_DEFAULTS["sign_box"],
                     CONTROL_MODE_DEFAULTS["default_loginway"],
                     CONTROL_MODE_DEFAULTS["double_login"],
                     self.sync_operator_id),
                )
                actions.append({"action": "insert", "table": "users_control_mode"})
            else:
                actions.append({"action": "skip_exists", "table": "users_control_mode"})

            existing_sl = self._fetch_all(
                "SELECT login_way FROM jhemr.users_sublogin WHERE user_id = %s AND hospital_no = %s AND file_visit_type = '2'",
                (user_id, self.hospital_no),
            )
            existing_ways = {str(r.get("login_way")) for r in existing_sl}
            for sub in SUBLOGIN_DEFAULTS:
                if sub["login_way"] not in existing_ways:
                    self._execute_write(
                        "INSERT INTO jhemr.users_sublogin "
                        "(user_id, hospital_no, file_visit_type, login_way, last_modify_time) "
                        "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                        (user_id, self.hospital_no, sub["file_visit_type"], sub["login_way"]),
                    )
                    actions.append({"action": "insert", "table": "users_sublogin", "login_way": sub["login_way"]})

            existing_ss = self._fetch_all(
                "SELECT sign_way FROM jhemr.users_subsign WHERE user_id = %s AND hospital_no = %s AND file_visit_type = '2'",
                (user_id, self.hospital_no),
            )
            existing_sign_ways = {str(r.get("sign_way")) for r in existing_ss}
            for sub in SUBSIGN_DEFAULTS:
                if sub["sign_way"] not in existing_sign_ways:
                    self._execute_write(
                        "INSERT INTO jhemr.users_subsign "
                        "(user_id, hospital_no, file_visit_type, sign_way, picmode, "
                        "default_flag, last_modify_time) "
                        "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
                        (user_id, self.hospital_no, sub["file_visit_type"], sub["sign_way"],
                         sub["picmode"], sub["default_flag"]),
                    )
                    actions.append({"action": "insert", "table": "users_subsign", "sign_way": sub["sign_way"]})

            verify_rg = self._fetch_one(
                "SELECT role_group_id FROM jhemr.jhauth_user_vs_role_group "
                "WHERE user_id = %s AND role_group_id = %s AND hospital_no = %s",
                (user_id, role_group_code, self.hospital_no),
            )
            if verify_rg is None:
                raise JhemrIdentityError("read-back failed: role group not present after align")

            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return {"status": "failed", "actions": actions, "error": f"{type(exc).__name__}: {str(exc)[:300]}", "rolled_back": True}

        return {"status": "success", "actions": actions}

    def update_education_title_only(
        self,
        user_id: str,
        education_title: str,
        *,
        expected_current: str | None = None,
    ) -> dict[str, Any]:
        """Update only ``users.education_title`` and verify it before commit.

        This deliberately does not call :meth:`align_existing_user`, whose
        normal identity reconciliation also touches role and department
        tables.  The daily title subtask has a narrower write contract.
        """
        normalized = str(education_title or "").strip()
        if not normalized:
            raise JhemrIdentityError("education_title must not be empty")
        current_row = self._fetch_one(
            "SELECT user_id, education_title FROM jhemr.users "
            "WHERE user_id = %s AND hospital_no = %s FOR UPDATE",
            (str(user_id).strip(), self.hospital_no),
        )
        if current_row is None:
            return {"status": "missing_target"}
        current = str(current_row.get("education_title") or "").strip() or None
        if current != expected_current:
            raise JhemrIdentityError("target_changed_after_plan")
        if current == normalized:
            return {"status": "skipped", "reason": "already_equal"}
        conn = self._ensure_conn()
        try:
            affected = self._execute_write(
                "UPDATE jhemr.users SET education_title = %s "
                "WHERE user_id = %s AND hospital_no = %s",
                (normalized, str(user_id).strip(), self.hospital_no),
            )
            if affected != 1:
                raise JhemrIdentityError(
                    f"education_title update affected {affected} rows; expected 1"
                )
            verified = self._fetch_one(
                "SELECT education_title FROM jhemr.users "
                "WHERE user_id = %s AND hospital_no = %s",
                (str(user_id).strip(), self.hospital_no),
            )
            if not verified or str(verified.get("education_title") or "").strip() != normalized:
                raise JhemrIdentityError("education_title read-back mismatch")
            conn.commit()
            return {"status": "success", "rows_affected": 1}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def update_education_titles_only(
        self,
        changes: list[tuple[str, str | None, str]],
    ) -> dict[str, Any]:
        """Apply the daily title plan in one JHEMR transaction.

        Every row is locked and compared with the snapshot value. Any
        missing/concurrently changed row, row-count mismatch or read-back
        mismatch rolls back the whole batch.
        """
        conn = self._ensure_conn()
        updated = 0
        skipped = 0
        try:
            for user_id, expected_current, education_title in changes:
                normalized = str(education_title or "").strip()
                if not normalized:
                    raise JhemrIdentityError("education_title must not be empty")
                current_row = self._fetch_one(
                    "SELECT user_id, education_title FROM jhemr.users "
                    "WHERE user_id = %s AND hospital_no = %s FOR UPDATE",
                    (str(user_id).strip(), self.hospital_no),
                )
                if current_row is None:
                    raise JhemrIdentityError("target_user_missing_during_update")
                current = str(current_row.get("education_title") or "").strip() or None
                if current != expected_current:
                    raise JhemrIdentityError("target_changed_after_plan")
                if current == normalized:
                    skipped += 1
                    continue
                affected = self._execute_write(
                    "UPDATE jhemr.users SET education_title = %s "
                    "WHERE user_id = %s AND hospital_no = %s",
                    (normalized, str(user_id).strip(), self.hospital_no),
                )
                if affected != 1:
                    raise JhemrIdentityError(
                        f"education_title update affected {affected} rows; expected 1"
                    )
                verified = self._fetch_one(
                    "SELECT education_title FROM jhemr.users "
                    "WHERE user_id = %s AND hospital_no = %s",
                    (str(user_id).strip(), self.hospital_no),
                )
                if not verified or str(verified.get("education_title") or "").strip() != normalized:
                    raise JhemrIdentityError("education_title read-back mismatch")
                updated += 1
            conn.commit()
            return {"status": "success", "updated": updated, "skipped": skipped}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def reset_existing_password(self, emp_no: str, date_str: str | None = None) -> dict:
        """Initialize an existing account password through the controlled SM4 path."""
        emp_no = str(emp_no or "").strip()
        if not emp_no:
            raise JhemrIdentityError("emp_no must not be empty")
        if not self.password_write_enabled:
            raise JhemrIdentityError(
                "password write is disabled (APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED=false)"
            )
        if not self.password_secret_ref:
            raise JhemrIdentityError("password_secret_ref is required for password reset")

        user = self._fetch_user(emp_no)
        if user is None:
            raise JhemrIdentityError("existing user not found; password reset refused")
        user_id = str(user["user_id"])
        if date_str is None:
            date_str = get_shanghai_date_str()
        password_fields = compute_password_fields(user_id, self.password_secret_ref, date_str)

        conn = self._ensure_conn()
        try:
            affected = self._execute_write(
                "UPDATE jhemr.users SET user_pwd_sm = %s, is_sm = %s, "
                "pwd_modify_time = CURRENT_TIMESTAMP "
                "WHERE user_id = %s AND db_user = %s AND hospital_no = %s",
                (
                    password_fields["user_pwd_sm"],
                    int(password_fields["is_sm"]),
                    user_id,
                    emp_no,
                    self.hospital_no,
                ),
            )
            if affected != 1:
                raise JhemrIdentityError(f"password reset affected {affected} rows; expected 1")
            verified = self._fetch_one(
                "SELECT user_pwd_sm, is_sm FROM jhemr.users "
                "WHERE user_id = %s AND db_user = %s AND hospital_no = %s",
                (user_id, emp_no, self.hospital_no),
            )
            if not verified or verified.get("user_pwd_sm") != password_fields["user_pwd_sm"]:
                raise JhemrIdentityError("password reset read-back mismatch")
            if str(verified.get("is_sm")) != str(password_fields["is_sm"]):
                raise JhemrIdentityError("password algorithm read-back mismatch")
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return {
                "status": "failed",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                "rolled_back": True,
            }
        return {"status": "success", "password_initialized": True, "pwd_set_date": date_str}

    # -- dry-run ------------------------------------------------------------

    def dry_run_single_user(self, emp_no: str, classification: str, dept_codes: list[str], role_group_code: str) -> list[dict]:
        classification_key, role_group_code, dept_codes = self._normalize_inputs(classification, dept_codes, role_group_code)
        actions: list[dict] = []
        user = self._fetch_user(emp_no)

        if user is None:
            actions.append({"action": "create_user", "table": "users", "fields": {"db_user": emp_no, "hospital_no": self.hospital_no}})
            actions.append({"action": "create_password", "table": "users", "fields": {"algorithm": "SM4/ECB/PKCS7", "encoding": "Base64"}})
            for idx, dept in enumerate(dept_codes):
                actions.append({"action": "insert", "table": "user_dept", "fields": {"user_dept": dept, "default_dept_flag": "1" if idx == 0 else "0"}})
            actions.append({"action": "insert", "table": "jhauth_user_vs_role_group", "fields": {"role_group_id": role_group_code}})
            actions.append({"action": "insert", "table": "users_control_mode", "fields": CONTROL_MODE_DEFAULTS})
            actions.append({"action": "insert", "table": "users_sublogin", "fields": {"count": len(SUBLOGIN_DEFAULTS)}})
            actions.append({"action": "insert", "table": "users_subsign", "fields": {"count": len(SUBSIGN_DEFAULTS)}})
            return actions

        user_id = user["user_id"]
        existing_rg = self._fetch_one(
            "SELECT role_group_id FROM jhemr.jhauth_user_vs_role_group "
            "WHERE user_id = %s AND role_group_id = %s AND hospital_no = %s",
            (user_id, role_group_code, self.hospital_no),
        )
        if existing_rg is None:
            actions.append({"action": "insert", "table": "jhauth_user_vs_role_group", "fields": {"role_group_id": role_group_code}})
        else:
            actions.append({"action": "skip_exists", "table": "jhauth_user_vs_role_group"})

        existing_depts = self._existing_dept_codes(user_id)
        for dept in dept_codes:
            if dept in existing_depts:
                actions.append({"action": "skip_exists", "table": "user_dept", "dept_code": dept})
            else:
                actions.append({"action": "insert", "table": "user_dept", "fields": {"user_dept": dept}})
        return actions

    # -- internal helpers ---------------------------------------------------

    def _normalize_inputs(self, classification: str, dept_codes: list[str], role_group_code: str) -> tuple[str, str, list[str]]:
        classification_key = (classification or "").strip().lower()
        if classification_key not in ROLE_GROUP_MAP:
            raise JhemrIdentityError(f"unsupported classification '{classification}'")
        expected_group = ROLE_GROUP_MAP[classification_key]
        role_group_code = (role_group_code or "").strip()
        if not role_group_code:
            role_group_code = expected_group
        if role_group_code != expected_group:
            raise JhemrIdentityError(f"role_group_code '{role_group_code}' != expected '{expected_group}'")
        cleaned: list[str] = []
        seen: set[str] = set()
        for dept_code in dept_codes or []:
            text = str(dept_code or "").strip()
            if text and text not in seen:
                seen.add(text)
                cleaned.append(text)
        return classification_key, role_group_code, cleaned

    def _fetch_user(self, emp_no: str) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM jhemr.users WHERE db_user = %s AND hospital_no = %s",
            (str(emp_no or "").strip(), self.hospital_no),
        )

    def _existing_dept_codes(self, user_id) -> set[str]:
        rows = self._fetch_all(
            "SELECT user_dept FROM jhemr.user_dept WHERE user_id = %s AND hospital_no = %s",
            (user_id, self.hospital_no),
        )
        return {str(row["user_dept"]) for row in rows if row.get("user_dept") is not None}

    def _mask_user_row(self, row: dict) -> dict:
        safe: dict = {}
        for key, value in row.items():
            if str(key).lower() in SENSITIVE_USER_FIELDS:
                safe[key] = _mask(value)
            else:
                safe[key] = self._jsonable_value(value)
        return safe

    def _jsonable(self, row: dict) -> dict:
        return {key: self._jsonable_value(value) for key, value in row.items()}

    @staticmethod
    def _jsonable_value(value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
