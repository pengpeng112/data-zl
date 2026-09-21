"""CDMS identity adapter for writing to the CDMS Oracle 11g database.

Target system: CDMS (Oracle 11.2.0.1.0, thick mode required).
Connection path: local -> SSH jump host (10.10.8.83) -> CDMS Oracle.
Target tables: T_MSS_EMP_DICT (PK=FLOGINNAME), T_MSS_AUTHMAPPING
(PK=FAUTHMAPPINGID; subject column FID, authority value column FAUTHORITYID),
T_MSS_HOSPITALFOFFN (PK=FID; LOGINNAME+HOSPITALAREASCODE+FOFFIN is the
RoleManage/User page source for 所属科室/角色勾选).
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
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb

from .credential_store import credential_path

from .data_masking import sanitize_text

logger = logging.getLogger(__name__)

CDMS_BASE_TEMPLATE: dict[str, str] = {
    "FSYSID": "2",
    "FUSERTYPE": "0",
    "FUSERSTATE": "0",
    "HOSPITALAREACODE": "A00001",
    # 2026-09-02（172 §6）：全库 1735 个登录过账号 99.7% FFREE3='1'，而夜间同步
    # 建户后从未登录的 46 户全部 FFREE3=NULL（用户报障 004066，参照 004019）。
    # 建户必须带 FFREE3='1'，否则账号在无纸化系统不可用。
    "FFREE3": "1",
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
    "FPRIVIEGETYPE, FST FROM CDMS.T_MSS_AUTHMAPPING WHERE FID = :emp_no"
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
    "(FLOGINNAME, FUSERNAME, FDEPT, FPWD, FSYSID, FUSERTYPE, FUSERSTATE, HOSPITALAREACODE, FFREE3) "
    "VALUES (:floginname, :fusername, :fdept, :fpwd, :fsysid, :fusertype, :fuserstate, :hospitalareacode, :ffree3)"
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
    "UPDATE CDMS.T_MSS_EMP_DICT SET FUSERSTATE = '1', FCHANGEDATE = SYSDATE "
    "WHERE FLOGINNAME = :emp_no AND FUSERSTATE = '0'"
)

# 186 v1.10 §13.3/P0-17：受控恢复 '1'→'0' 的 CAS 变体。FCHANGEDATE 与
# 停用时记录的原始值一起作为 WHERE 条件（绑定 datetime），目标行在停用
# 之后被再次改动（哪怕同秒人工重锁后状态又回到 '1' 且时间变化）时
# rowcount=0 → attribution_target_changed，绝不无条件覆盖。
_SQL_UNLOCK_USER_CAS = (
    "UPDATE CDMS.T_MSS_EMP_DICT SET FUSERSTATE = '0', FCHANGEDATE = SYSDATE "
    "WHERE FLOGINNAME = :emp_no AND FUSERSTATE = '1' AND FCHANGEDATE = :expected_changed"
)

_SQL_COUNT_HOSPITALFOFFN = (
    "SELECT COUNT(*) AS CNT FROM CDMS.T_MSS_HOSPITALFOFFN "
    "WHERE LOGINNAME = :emp_no"
)

_SQL_INSERT_HOSPITALFOFFN = (
    "INSERT INTO CDMS.T_MSS_HOSPITALFOFFN "
    "(FID, LOGINNAME, HOSPITALAREASCODE, FOFFIN, ISDEFAULTFOFFIN, FREE1, FREE2, FREE3) "
    "VALUES (:fid, :emp_no, :hosp, :dept, 1, :free1, '1', '1')"
)

_SQL_TOFFIM_FTYPE = (
    "SELECT FTYPE FROM CDMS.TOFFIM WHERE FOFFN = :dept AND ROWNUM <= 1"
)


def _normalize_dept_type(raw: Any) -> str:
    """Map TOFFIM.FTYPE to RoleManage 所属科室类别: I/O/T/H."""
    value = str(raw or "").strip()
    if value in {"I", "O", "T", "H"}:
        return value
    return "T" if value else "I"


def _normalize_raw_time(value: Any) -> str | None:
    """186 v1.10 §13.3：目标侧时间原始值规范化（仅变更检测用）。

    datetime → isoformat() 字符串；str → strip()；None → None；其余类型 →
    str()。不做时区换算、不做容差——时间一致不是锁所有权证明，只是变更
    检测输入（所有权证据在编排/门禁层）。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip()
    return str(value)


