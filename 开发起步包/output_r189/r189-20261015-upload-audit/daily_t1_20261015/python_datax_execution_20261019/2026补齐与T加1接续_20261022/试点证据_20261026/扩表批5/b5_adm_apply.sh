#!/bin/sh
set -e
RC="python /app/scripts/reporting_ctl.py"
CD="--config /opt/data-asset/t1-config"
FL="--bindings-file /opt/data-asset/t1-config/bindings_batch5.json --runtime-config /opt/data-asset/t1-config/freeze_batch5_v3.json --state-db $APP_DB_URL --stage-root /opt/data-asset/t1-stage"
REF="T1-EXPAND-B5-20261025:emr_admission_record"
BID="DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
echo "=== STEP4 apply（QUARANTINED 合法子集续跑，批1范式）==="
APPLY_START=$(date '+%F %T')
$RC $CD apply --batch "$BID" --approval-ref "$REF" $FL
APPLY_END=$(date '+%F %T')
echo "APPLY_WINDOW=$APPLY_START $APPLY_END"
echo "=== STEP5 reconcile ==="
$RC $CD reconcile --batch "$BID" $FL
echo "=== DONE apply+reconcile ==="
