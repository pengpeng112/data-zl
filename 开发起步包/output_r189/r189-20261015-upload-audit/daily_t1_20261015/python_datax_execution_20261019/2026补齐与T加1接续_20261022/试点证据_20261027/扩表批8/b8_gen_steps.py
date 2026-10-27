"""批8 五步驱动脚本生成器（照批6 b6_gen_steps.py 模板，批8 前缀/配置卷/批准号/业务日 2026-10-26）。"""
from pathlib import Path

TABLES = ["EMR_ANES_RECORD_MED", "EMR_ADMISSION_RECORD_EXAM", "EMR_CONSUMABLES",
          "EMR_OUTPATIENT_DIAG", "EMR_DOC_ORDER_DRUG", "EMR_OUT_FEE_INFO_MAIN",
          "EMR_OUT_FEE_INFO_CHILD", "EMR_IN_FEE_INFO_CHILD", "EMR_INFOR_OPERATION",
          "EMR_INFOR_OTHERS"]

TPL = r'''#!/bin/sh
set -e
RC="python /app/scripts/reporting_ctl.py"
CD="--config /opt/data-asset/t1-config"
FL="--bindings-file /opt/data-asset/t1-config/bindings_batch8.json --runtime-config /opt/data-asset/t1-config/freeze_batch8_v1.json --state-db $APP_DB_URL --stage-root /opt/data-asset/t1-stage"
REF="T1-EXPAND-B8-20261026:__LOWER__"
echo "=== TABLE __TABLE__ 业务日 2026-10-26 ==="
if [ "$SKIP_APPROVAL" != "1" ]; then
  echo "=== STEP1 approval-register ==="
  date '+%F %T'
  $RC approval-register --state-db "$APP_DB_URL" --approval-ref "$REF"     --executor-code sql-target-apply-1     --target-scope "10.10.8.74:1521/orcl.DBOPER.__TABLE__"     --registered-by "用户会话批准2026-10-26(扩表批8并行试点)" --valid-hours 24     --note "扩表批8试点"
else
  echo "=== STEP1 approval-register SKIPPED（已登记） ==="
fi
echo "=== STEP2 capture ==="
date '+%F %T'
$RC $CD capture --table __TABLE__ --business-day 2026-10-26 $FL > /tmp/b8_cap.out 2>&1 || { cat /tmp/b8_cap.out; exit 1; }
cat /tmp/b8_cap.out
BID=$(python -c "import json;print(json.load(open('/tmp/b8_cap.out'))['batch_id'])")
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
echo "=== DONE __TABLE__ ==="
'''

here = Path(__file__).parent
for t in TABLES:
    text = TPL.replace("__TABLE__", t).replace("__LOWER__", t.lower())
    (here / f"b8_steps_{t.lower()}.sh").write_text(
        text, encoding="utf-8", newline="\n")
print("written", len(TABLES), "driver scripts to", here)
