"""批7 冻结件 v2 本地核验：装载即验 + Oracle 渲染断言（14 处表达式各 2 次=嵌套分页两遍，
其余列零表达式 token）+ 投影与 bindings 逐列一致 + 锚点直谓词 + 无父子。
运行：cd backend && ./.venv/Scripts/python.exe <任务目录>/试点证据_20261026/扩表批7/b7_local_freeze_verify.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config
from app.services.reporting_pipeline.source_factory import OracleProjectionQueryBuilder
from app.services.reporting_pipeline.planner import TimeWindow

TASK_DIR = Path(
    r"F:/python/数据资产/开发起步包/output_r189/r189-20261015-upload-audit/"
    r"daily_t1_20261015/python_datax_execution_20261019/2026补齐与T加1接续_20261022"
)
FREEZE = TASK_DIR / "扩表冻结件_批7_ODS二波_v2_20261026.json"
BINDINGS = TASK_DIR / "扩表bindings_批7_20261026.json"

cfg = load_frozen_runtime_config(str(FREEZE))
print(f"load OK: environment={cfg.environment}")
print(f"config fp: {cfg.config_fingerprint}")
print(f"tables: {sorted(cfg.tables)}")

bindings = json.loads(BINDINGS.read_text(encoding="utf-8"))
win = TimeWindow(datetime(2026, 10, 25, 0, 0, 0), datetime(2026, 10, 26, 0, 0, 0))

# 14 处表达式（13 错配列 + VISIT_DATE NULL 投影）：各应出现 2 次（嵌套分页两遍）
EXPR_COLS = {
    "EMR_OPERATION_NURSING": ["OPERATION_END_DATE", "OPERATION_START_DATE", "IN_ROOM_DATE",
                              "OUT_ROOM_DATE", "HANDOVER_DATE", "RECORD_DATE"],
    "EMR_REFERRAL_HOS_RECORD": ["SURGERY_START_DATE"],
    "EMR_ADMISSION_DEAD_RECORD_TF": ["JOB_CODE"],
    "EMR_AFTER_OPERA_RECORD": ["ANES_METHOD_CODE"],
    "EMR_HOS_PREOP_DISCUSS": ["PROF_TECH_CATE_CODE", "PERFORM_OPERATION_DATE", "PERFORM_ANES_CODE"],
    "EMR_INFOR_ANESTHESIA": ["AGE_MONTH"],
    "EMR_OUTPATIENT_RECIPE_ITEM": ["VISIT_DATE"],
}
EXPR_TOKENS = ("CASE WHEN", "CONVERT(", "TO_DATE(", "TO_CHAR(", "TO_NUMBER(", "NULLIF(",
               "NULL AS ", "REGEXP_LIKE")

problems = []
for name in sorted(cfg.tables):
    spec = cfg.tables[name]
    if spec.dialect != "oracle":
        problems.append(f"{name}: dialect != oracle")
    if spec.source_group != "ods":
        problems.append(f"{name}: source_group={spec.source_group}")
    if spec.anchor_column != "DATETIME" or spec.anchor_expression is not None:
        problems.append(f"{name}: anchor={spec.anchor_column} expr={spec.anchor_expression}")
    if list(spec.stable_key) != ["ID"]:
        problems.append(f"{name}: stable_key={list(spec.stable_key)}")
    if spec.parent_table:
        problems.append(f"{name}: parent={spec.parent_table}")
    builder = OracleProjectionQueryBuilder(spec)
    sql, params = builder(win, None, 50000)
    if "DATETIME >= :1 AND DATETIME < :2" not in sql:
        problems.append(f"{name}: anchor predicate not plain: {sql[:200]}")
    if "ORDER BY ID" not in sql or "ROWNUM <= :3" not in sql:
        problems.append(f"{name}: pagination shape wrong")
    # 表达式断言：本表清单内列 → 表达式 token 各 2 次；其余列 → 零 token
    expr_cols = EXPR_COLS.get(name, [])
    for f in spec.projection:
        is_expr = f.name in expr_cols
        cnt = sum(sql.upper().count(tok) for tok in EXPR_TOKENS
                  if tok.upper() in f.source_expression.upper())
        if is_expr:
            if cnt == 0:
                problems.append(f"{name}.{f.name}: expression column has no expression")
            # SQL 中出现次数（近似：列名跟随表达式出现 2 次）
            if sql.count(f"AS {f.name}") != 2:
                problems.append(
                    f"{name}.{f.name}: 'AS {f.name}' appears {sql.count(f'AS {f.name}')} times (expect 2)")
        else:
            if f.source_expression.strip() != f.name:
                problems.append(f"{name}.{f.name}: non-identity source_expression")
    # 投影与 bindings write_columns 逐列一致
    fz_cols = sorted(f.name for f in spec.projection)
    bd_cols = sorted(bindings["targets_by_table"][name]["write_columns"])
    if fz_cols != bd_cols:
        problems.append(f"{name}: freeze projection != bindings write_columns")
    print(
        f"{name}: render OK | proj={len(spec.projection)}列（表达式{len(expr_cols)}） | "
        f"谓词=DATETIME >= :1 AND DATETIME < :2 | ORDER BY ID + ROWNUM<=:3 | params={params}"
    )

print()
if problems:
    print("FAILED:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("ALL OK: 11 tables, plain DATE anchor predicates, no parents,")
print("14 column expressions (13 mismatch + VISIT_DATE NULL) each rendered twice")
print("(nested pagination), all other columns identity,")
print("projection == bindings write_columns (programmatic check).")
print("note: RECIPE_ITEM coverage gap notes 留痕（OR_ID 活源实存 as 正则盲区+VISIT_DATE 真缺口 NULL 投影）；")
print("mask 依据=活源预核（NLS DD-MON-YY 中文月=REFERRAL 全表唯一形态；OPN 六列全 'YYYY-MM-DD HH24:MI:SS'）。")
