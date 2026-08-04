"""CDMS identity adapter for writing to the CDMS Oracle 11g database.

Target system: CDMS (Oracle 11.2.0.1.0, thick mode required).
Connection path: local -> SSH jump host (10.10.8.83) -> CDMS Oracle.
Target tables: T_MSS_EMP_DICT (PK=FLOGINNAME), T_MSS_AUTHMAPPING
(PK=FAUTHMAPPINGID; subject column FID, authority value column FAUTHORITYID).
Write policy: identity_account_sync.

Live-schema verification 2026-08-03 (read-only):
- T_MSS_EMP_DICT columns include FLOGINNAME(PK), FUSERNAME, FPWD, FDEPT,
  FSYSID, FUSERTYPE(NUMBER), FUSERSTATE, HOSPITALAREACODE.
  There is NO FDEPTID column.
- T_MSS_AUTHMAPPING columns: FAUTHMAPPINGID(PK, 32-char hex), FID(=login),
  FAUTHORITYID(=value), FTYPE, FDATE, FUSER(=operator), FST,
  FUPDATEUSER(=update operator), FPRIVIEGETYPE(=FTYPE).
  There are NO FLOGINNAME/FVALUE columns.
- Template modes for accounts holding the 医疗质控/护理质控 roles (904/1036):
  FSYSID='2', FUSERTYPE=0, FUSERSTATE='0'; FTYPE=3 mode '100005',
  FTYPE=5 mode 'A00001'; FTYPE=10 value '1' grants discharged-patient access.

This adapter supports creating CDMS accounts, locking accounts, and
read-only snapshots. All SQL uses bind variables. No DELETE operations.
Passwords are never logged or returned in API responses.
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

import oracledb

from .credential_store import credential_path

logger = logging.getLogger(__name__)

CDMS_BASE_TEMPLATE: dict[str, str] = {
    "FSYSID": "2",
    "FUSERTYPE": "0",
    "FUSERSTATE": "0",
    "HOSPITALAREACODE": "A00001",
}

CDMS_BASE_AUTH: list[dict[str, str]] = [
    {"ftype": "3", "fvalue": "100005"},
    {"ftype": "5", "fvalue": "A00001"},
    {"ftype": "10", "fvalue": "1"},
]

CDMS_OPERATOR = "admin"

SENSITIVE_FIELDS: set[str] = {"FPWD", "FPWD_SM", "PASSWORD"}

_FORBIDDEN_FTYPES: set[str] = {"8", "32"}

_SQL_SELECT_EMP = (
    "SELECT FLOGINNAME, FUSERNAME, FDEPT, FSYSID, FUSERTYPE, "
    "FUSERSTATE, HOSPITALAREACODE FROM CDMS.T_MSS_EMP_DICT "
    "WHERE FLOGINNAME = :emp_no AND ROWNUM <= 1"
)

_SQL_SELECT_AUTH = (
    "SELECT FAUTHMAPPINGID, FID, FUSER, FUPDATEUSER, FTYPE, FAUTHORITYID, "
    "FPRIVIEGETYPE FROM CDMS.T_MSS_AUTHMAPPING WHERE FID = :emp_no"
)

_SQL_PWD_STATS = (
    "SELECT FPWD, COUNT(*) AS CNT FROM CDMS.T_MSS_EMP_DICT "
    "WHERE FPWD IS NOT NULL GROUP BY FPWD ORDER BY CNT DESC"
)

_SQL_PWD_TOTAL = "SELECT COUNT(*) AS TOTAL FROM CDMS.T_MSS_EMP_DICT"

_SQL_COUNT_EMP = (
    "SELECT COUNT(*) AS CNT FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME = :emp_no"
)

_SQL_INSERT_EMP = (
    "INSERT INTO CDMS.T_MSS_EMP_DICT "
    "(FLOGINNAME, FUSERNAME, FDEPT, FPWD, FSYSID, FUSERTYPE, FUSERSTATE, HOSPITALAREACODE) "
    "VALUES (:floginname, :fusername, :fdept, :fpwd, :fsysid, :fusertype, :fuserstate, :hospitalareacode)"
)

# FID carries the employee login; FUSER is the fixed operator admin;
# FUPDATEUSER remains NULL; FPRIVIEGETYPE mirrors FTYPE; FST='0' (valid).
_SQL_INSERT_AUTH = (
    "INSERT INTO CDMS.T_MSS_AUTHMAPPING "
    "(FAUTHMAPPINGID, FID, FAUTHORITYID, FTYPE, FDATE, FUSER, FST, "
    "FUPDATEUSER, FUPDATE, FPRIVIEGETYPE) VALUES "
    "(:fid_pk, :emp_no, :fvalue, :ftype, SYSDATE, :operator, '0', "
    "NULL, SYSDATE, :ftype2)"
)

_SQL_LOCK_USER = (
    "UPDATE CDMS.T_MSS_EMP_DICT SET FUSERSTATE = '1' WHERE FLOGINNAME = :emp_no"
)


def _strip_sensitive(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with sensitive fields removed."""
    return {k: v for k, v in data.items() if k.upper() not in SENSITIVE_FIELDS}


