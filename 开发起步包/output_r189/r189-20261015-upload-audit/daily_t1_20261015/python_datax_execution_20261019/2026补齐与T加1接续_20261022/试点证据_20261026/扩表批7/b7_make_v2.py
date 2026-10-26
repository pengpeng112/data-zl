"""批7 v2 表达式注入（照批5 v3 范式）：v1 载入→改 14 处 source_expression
（13 错配列+VISIT_DATE NULL 投影）→compute_table_fingerprint/compute_config_fingerprint
重算→写 v2。mask 依据=活源预核（前置探查与mask样例_20261026.out+mask补充值域_20261026.out）：
- OPERATION_NURSING 六列源值全 'YYYY-MM-DD HH24:MI:SS'（时间部分可选防御）；
- REFERRAL.SURGERY_START_DATE 源值全表 264 行 LEN=9 NLS 'DD-MON-YY' 中文月格式
  （'08-12月-25'/'29-1月 -26'，月段 1-2 位数字+'月'+可选填充空格）；
- JOB_CODE 全值域 2 位数字串；ANES_METHOD_CODE 全数字串；
- PROF_TECH_CATE_CODE/PERFORM_ANES_CODE/AGE_MONTH 源 NUMBER（位数≤2）TO_CHAR 无超长风险；
- PERFORM_OPERATION_DATE 目标既有值 LEN 分布 9(22691)/14(79681)，按预核模板写 14 字符紧凑格式。
表达式全部自带 AS <列名>（批5 v2 漏 AS 教训）。
运行：cd backend && ./.venv/Scripts/python.exe <任务目录>/试点证据_20261026/扩表批7/b7_make_v2.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.services.reporting_pipeline.runtime_config import (
    compute_config_fingerprint,
    compute_table_fingerprint,
)

TASK_DIR = Path(
    r"F:/python/数据资产/开发起步包/output_r189/r189-20261015-upload-audit/"
    r"daily_t1_20261015/python_datax_execution_20261019/2026补齐与T加1接续_20261022"
)
V1 = TASK_DIR / "扩表冻结件_批7_ODS二波_v1_20261026.json"
V2 = TASK_DIR / "扩表冻结件_批7_ODS二波_v2_20261026.json"

# 13 错配列表达式（预核结论§四模板 + 活源 mask 实测定案）
EXPRS = {}

# OPERATION_NURSING 六列 VARCHAR2→DATE 全 NOT NULL（时间部分可选；脏值→NULL→REQUIRED 隔离合法子集）
OPN_COLS = ["OPERATION_END_DATE", "OPERATION_START_DATE", "IN_ROOM_DATE",
            "OUT_ROOM_DATE", "HANDOVER_DATE", "RECORD_DATE"]
for c in OPN_COLS:
    EXPRS[("EMR_OPERATION_NURSING", c)] = (
        f'CASE WHEN REGEXP_LIKE("{c}",\'^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
        f'([ ][0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}})?$\') '
        f"THEN TO_DATE(\"{c}\",'YYYY-MM-DD HH24:MI:SS') ELSE NULL END AS {c}"
    )

# REFERRAL.SURGERY_START_DATE VARCHAR2→DATE 可空：NLS 'DD-MON-YY' 中文月（活源全表实测唯一形态）
EXPRS[("EMR_REFERRAL_HOS_RECORD", "SURGERY_START_DATE")] = (
    'CASE WHEN REGEXP_LIKE("SURGERY_START_DATE",'
    "'^[0-9]{2}-[0-9]{1,2}\u6708 ?-[0-9]{2}$') "
    "THEN TO_DATE(\"SURGERY_START_DATE\",'DD-MON-YY',"
    "'NLS_DATE_LANGUAGE=''SIMPLIFIED CHINESE''') "
    "ELSE NULL END AS SURGERY_START_DATE"
)

# S→N 可空：JOB_CODE（活源全值域 2 位数字串）
EXPRS[("EMR_ADMISSION_DEAD_RECORD_TF", "JOB_CODE")] = (
    'CASE WHEN REGEXP_LIKE("JOB_CODE",\'^[0-9]+\\.?[0-9]*$\') '
    'THEN TO_NUMBER("JOB_CODE") ELSE NULL END AS JOB_CODE'
)

# S→N NOT NULL：ANES_METHOD_CODE（脏值→NULL→REQUIRED 隔离合法子集）
EXPRS[("EMR_AFTER_OPERA_RECORD", "ANES_METHOD_CODE")] = (
    'CASE WHEN REGEXP_LIKE("ANES_METHOD_CODE",\'^[0-9]+\\.?[0-9]*$\') '
    'THEN TO_NUMBER("ANES_METHOD_CODE") ELSE NULL END AS ANES_METHOD_CODE'
)

# N→S：TO_CHAR
EXPRS[("EMR_HOS_PREOP_DISCUSS", "PROF_TECH_CATE_CODE")] = \
    'TO_CHAR("PROF_TECH_CATE_CODE") AS PROF_TECH_CATE_CODE'
EXPRS[("EMR_HOS_PREOP_DISCUSS", "PERFORM_ANES_CODE")] = \
    'TO_CHAR("PERFORM_ANES_CODE") AS PERFORM_ANES_CODE'
EXPRS[("EMR_INFOR_ANESTHESIA", "AGE_MONTH")] = \
    'TO_CHAR("AGE_MONTH") AS AGE_MONTH'

# D→S(14)：14 字符紧凑格式（目标既有值 14 字符为主形态 79681/102372）
EXPRS[("EMR_HOS_PREOP_DISCUSS", "PERFORM_OPERATION_DATE")] = \
    'TO_CHAR("PERFORM_OPERATION_DATE",\'YYYYMMDDHH24MISS\') AS PERFORM_OPERATION_DATE'

# 真缺口列：目标 DATE 可空，视图不暴露 → NULL 投影（批1 HRP 先例）
EXPRS[("EMR_OUTPATIENT_RECIPE_ITEM", "VISIT_DATE")] = 'NULL AS VISIT_DATE'

doc = json.loads(V1.read_text(encoding="utf-8"))
assert doc["version"] == "v1"
assert len(EXPRS) == 14, len(EXPRS)

changed = []
for tname, tdoc in doc["tables"].items():
    for f in tdoc["projection"]:
        key = (tname, f["name"])
        if key in EXPRS:
            old = f["source_expression"]
            f["source_expression"] = EXPRS[key]
            changed.append((tname, f["name"], old, f["source_expression"]))
        else:
            # 其余列恒等投影不动（含 OR_ID 盲区列恒等）
            assert f["source_expression"] == f["name"], (tname, f["name"])
assert len(changed) == 14, len(changed)

doc["version"] = "v2"
# 表指纹与整件指纹重算
for tname, tdoc in doc["tables"].items():
    tdoc["fingerprint"] = compute_table_fingerprint(tdoc)
doc["config_fingerprint"] = compute_config_fingerprint(doc)

V2.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("v2 written:", V2.name)
print("config_fingerprint(v2):", doc["config_fingerprint"])
print("changed 14 columns:")
for t, c, old, new in changed:
    print(f"  {t}.{c}: {old} -> {new}")
