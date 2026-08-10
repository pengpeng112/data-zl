"""Read HIS signatures and idempotently fill missing JHEMR pictures.

The target adapter remains the only writer.  This module records only HMAC
account fingerprints, counts and stable error categories; it never returns
employee numbers, SQL parameters or signature bytes.
"""

from __future__ import annotations

import base64
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..core.config import settings
from .his_identity_sync import _connector, _select
from .identity_hmac import compute_account_fingerprint
from .identity_sync_status import error_code_masked, increment_error, short_fingerprint
from .identity_sync_audit import AuditWriteError, create_action, finish_action
from .identity_watermark import advance_watermark, max_watermark
from .jhemr_identity_adapter import JhemrIdentityAdapter
from .signature_image import normalize_signature_image

logger = logging.getLogger(__name__)


def _subtask_status(*, failed: int, processed: int) -> str:
    if failed == 0:
        return "success"
    return "partial_success" if processed > failed else "failed"


def sync_missing_jhemr_signatures(
    *,
    max_rows: int | None = None,
    run_id: str | None = None,
    db=None,
    emp_no: str | None = None,
    advance_watermark_on_success: bool = True,
) -> dict[str, Any]:
    """Sync missing JHEMR signature pictures from HIS.

    When ``emp_no`` is set, only that single employee is selected (exact match,
    ROWNUM<=1). Single-account补跑 must pass ``advance_watermark_on_success=False``
    so a one-off write never advances the nightly watermark.
    """
    limit = max(1, min(int(max_rows or settings.his_identity_sync_max_rows), 50000))
    only_emp = (emp_no or "").strip() or None
    if only_emp:
        limit = 1
    source_rows: list[tuple[str, bytes, datetime | None]] = []
    source_errors: dict[str, dict[str, int]] = {}

    # I3: source selection has its own error category and closes without a
    # target connection if the read fails.
    his = None
    try:
        his = _connector()
        if only_emp:
            # Exact one-account path for authorized single-account补跑.
            # Bind only EMPLCODE; never log the value.
            try:
                rows = his.execute_readonly(
                    "SELECT EMPLCODE, SIGNATUREBASE64, MODIFIEDTIME FROM FXHIS.SYS_EMPLOYEE_QM "
                    "WHERE EMPLCODE = :emp_no AND SIGNATUREBASE64 IS NOT NULL "
                    "AND DBMS_LOB.GETLENGTH(SIGNATUREBASE64) > 0 AND ROWNUM <= 1",
                    params={"emp_no": only_emp},
                    max_rows=1,
                )
            except Exception:
                rows = his.execute_readonly(
                    "SELECT EMPLCODE, SIGNATUREBASE64 FROM FXHIS.SYS_EMPLOYEE_QM "
                    "WHERE EMPLCODE = :emp_no AND SIGNATUREBASE64 IS NOT NULL "
                    "AND DBMS_LOB.GETLENGTH(SIGNATUREBASE64) > 0 AND ROWNUM <= 1",
                    params={"emp_no": only_emp},
                    max_rows=1,
                )
        else:
            try:
                rows = _select(
                    his,
                    "SELECT EMPLCODE, SIGNATUREBASE64, MODIFIEDTIME FROM FXHIS.SYS_EMPLOYEE_QM WHERE SIGNATUREBASE64 IS NOT NULL AND DBMS_LOB.GETLENGTH(SIGNATUREBASE64) > 0 AND ROWNUM <= :max_rows",
                    limit,
                )
            except Exception:
                # Some legacy deployments lack MODIFIEDTIME on the signature
                # table. Keep the source read bounded, but mark its independent
                # watermark stalled instead of pretending it advanced.
                rows = _select(
                    his,
                    "SELECT EMPLCODE, SIGNATUREBASE64 FROM FXHIS.SYS_EMPLOYEE_QM WHERE SIGNATUREBASE64 IS NOT NULL AND DBMS_LOB.GETLENGTH(SIGNATUREBASE64) > 0 AND ROWNUM <= :max_rows",
                    limit,
                )
        for row in rows:
            row_emp = str(row.get("EMPLCODE") or "").strip()
            raw = row.get("SIGNATUREBASE64")
            text = raw.read() if hasattr(raw, "read") else str(raw or "")
            encoded = text.split(",", 1)[1] if "," in text else text
            try:
                image = base64.b64decode(encoded, validate=True) if encoded else b""
                if image:
                    image = normalize_signature_image(image)
            except Exception as exc:
                increment_error(source_errors, "source_signature_select", exc)
                image = b""
            if row_emp and image:
                if only_emp and row_emp != only_emp:
                    # Fail closed: never process a different employee.
                    continue
                modified = row.get("MODIFIEDTIME") or row.get("modifiedtime")
                try:
                    modified = datetime.fromisoformat(str(modified)) if modified else None
                    if modified and modified.tzinfo is None:
                        modified = modified.replace(tzinfo=timezone.utc)
                except ValueError:
                    modified = None
                source_rows.append((row_emp, image, modified))
    except Exception as exc:
        increment_error(source_errors, "source_signature_select", exc)
    finally:
        if his is not None:
            his.close()

    result: dict[str, Any] = {
        "status": "failed" if source_errors and not source_rows else "running",
        "run_id": run_id,
        "planned_count": len(source_rows),
        "source_signatures": len(source_rows),
        "inserted": 0,
        "skipped_existing": 0,
        "skipped_no_user": 0,
        "failed": 0,
        "error_classes": source_errors,
        "failed_fingerprints": [],
        "watermark": {"watermark_key": "jhemr_signature_sync", "status": "stalled", "candidate": None},
    }
    if source_errors and not source_rows:
        result["status"] = "failed"
        return result

    adapter = JhemrIdentityAdapter(
        credential_ref=settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
    )
    try:
        try:
            adapter.connect()
        except Exception as exc:
            increment_error(result["error_classes"], "target_user_lookup_select", exc)
            result["failed"] = len(source_rows)
            result["failed_fingerprints"] = [
                short_fingerprint(compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref))
                for emp, _, _ in source_rows[:3]
            ] if source_rows else []
            result["status"] = "failed"
            return result

        for emp_no, image, modified in source_rows:
            fingerprint: str | None = None
            action = None
            try:
                fingerprint = compute_account_fingerprint(emp_no, "JHEMR", settings.identity_hmac_key_ref)
            except Exception as exc:
                increment_error(result["error_classes"], "target_user_lookup_select", exc)
                result["failed"] += 1
                if len(result["failed_fingerprints"]) < 3:
                    result["failed_fingerprints"].append("hmac-unavailable")
                continue
            try:
                # The audit row is durable before the target transaction.  A
                # failed audit write therefore prevents an untraceable write.
                action = create_action(db, run_id=run_id or "unbound", fingerprint=fingerprint)
                try:
                    user = adapter._fetch_all(
                        "SELECT user_name FROM jhemr.users WHERE user_id = %s AND hospital_no = %s",
                        (emp_no, settings.identity_sync_jhemr_hospital_no),
                    )
                except Exception as exc:
                    increment_error(result["error_classes"], "target_user_lookup_select", exc)
                    raise
                if not user:
                    result["skipped_no_user"] += 1
                    finish_action(db, action, status="skipped", reason_code="no_target_user")
                    continue
                display_name = user[0].get("user_name") or ""
                cur = adapter._conn.cursor()
                try:
                    try:
                        cur.execute(
                            "SELECT octet_length(user_name_pic) FROM jhemr.users_pic WHERE user_id = %s FOR UPDATE",
                            (emp_no,),
                        )
                        existing = cur.fetchone()
                    except Exception as exc:
                        increment_error(result["error_classes"], "target_picture_lock_select", exc)
                        raise
                    if existing and existing[0]:
                        result["skipped_existing"] += 1
                        finish_action(db, action, status="skipped", reason_code="already_has_signature")
                        continue
                    if existing:
                        try:
                            cur.execute(
                                "UPDATE jhemr.users_pic SET user_name_pic = %s, user_name = COALESCE(user_name, %s), extension_file_name = '.jpg' WHERE user_id = %s AND (user_name_pic IS NULL OR octet_length(user_name_pic) = 0)",
                                (image, display_name, emp_no),
                            )
                        except Exception as exc:
                            increment_error(result["error_classes"], "target_picture_update", exc)
                            raise
                    else:
                        try:
                            cur.execute(
                                "INSERT INTO jhemr.users_pic (user_id, user_name_pic, user_name, create_date, use_flag, extension_file_name, hospital_no) SELECT %s, %s, %s, CURRENT_TIMESTAMP, 1, '.jpg', %s WHERE NOT EXISTS (SELECT 1 FROM jhemr.users_pic WHERE user_id = %s)",
                                (emp_no, image, display_name, settings.identity_sync_jhemr_hospital_no, emp_no),
                            )
                        except Exception as exc:
                            increment_error(result["error_classes"], "target_picture_insert", exc)
                            raise
                    affected = int(cur.rowcount or 0)
                    try:
                        adapter._conn.commit()
                    except Exception as exc:
                        increment_error(result["error_classes"], "target_commit", exc)
                        raise
                    if affected:
                        result["inserted"] += 1
                        finish_action(db, action, status="executed", rows_affected=affected)
                    else:
                        result["skipped_existing"] += 1
                        finish_action(db, action, status="skipped", reason_code="idempotent_noop")
                    # A cheap, parameter-free rowcount/readback assertion keeps
                    # the audit honest without returning the signature.
                    try:
                        readback = adapter._fetch_all(
                            "SELECT octet_length(user_name_pic) AS size FROM jhemr.users_pic WHERE user_id = %s",
                            (emp_no,),
                        )
                        if affected and (not readback or not readback[0].get("size")):
                            raise RuntimeError("target_readback_empty")
                    except Exception as exc:
                        increment_error(result["error_classes"], "target_readback", exc)
                        raise
                finally:
                    cur.close()
            except AuditWriteError as exc:
                increment_error(result["error_classes"], "target_commit", exc)
                result["failed"] += 1
                if len(result["failed_fingerprints"]) < 3:
                    result["failed_fingerprints"].append(short_fingerprint(fingerprint))
                # Do not attempt a target write after an audit failure.
            except Exception as exc:
                try:
                    adapter._conn.rollback()
                except Exception as rollback_exc:
                    increment_error(result["error_classes"], "target_commit", rollback_exc)
                result["failed"] += 1
                if len(result["failed_fingerprints"]) < 3:
                    result["failed_fingerprints"].append(short_fingerprint(fingerprint))
                try:
                    finish_action(db, action, status="failed", error_class=next(iter(result["error_classes"]), "target_write"), error_code=error_code_masked(exc))
                except AuditWriteError:
                    # The original target failure remains the authoritative
                    # task state; audit failure is counted as target_commit.
                    increment_error(result["error_classes"], "target_commit", "audit_write")
                logger.error("signature sync item failed: error_class=%s", ";".join(sorted(result["error_classes"].keys())))
    finally:
        adapter.close()

    processed = result["inserted"] + result["skipped_existing"] + result["skipped_no_user"] + result["failed"]
    result["status"] = _subtask_status(failed=result["failed"], processed=processed)
    if result["error_classes"] and result["status"] == "success":
        result["status"] = "partial_success"
    result["processed_count"] = processed
    candidate = max_watermark([
        (modified, compute_account_fingerprint(emp_no, "HIS", settings.identity_hmac_key_ref))
        for emp_no, _, modified in source_rows
    ])
    if candidate.create_date is not None:
        result["watermark"] = {"watermark_key": "jhemr_signature_sync", "status": "candidate" if result["failed"] else "committed", "candidate": candidate.create_date.isoformat()}
        if (
            db is not None
            and result["failed"] == 0
            and advance_watermark_on_success
            and not only_emp
        ):
            # Single-account补跑 never advances the nightly watermark.
            advance_watermark(db, source_code="HIS", watermark_key="jhemr_signature_sync", candidate=candidate, run_id=run_id or "unbound", success=True)
    return result