def _strip_sensitive_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_strip_sensitive(row) for row in rows]


def _read_credential(credential_ref: str) -> tuple[str, str]:
    """Read username:password from the server credential file.

    Accepts either a bare source code (resolved via credential_store) or a
    file:// URI pointing directly at the credential file.
    """
    if credential_ref.startswith("file://"):
        path = Path(credential_ref[7:])
    else:
        path = credential_path(credential_ref, writable=True)
    if not path.is_file():
        raise FileNotFoundError(f"credential file not found: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if ":" not in content:
        raise ValueError("credential file must contain username:password")
    username, password = content.split(":", 1)
    if not username.strip() or not password:
        raise ValueError("credential file has empty username or password")
    return username.strip(), password


class CdmsIdentityAdapter:
    """Write-capable adapter for CDMS identity account synchronization.

    Connection is established through an SSH tunnel to the jump host, then
    a local Oracle thick-mode connection to the CDMS database.
    """

    def __init__(
        self,
        credential_ref: str,
        jump_host: str,
        jump_port: int,
        jump_user: str,
        jump_key: str | None,
        oracle_client_lib: str,
        *,
        cdms_host: str = "127.0.0.1",
        cdms_port: int = 1521,
        cdms_service: str = "CDMS",
        local_bind_port: int = 11521,
        ssh_timeout: int = 30,
    ) -> None:
        self._credential_ref = credential_ref
        self._jump_host = jump_host
        self._jump_port = jump_port
        self._jump_user = jump_user
        self._jump_key = jump_key
        self._oracle_client_lib = oracle_client_lib
        self._cdms_host = cdms_host
        self._cdms_port = cdms_port
        self._cdms_service = cdms_service
        self._local_bind_port = local_bind_port
        self._ssh_timeout = ssh_timeout

        self._conn: oracledb.Connection | None = None
        self._tunnel_proc: subprocess.Popen | None = None
        self._oracle_client_initialized = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish Oracle thick-mode connection via SSH tunnel."""
        if self._conn is not None:
            return

        self._init_oracle_client()
        self._start_ssh_tunnel()

        username, password = _read_credential(self._credential_ref)
        # DSN must point at the LOCAL end of the SSH tunnel, never at the
        # remote host directly (the remote host is only reachable via jump).
        dsn = f"127.0.0.1:{self._local_bind_port}/{self._cdms_service}"
        logger.info(
            "connecting to CDMS via tunnel %s:%s -> %s",
            self._jump_host,
            self._jump_port,
            dsn,
        )
        try:
            self._conn = oracledb.connect(
                user=username,
                password=password,
                dsn=dsn,
            )
            self._conn.call_timeout = 60_000
            logger.info("CDMS connection established")
        except Exception:
            self._stop_ssh_tunnel()
            raise

    def close(self) -> None:
        """Close Oracle connection and SSH tunnel."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                logger.debug("error closing CDMS connection", exc_info=True)
            finally:
                self._conn = None
        self._stop_ssh_tunnel()
        logger.info("CDMS adapter closed")

    def __enter__(self) -> "CdmsIdentityAdapter":
        self.connect()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Read-only snapshots
    # ------------------------------------------------------------------

    def snapshot_user(self, emp_no: str) -> dict[str, Any] | None:
        """Read-only: fetch one row from T_MSS_EMP_DICT by FLOGINNAME."""
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(_SQL_SELECT_EMP, {"emp_no": emp_no})
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cursor.description]
            return _strip_sensitive(dict(zip(columns, row)))
        finally:
            cursor.close()

    def snapshot_auth(self, emp_no: str) -> list[dict[str, Any]]:
        """Read-only: fetch all T_MSS_AUTHMAPPING rows for a user."""
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(_SQL_SELECT_AUTH, {"emp_no": emp_no})
            columns = [desc[0] for desc in cursor.description]
            return [_strip_sensitive(dict(zip(columns, r))) for r in cursor.fetchall()]
        finally:
            cursor.close()

    def check_password_template(self) -> dict[str, Any]:
        """Read-only stats on FPWD: mode value, length, coverage rate.

        Returns aggregate statistics only. The actual password ciphertext is
        never included in the return value or logs.
        """
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(_SQL_PWD_TOTAL)
            total_row = cursor.fetchone()
            total = int(total_row[0]) if total_row else 0

            cursor.execute(_SQL_PWD_STATS)
            rows = cursor.fetchall()

            if not rows or total == 0:
                return {
                    "mode_value": None,
                    "mode_length": 0,
                    "coverage": 0.0,
                    "total": total,
                    "mode_count": 0,
                }

            mode_pwd, mode_count = rows[0][0], int(rows[0][1])
            non_null_count = sum(int(r[1]) for r in rows)
            coverage = round(non_null_count / total, 4) if total > 0 else 0.0

            return {
                "mode_value": f"[{len(str(mode_pwd))} chars]",
                "mode_length": len(str(mode_pwd)),
                "coverage": coverage,
                "total": total,
                "mode_count": mode_count,
            }
        finally:
            cursor.close()

    def fetch_mode_fpwd_ciphertext(self) -> str | None:
        """Return the mode FPWD ciphertext for initial-password reuse.

        The CDMS password algorithm is unknown (104 报告 E8)，新账号初始密码
        采用“复用全院默认密文”策略：直接读取占比最高的 FPWD 密文并仅保存在
        内存中用于同事务 INSERT。该值绝不进入日志、审计、API 或返回值以外的
        任何持久化通道。
        """
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(_SQL_PWD_STATS)
            row = cursor.fetchone()
            if row is None or row[0] is None:
                return None
            return str(row[0])
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def dry_run_single_user(
        self,
        emp_no: str,
        classification: str,
        dept_codes: list[str],
        role_mapping: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate planned actions for a single user without executing."""
        actions: list[dict[str, Any]] = []
        existing = self.snapshot_user(emp_no)
        if existing is not None:
            actions.append({
                "action": "skip",
                "reason": "FLOGINNAME already exists",
                "table": "T_MSS_EMP_DICT",
                "emp_no": emp_no,
            })
            return actions

        actions.append({
            "action": "insert",
            "table": "T_MSS_EMP_DICT",
            "emp_no": emp_no,
            "classification": classification,
            "fields": {
                "FLOGINNAME": emp_no,
                "FSYSID": CDMS_BASE_TEMPLATE["FSYSID"],
                "FUSERTYPE": CDMS_BASE_TEMPLATE["FUSERTYPE"],
                "FUSERSTATE": CDMS_BASE_TEMPLATE["FUSERSTATE"],
                "HOSPITALAREACODE": CDMS_BASE_TEMPLATE["HOSPITALAREACODE"],
            },
        })

        role_code = role_mapping.get("role_code", "")
        if role_code:
            actions.append({
                "action": "insert",
                "table": "T_MSS_AUTHMAPPING",
                "emp_no": emp_no,
                "ftype": "0",
                "fvalue": role_code,
                "description": "role mapping",
            })

        for dept_code in dept_codes:
            actions.append({
                "action": "insert",
                "table": "T_MSS_AUTHMAPPING",
                "emp_no": emp_no,
                "ftype": "2",
                "fvalue": dept_code,
                "description": "department mapping",
            })

        for base_auth in CDMS_BASE_AUTH:
            actions.append({
                "action": "insert",
                "table": "T_MSS_AUTHMAPPING",
                "emp_no": emp_no,
                "ftype": base_auth["ftype"],
                "fvalue": base_auth["fvalue"],
                "description": "base auth",
            })

        actions.append({
            "action": "verify",
            "description": "read-back verification before commit",
        })
        return actions

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def apply_single_user(
        self,
        emp_no: str,
        person_name: str,
        dept_code: str,
        classification: str,
        dept_codes: list[str],
        role_mapping: dict[str, Any],
        fpwd_template: str,
    ) -> dict[str, Any]:
        """Create a CDMS account in ONE transaction.

        Steps: re-check existence -> INSERT emp -> INSERT auth rows ->
        read-back verify -> COMMIT. On any failure the entire transaction
        is rolled back.
        """
        conn = self._require_conn()
        cursor = conn.cursor()
        actions_log: list[dict[str, Any]] = []
        rows_affected: dict[str, int] = {}
        try:
            # (a) Re-check FLOGINNAME does not exist
            cursor.execute(_SQL_COUNT_EMP, {"emp_no": emp_no})
            count_row = cursor.fetchone()
            if count_row and int(count_row[0]) > 0:
                return {
                    "status": "failed",
                    "reason": "FLOGINNAME already exists",
                    "rows_affected": {},
                    "actions": [{"action": "abort", "reason": "duplicate FLOGINNAME"}],
                }

            # (b) INSERT T_MSS_EMP_DICT
            cursor.execute(_SQL_INSERT_EMP, {
                "floginname": emp_no,
                "fusername": person_name,
                "fdept": dept_code,
                "fpwd": fpwd_template,
                "fsysid": CDMS_BASE_TEMPLATE["FSYSID"],
                "fusertype": CDMS_BASE_TEMPLATE["FUSERTYPE"],
                "fuserstate": CDMS_BASE_TEMPLATE["FUSERSTATE"],
                "hospitalareacode": CDMS_BASE_TEMPLATE["HOSPITALAREACODE"],
            })
            rows_affected["T_MSS_EMP_DICT"] = cursor.rowcount
            actions_log.append({"action": "insert", "table": "T_MSS_EMP_DICT", "emp_no": emp_no})

            # (c) INSERT T_MSS_AUTHMAPPING FTYPE=0 (role)
            role_code = role_mapping.get("role_code", "")
            if role_code:
                cursor.execute(_SQL_INSERT_AUTH, {
                    "fid_pk": uuid.uuid4().hex,
                    "emp_no": emp_no,
                    "fvalue": role_code,
                    "ftype": "0",
                    "operator": CDMS_OPERATOR,
                    "ftype2": "0",
                })
                rows_affected["AUTH_ROLE"] = cursor.rowcount
                actions_log.append({"action": "insert", "table": "T_MSS_AUTHMAPPING", "ftype": "0", "fvalue": role_code})

            # (d) INSERT T_MSS_AUTHMAPPING FTYPE=2 (departments)
            dept_insert_count = 0
            for single_dept in dept_codes:
                cursor.execute(_SQL_INSERT_AUTH, {
                    "fid_pk": uuid.uuid4().hex,
                    "emp_no": emp_no,
                    "fvalue": single_dept,
                    "ftype": "2",
                    "operator": CDMS_OPERATOR,
                    "ftype2": "2",
                })
                dept_insert_count += cursor.rowcount
                actions_log.append({"action": "insert", "table": "T_MSS_AUTHMAPPING", "ftype": "2", "fvalue": single_dept})
            rows_affected["AUTH_DEPT"] = dept_insert_count

            # (e) INSERT base auth rows (FTYPE=3/100005, 5/A00001, 10/0)
            base_insert_count = 0
            for base_auth in CDMS_BASE_AUTH:
                if base_auth["ftype"] in _FORBIDDEN_FTYPES:
                    continue
                cursor.execute(_SQL_INSERT_AUTH, {
                    "fid_pk": uuid.uuid4().hex,
                    "emp_no": emp_no,
                    "fvalue": base_auth["fvalue"],
                    "ftype": base_auth["ftype"],
                    "operator": CDMS_OPERATOR,
                    "ftype2": base_auth["ftype"],
                })
                base_insert_count += cursor.rowcount
                actions_log.append({
                    "action": "insert",
                    "table": "T_MSS_AUTHMAPPING",
                    "ftype": base_auth["ftype"],
                    "fvalue": base_auth["fvalue"],
                })
            rows_affected["AUTH_BASE"] = base_insert_count

            # (f) FTYPE=8 and FTYPE=32 are intentionally NOT written

            # (g) Read-back verify before commit
            cursor.execute(_SQL_SELECT_EMP, {"emp_no": emp_no})
            verify_emp = cursor.fetchone()
            if verify_emp is None:
                raise RuntimeError("read-back verification failed: emp row not found after insert")

            cursor.execute(_SQL_SELECT_AUTH, {"emp_no": emp_no})
            verify_auth = cursor.fetchall()
            expected_auth_count = (1 if role_code else 0) + len(dept_codes) + len(CDMS_BASE_AUTH)
            if len(verify_auth) < expected_auth_count:
                raise RuntimeError(
                    f"read-back verification failed: expected >= {expected_auth_count} "
                    f"auth rows, found {len(verify_auth)}"
                )

            conn.commit()
            actions_log.append({"action": "commit"})
            logger.info("CDMS account created: emp_no=%s, auth_rows=%d", emp_no, len(verify_auth))
            return {
                "status": "success",
                "rows_affected": rows_affected,
                "actions": actions_log,
            }

        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                logger.debug("rollback error", exc_info=True)
            actions_log.append({"action": "rollback", "error": str(exc)})
            logger.error("CDMS apply_single_user failed for emp_no=%s: %s", emp_no, exc)
            return {
                "status": "failed",
                "reason": str(exc),
                "rows_affected": rows_affected,
                "actions": actions_log,
            }
        finally:
            cursor.close()

    def lock_user(self, emp_no: str) -> dict[str, Any]:
        """Lock a CDMS account by setting FUSERSTATE=1 (lock, not delete)."""
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(_SQL_LOCK_USER, {"emp_no": emp_no})
            affected = cursor.rowcount
            conn.commit()
            logger.info("CDMS account locked: emp_no=%s, rows=%d", emp_no, affected)
            return {
                "status": "success" if affected > 0 else "not_found",
                "rows_affected": affected,
                "emp_no": emp_no,
            }
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                logger.debug("rollback error", exc_info=True)
            logger.error("CDMS lock_user failed for emp_no=%s: %s", emp_no, exc)
            return {"status": "failed", "reason": str(exc), "emp_no": emp_no}
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_conn(self) -> oracledb.Connection:
        if self._conn is None:
            raise RuntimeError("CDMS adapter is not connected; call connect() first")
        return self._conn

    def _init_oracle_client(self) -> None:
        if self._oracle_client_initialized:
            return
        try:
            oracledb.init_oracle_client(lib_dir=self._oracle_client_lib)
            self._oracle_client_initialized = True
            logger.info("Oracle thick client initialized: %s", self._oracle_client_lib)
        except Exception as exc:
            if "already initialized" in str(exc).lower():
                self._oracle_client_initialized = True
            else:
                raise

    def _start_ssh_tunnel(self) -> None:
        if self._tunnel_proc is not None:
            return
        cmd = [
            "ssh",
            "-fNL",
            f"{self._local_bind_port}:{self._cdms_host}:{self._cdms_port}",
            "-p", str(self._jump_port),
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ConnectTimeout=10",
        ]
        if self._jump_key:
            cmd.extend(["-i", self._jump_key])
        cmd.append(f"{self._jump_user}@{self._jump_host}")

        logger.info(
            "starting SSH tunnel: localhost:%s -> %s:%s via %s@%s:%s",
            self._local_bind_port,
            self._cdms_host,
            self._cdms_port,
            self._jump_user,
            self._jump_host,
            self._jump_port,
        )
        self._tunnel_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        # ssh -f forks to background; wait briefly for the parent to exit
        try:
            retcode = self._tunnel_proc.wait(timeout=self._ssh_timeout)
            if retcode != 0:
                stderr_output = ""
                if self._tunnel_proc.stderr:
                    stderr_output = self._tunnel_proc.stderr.read().decode("utf-8", errors="replace")[:500]
                self._tunnel_proc = None
                raise RuntimeError(f"SSH tunnel failed (exit {retcode}): {stderr_output}")
        except subprocess.TimeoutExpired:
            # -f should fork quickly; if it hangs, treat as failure
            self._tunnel_proc.kill()
            self._tunnel_proc = None
            raise RuntimeError("SSH tunnel start timed out")
        # After -f fork, the Popen pid is the parent that already exited;
        # the tunnel lives in the background. We keep proc=None to signal
        # that we cannot kill it via Popen (cleanup via pkill or port check).
        self._tunnel_proc = None
        logger.info("SSH tunnel established on local port %s", self._local_bind_port)

    def _stop_ssh_tunnel(self) -> None:
        """Best-effort cleanup of the background SSH tunnel."""
        # ssh -f detaches, so we kill by port pattern
        try:
            subprocess.run(
                [
                    "pkill", "-f",
                    f"ssh.*-L.*{self._local_bind_port}:{self._cdms_host}:{self._cdms_port}",
                ],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except Exception:
            logger.debug("SSH tunnel cleanup skipped", exc_info=True)
