"""H5 readonly precheck for one authorized signature补跑.

Env:
  APP_SINGLE_SIGNATURE_EMP_NO  temporary emp no (not printed)

Output: fingerprint_short, source image dims, target emptiness, counts only.
Never prints emp, names, tokens, or image bytes.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from io import BytesIO

from app.core.config import settings
from app.services.his_identity_sync import _connector
from app.services.identity_hmac import compute_account_fingerprint
from app.services.identity_sync_status import short_fingerprint
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
from app.services.signature_image import normalize_signature_image


def main() -> int:
    emp = (os.environ.get("APP_SINGLE_SIGNATURE_EMP_NO") or "").strip()
    if not emp:
        print(json.dumps({"status": "failed", "error": "APP_SINGLE_SIGNATURE_EMP_NO required"}))
        return 2

    out: dict = {"status": "ok"}
    try:
        out["fingerprint_short"] = short_fingerprint(
            compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref)
        )
    except Exception as exc:
        out["fingerprint_short"] = "hmac-unavailable"
        out["hmac_error"] = type(exc).__name__

    # HIS source
    his = _connector()
    try:
        rows = his.execute_readonly(
            "SELECT EMPLCODE, SIGNATUREBASE64, MODIFIEDTIME FROM FXHIS.SYS_EMPLOYEE_QM "
            "WHERE EMPLCODE = :emp_no AND SIGNATUREBASE64 IS NOT NULL "
            "AND DBMS_LOB.GETLENGTH(SIGNATUREBASE64) > 0 AND ROWNUM <= 1",
            params={"emp_no": emp},
            max_rows=1,
        )
        out["his_rows"] = len(rows)
        if not rows:
            out["status"] = "failed"
            out["error"] = "his_signature_missing"
            print(json.dumps(out, ensure_ascii=True, default=str))
            return 1
        raw = rows[0].get("SIGNATUREBASE64")
        text = raw.read() if hasattr(raw, "read") else str(raw or "")
        encoded = text.split(",", 1)[1] if "," in text else text
        image = base64.b64decode(encoded, validate=True)
        from PIL import Image

        with Image.open(BytesIO(image)) as im:
            im.load()
            out["source_format"] = im.format
            out["source_width"], out["source_height"] = im.size
            out["source_bytes"] = len(image)
        normalized = normalize_signature_image(image)
        with Image.open(BytesIO(normalized)) as im2:
            im2.load()
            out["target_format"] = im2.format
            out["target_width"], out["target_height"] = im2.size
            out["target_bytes"] = len(normalized)
        out["has_modifiedtime"] = bool(rows[0].get("MODIFIEDTIME") or rows[0].get("modifiedtime"))
    finally:
        his.close()

    # JHEMR target
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
        adapter.connect()
        users = adapter._fetch_all(
            "SELECT user_id, user_name FROM jhemr.users WHERE user_id = %s AND hospital_no = %s",
            (emp, settings.identity_sync_jhemr_hospital_no),
        )
        out["jhemr_user_count"] = len(users)
        pics = adapter._fetch_all(
            "SELECT user_id, octet_length(user_name_pic) AS size FROM jhemr.users_pic WHERE user_id = %s",
            (emp,),
        )
        out["jhemr_pic_count"] = len(pics)
        out["jhemr_pic_bytes"] = int(pics[0]["size"] or 0) if pics else 0
        out["target_empty"] = out["jhemr_user_count"] == 1 and out["jhemr_pic_count"] == 1 and out["jhemr_pic_bytes"] == 0
        out["ready_to_write"] = bool(
            out.get("his_rows") == 1
            and out.get("target_empty")
            and out.get("target_width", 999) <= 150
        )
    finally:
        adapter.close()

    print(json.dumps(out, ensure_ascii=True, default=str))
    os.environ.pop("APP_SINGLE_SIGNATURE_EMP_NO", None)
    return 0 if out.get("ready_to_write") else 1


if __name__ == "__main__":
    raise SystemExit(main())
