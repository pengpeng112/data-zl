#!/bin/sh
set -e
RC="python /app/scripts/reporting_ctl.py"
CD="--config /opt/data-asset/t1-config"
FL="--bindings-file /opt/data-asset/t1-config/bindings_batch4.json --runtime-config /opt/data-asset/t1-config/freeze_batch4_v1.json --state-db $APP_DB_URL --stage-root /opt/data-asset/t1-stage"
REF="T1-EXPAND-B4-20261025:emr_admission_assessment"
echo "=== TABLE EMR_ADMISSION_ASSESSMENT 业务日 2026-10-24 ==="
if [ "$SKIP_APPROVAL" != "1" ]; then
  echo "=== STEP1 approval-register ==="
  date '+%F %T'
  $RC approval-register --state-db "$APP_DB_URL" --approval-ref "$REF"     --executor-code sql-target-apply-1     --target-scope "10.10.8.74:1521/orcl.DBOPER.EMR_ADMISSION_ASSESSMENT"     --registered-by "用户会话批准2026-10-25(扩表批4并行试点)" --valid-hours 24     --note "扩表批4试点"
else
  echo "=== STEP1 approval-register SKIPPED（已登记） ==="
fi
echo "=== STEP2 capture ==="
date '+%F %T'
$RC $CD capture --table EMR_ADMISSION_ASSESSMENT --business-day 2026-10-24 $FL > /tmp/b4_cap.out 2>&1 || { cat /tmp/b4_cap.out; exit 1; }
cat /tmp/b4_cap.out
BID=$(python -c "import json;print(json.load(open('/tmp/b4_cap.out'))['batch_id'])")
echo "BATCH_ID=$BID"
echo "=== STEP3 verify ==="
date '+%F %T'
$RC $CD verify --batch "$BID" $FL
echo "=== STEP4 apply ==="
APPLY_START=$(date '+%F %T')
$RC $CD apply --batch "$BID" --approval-ref "$REF" $FL
APPLY_END=$(date '+%F %T')
echo "APPLY_WINDOW=$APPLY_START $APPLY_END"
echo "=== STEP5 reconcile ==="
date '+%F %T'
$RC $CD reconcile --batch "$BID" $FL
echo "=== DONE EMR_ADMISSION_ASSESSMENT ==="