# _fetch_user_state 的规范小写键（P0-16）：真实 oracledb cursor.description
# 的列名随 Oracle 端返回大写；读路径统一按大小写不敏感映射到这三个名字。
_USER_STATE_CANONICAL_KEYS = ("floginname", "fuserstate", "fchangedate")


def _ensure_hospitalfoffn(
    cursor: Any,
    *,
    emp_no: str,
    dept_code: str,
    hospital_area: str,
) -> dict[str, str]:
    """Idempotent insert of the RoleManage/User courtyard-dept row.

    XTWH may lack TOFFIM (ORA-00942); use SAVEPOINT so a missing dictionary
    does not poison the surrounding identity transaction.
    """
    dept = str(dept_code or "").strip()
    if not dept or dept == "0":
        return {"action": "skip", "reason": "no_dept"}
    cursor.execute(_SQL_COUNT_HOSPITALFOFFN, {"emp_no": emp_no})
    count_row = cursor.fetchone()
    if count_row and int(count_row[0]) > 0:
        return {"action": "skip", "reason": "exists"}

    free1 = "I"
    cursor.execute("SAVEPOINT sp_toffim_ftype")
    try:
        cursor.execute(_SQL_TOFFIM_FTYPE, {"dept": dept})
        type_row = cursor.fetchone()
        if type_row:
            free1 = _normalize_dept_type(type_row[0])
    except Exception:
        cursor.execute("ROLLBACK TO SAVEPOINT sp_toffim_ftype")

    hosp = str(hospital_area or CDMS_BASE_TEMPLATE["HOSPITALAREACODE"]).strip() or "A00001"
    cursor.execute("SAVEPOINT sp_hospitalfoffn")
    try:
        cursor.execute(
            _SQL_INSERT_HOSPITALFOFFN,
            {
                "fid": uuid.uuid4().hex.upper(),
                "emp_no": emp_no,
                "hosp": hosp,
                "dept": dept,
                "free1": free1,
            },
        )
        return {"action": "insert", "table": "T_MSS_HOSPITALFOFFN", "foffin": dept, "free1": free1}
    except Exception as exc:
        cursor.execute("ROLLBACK TO SAVEPOINT sp_hospitalfoffn")
        return {"action": "skip", "reason": sanitize_text(str(exc), limit=160)}


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
        direct = os.environ.get("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "").strip().lower() in {"1", "true", "yes"}
        if not direct:
            self._start_ssh_tunnel()

        username, password = _read_credential(self._credential_ref)
        # DSN must point at the LOCAL end of the SSH tunnel, never at the
        # remote host directly (the remote host is only reachable via jump).
        dsn_host = self._cdms_host if direct else "127.0.0.1"
        dsn_port = self._cdms_port if direct else self._local_bind_port
        dsn = f"{dsn_host}:{dsn_port}/{self._cdms_service}"
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
                "FFREE3": CDMS_BASE_TEMPLATE["FFREE3"],
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
                "ffree3": CDMS_BASE_TEMPLATE["FFREE3"],
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

            # (f2) RoleManage/User 读 T_MSS_HOSPITALFOFFN；缺行则角色/所属科室整段空白。
            hf = _ensure_hospitalfoffn(
                cursor,
                emp_no=emp_no,
                dept_code=dept_code,
                hospital_area=CDMS_BASE_TEMPLATE["HOSPITALAREACODE"],
            )
            actions_log.append(hf)
            if hf.get("action") == "insert":
                rows_affected["T_MSS_HOSPITALFOFFN"] = 1

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
            # QA ST-012：异常原文过 sanitize_text，防 ORA 错误内嵌 SQL/绑定值入库存档。
            actions_log.append({"action": "rollback", "error": sanitize_text(str(exc), limit=300)})
            logger.error("CDMS apply_single_user failed for emp_no=%s: %s", emp_no, sanitize_text(str(exc), limit=300))
            return {
                "status": "failed",
                "reason": sanitize_text(str(exc), limit=300),
                "rows_affected": rows_affected,
                "actions": actions_log,
            }
        finally:
            cursor.close()

    def align_existing_user(
        self,
        *,
        emp_no: str,
        dept_code: str,
        dept_codes: list[str],
        role_mapping: dict[str, Any],
    ) -> dict[str, Any]:
        """Add missing CDMS role/department/base permissions without deletion."""
        conn = self._require_conn()
        cursor = conn.cursor()
        actions: list[dict[str, Any]] = []
        try:
            cursor.execute(_SQL_COUNT_EMP, {"emp_no": emp_no})
            if int(cursor.fetchone()[0]) != 1:
                raise RuntimeError("existing CDMS account count is not one")
            cursor.execute(
                "UPDATE CDMS.T_MSS_EMP_DICT SET FDEPT = :dept "
                "WHERE FLOGINNAME = :emp_no AND NVL(FDEPT, ' ') <> :dept",
                {"dept": dept_code, "emp_no": emp_no},
            )
            if cursor.rowcount:
                actions.append({"action": "update_primary_dept"})

            # 172 §6：FFREE3 是无纸化账号可用开关（NULL → 无法登录使用）。
            # 旧模板建户漏写该列；align 时幂等补齐，避免存量户永久不可用。
            cursor.execute(
                "UPDATE CDMS.T_MSS_EMP_DICT SET FFREE3 = :ffree3 "
                "WHERE FLOGINNAME = :emp_no AND NVL(FFREE3, ' ') <> :ffree3",
                {"ffree3": CDMS_BASE_TEMPLATE["FFREE3"], "emp_no": emp_no},
            )
            if cursor.rowcount:
                actions.append({"action": "update_ffree3"})

            cursor.execute(_SQL_SELECT_AUTH, {"emp_no": emp_no})
            existing = {(str(r[4]), str(r[5])) for r in cursor.fetchall()}
            required = []
            role_code = str(role_mapping.get("role_code") or "").strip()
            if role_code:
                required.append(("0", role_code))
            required.extend(("2", str(code)) for code in dept_codes if code)
            required.extend((row["ftype"], row["fvalue"]) for row in CDMS_BASE_AUTH)
            for ftype, value in required:
                if (ftype, value) in existing:
                    continue
                cursor.execute(_SQL_INSERT_AUTH, {
                    "fid_pk": uuid.uuid4().hex,
                    "emp_no": emp_no,
                    "fvalue": value,
                    "ftype": ftype,
                    "operator": CDMS_OPERATOR,
                    "ftype2": ftype,
                })
                actions.append({"action": "insert_auth", "ftype": ftype})

            cursor.execute(_SQL_SELECT_AUTH, {"emp_no": emp_no})
            verified = {(str(r[4]), str(r[5])) for r in cursor.fetchall()}
            missing = [pair for pair in required if pair not in verified]
            if missing:
                raise RuntimeError("CDMS permission read-back mismatch")
            hf = _ensure_hospitalfoffn(
                cursor,
                emp_no=emp_no,
                dept_code=dept_code,
                hospital_area=CDMS_BASE_TEMPLATE["HOSPITALAREACODE"],
            )
            actions.append(hf)
            conn.commit()
            return {"status": "success", "actions": actions, "aligned": True}
        except Exception as exc:
            conn.rollback()
            return {"status": "failed", "reason": sanitize_text(f"{type(exc).__name__}: {str(exc)[:200]}", limit=250), "rolled_back": True}
        finally:
            cursor.close()

    def lock_user(self, emp_no: str) -> dict[str, Any]:
        """Lock a CDMS account: FUSERSTATE '0'→'1' (lock, never delete).

        186 v1.10 P0-16: the row is taken with SELECT ... FOR UPDATE and read
        through :meth:`_fetch_user_state` (canonical lower-case keys built
        case-insensitively from the real cursor description — the legacy
        lower()-then-uppercase-read path crashed on real cursors). Conditional
        update (expected old state '0'), 0-row classification, pre-commit
        read-back. FCHANGEDATE=SYSDATE is written and returned raw
        (``changed_at_raw``) as the precise change-detection evidence for
        the controlled unlock path; no tolerance is ever applied to it.
        """
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            current = self._fetch_user_state(cursor, emp_no, for_update=True)
            if current is None:
                return {"status": "missing_target", "emp_no": emp_no}
            if str(current.get("fuserstate")).strip() == "1":
                return {"status": "skipped", "reason": "already_locked", "emp_no": emp_no}
            cursor.execute(_SQL_LOCK_USER, {"emp_no": emp_no})
            affected = cursor.rowcount
            if affected != 1:
                raise RuntimeError(f"lock update affected {affected} rows; expected 1")
            verified = self._fetch_user_state(cursor, emp_no)
            if verified is None or str(verified.get("fuserstate")).strip() != "1":
                raise RuntimeError("lock read-back mismatch")
            conn.commit()
            logger.info("CDMS account locked: emp_no=%s, rows=%d", emp_no, affected)
            return {
                "status": "success",
                "rows_affected": affected,
                "emp_no": emp_no,
                # 兼容键保留；原始值见 changed_at_raw（精确比对用，无容差）。
                "changed_at": str(verified.get("fchangedate") or ""),
                "changed_at_raw": _normalize_raw_time(verified.get("fchangedate")),
            }
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                logger.debug("rollback error", exc_info=True)
            logger.error("CDMS lock_user failed for emp_no=%s: %s", emp_no, exc)
            return {"status": "failed", "reason": sanitize_text(str(exc), limit=300), "emp_no": emp_no}
        finally:
            cursor.close()

    def _fetch_user_state(
        self,
        cursor: Any,
        emp_no: str,
        *,
        for_update: bool = False,
    ) -> dict[str, Any] | None:
        """Read FLOGINNAME/FUSERSTATE/FCHANGEDATE into canonical lower-case keys.

        186 v1.10 P0-16（全链修复）：真实 oracledb cursor.description 报告
        Oracle 端的大写列名；此前 cols 被 lower() 而调用方读大写键，真实
        cursor 路径必然 KeyError。现从 cursor.description 逐列大小写不敏感
        映射到 {floginname, fuserstate, fchangedate}（未知列忽略）。写路径
        传 ``for_update=True`` 加行锁。
        """
        sql = (
            "SELECT FLOGINNAME, FUSERSTATE, FCHANGEDATE FROM CDMS.T_MSS_EMP_DICT "
            "WHERE FLOGINNAME = :emp_no"
        )
        if for_update:
            sql += " FOR UPDATE"
        cursor.execute(sql, {"emp_no": emp_no})
        row = cursor.fetchone()
        if row is None:
            return None
        state: dict[str, Any] = {}
        for desc, value in zip(cursor.description, row):
            canonical = str(desc[0]).strip().lower()
            if canonical in _USER_STATE_CANONICAL_KEYS and canonical not in state:
                state[canonical] = value
        return state

    def read_account_state(self, emp_no: str) -> dict[str, Any] | None:
        """186 I3：读单个 CDMS 账号状态（规范小写键，FCHANGEDATE 供归因）。"""
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            return self._fetch_user_state(cursor, emp_no)
        finally:
            cursor.close()

    def unlock_user(
        self,
        emp_no: str,
        *,
        origin_disable: dict | None = None,
    ) -> dict[str, Any]:
        """186 v1.10 §13.3/P0-17：受控恢复 FUSERSTATE '1'→'0'（变更检测 CAS）。

        语义边界：只验证“平台持久停用证据（origin_disable）中的目标原始
        时间值与当前行 FCHANGEDATE 精确不变”，并用 CAS 条件更新
        （FUSERSTATE='1' AND FCHANGEDATE=:expected_changed）落库。时间一致
        不证明锁归本规则所有——所有权证据在编排/门禁层；这里承担目标行
        未被再次修改的变更检测（先比对再 UPDATE，双保险）。

        origin_disable keys：``attempt_id``(int)、``target_raw_time``(str|None)、
        ``target_account_fingerprint``(str)、``rule_version``(str)。
        - state=='0' → skipped already_enabled；state!='1' → blocked
          unexpected_state。
        - origin 缺失 / target_raw_time 缺失 / 当前行 FCHANGEDATE 缺失 /
          origin raw 不是可解析的 ISO 时间 → blocked attribution_unknown。
        - 当前原始值与 origin 原始值精确比对（同一规范化后字符串全等，无
          ±容差、无时区换算）不等 → blocked attribution_target_changed。
        - CAS UPDATE rowcount==0 → blocked attribution_target_changed（并发
          修改，rollback）；rowcount>1 → raise 回滚。不重设密码、不改角色。
        """
        conn = self._require_conn()
        cursor = conn.cursor()
        try:
            current = self._fetch_user_state(cursor, emp_no, for_update=True)
            if current is None:
                return {"status": "missing_target", "emp_no": emp_no}
            state = str(current.get("fuserstate")).strip()
            if state == "0":
                return {"status": "skipped", "reason": "already_enabled", "emp_no": emp_no}
            if state != "1":
                return {"status": "blocked", "reason": "unexpected_state", "emp_no": emp_no}

            origin_raw = (
                origin_disable.get("target_raw_time")
                if origin_disable is not None
                else None
            )
            origin_raw_text = _normalize_raw_time(origin_raw)
            current_raw = _normalize_raw_time(current.get("fchangedate"))
            if (
                origin_disable is None
                or origin_raw_text is None
                or current_raw is None
            ):
                return {
                    "status": "blocked",
                    "reason": "attribution_unknown",
                    "lock_attribution": "manual_or_unknown",
                    "emp_no": emp_no,
                }
            if origin_raw_text != current_raw:
                return {
                    "status": "blocked",
                    "reason": "attribution_target_changed",
                    "lock_attribution": "manual_or_unknown",
                    "emp_no": emp_no,
                }

            # CAS 绑定值必须是 datetime（与 Oracle FCHANGEDATE 可比）。
            if isinstance(origin_raw, datetime):
                expected_changed = origin_raw
            else:
                try:
                    expected_changed = datetime.fromisoformat(origin_raw_text)
                except ValueError:
                    return {
                        "status": "blocked",
                        "reason": "attribution_unknown",
                        "lock_attribution": "manual_or_unknown",
                        "emp_no": emp_no,
                    }

            cursor.execute(
                _SQL_UNLOCK_USER_CAS,
                {"emp_no": emp_no, "expected_changed": expected_changed},
            )
            affected = cursor.rowcount
            if affected == 0:
                conn.rollback()
                return {
                    "status": "blocked",
                    "reason": "attribution_target_changed",
                    "lock_attribution": "manual_or_unknown",
                    "emp_no": emp_no,
                }
            if affected > 1:
                raise RuntimeError(f"unlock update affected {affected} rows; expected 1")
            verified = self._fetch_user_state(cursor, emp_no)
            if verified is None or str(verified.get("fuserstate")).strip() != "0":
                raise RuntimeError("unlock read-back mismatch")
            conn.commit()
            return {
                "status": "success",
                "rows_affected": affected,
                "emp_no": emp_no,
                "lock_attribution": "by_this_rule",
                "origin_disable_attempt_id": origin_disable["attempt_id"],
            }
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                logger.debug("rollback error", exc_info=True)
            return {"status": "failed", "reason": sanitize_text(str(exc), limit=300), "emp_no": emp_no}
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
