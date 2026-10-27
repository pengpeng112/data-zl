#!/bin/sh
set -e
RC="python /app/scripts/reporting_ctl.py"
CD="--config /opt/data-asset/t1-config"
FL="--bindings-file /opt/data-asset/t1-config/bindings_batch8.json --runtime-config /opt/data-asset/t1-config/freeze_batch8_v1.json --state-db $APP_DB_URL --stage-root /opt/data-asset/t1-stage"
REF="T1-EXPAND-B8-20261026:emr_outpatient_diag"
BID="DBOPER.EMR_OUTPATIENT_DIAG.T1.2026-10-26.3d125309117a"
echo "=== TABLE EMR_OUTPATIENT_DIAG 续跑（QUARANTINED 合法子集 apply）==="
echo "=== STEP4 apply ==="
APPLY_START=$(date '+%F %T')
$RC $CD apply --batch "$BID" --approval-ref "$REF" $FL
APPLY_END=$(date '+%F %T')
echo "APPLY_WINDOW=$APPLY_START $APPLY_END"
echo "=== STEP5 reconcile ==="
date '+%F %T'
$RC $CD reconcile --batch "$BID" $FL
echo "=== DONE EMR_OUTPATIENT_DIAG 续跑 ==="
