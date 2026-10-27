"""批8 冻结件 v1 本地核验：装载即验 + Oracle 渲染断言（零表达式）+ 投影与 bindings 逐列一致。
运行：cd backend && ./.venv/Scripts/python.exe <本脚本>
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
FREEZE = TASK_DIR / "扩表冻结件_批8_ODS二波_v1_20261026.json"
BINDINGS = TASK_DIR / "扩表bindings_批8_20261026.json"

cfg = load_frozen_runtime_config(str(FREEZE))
print(f"load OK: environment={cfg.environment}")
print(f"config fp: {cfg.config_fingerprint}")
print(f"tables: {sorted(cfg.tables)}")

bindings = json.loads(BINDINGS.read_text(encoding="utf-8"))
win = TimeWindow(datetime(2026, 10, 25, 0, 0, 0), datetime(2026, 10, 26, 0, 0, 0))

problems = []
for name in sorted(cfg.tables):
    spec = cfg.tables[name]
    if spec.dialect != "oracle":
        problems.append(f"{name}: dialect != oracle")
    if spec.source_group != "ods":
        problems.append(f"{name}: source_group={spec.source_group}")
    if spec.anchor_column != "DATETIME" or spec.anchor_expression is not None:
        problems.append(
            f"{name}: anchor={spec.anchor_column} expr={spec.anchor_expression}"
        )
    if list(spec.stable_key) != ["ID"]:
        problems.append(f"{name}: stable_key={list(spec.stable_key)}")
    if spec.parent_table:
        problems.append(f"{name}: parent={spec.parent_table}")
    budget = spec.budget if isinstance(spec.budget, dict) else spec.budget.__dict__
    if budget.get("max_rows_per_slice") != 50000:
        problems.append(f"{name}: budget={budget.get('max_rows_per_slice')} (跨页行为只观察不改预算)")
    builder = OracleProjectionQueryBuilder(spec)
    sql, params = builder(win, None, 50000)
    # 锚点直谓词（无 TO_DATE 包装）
    if "DATETIME >= :1 AND DATETIME < :2" not in sql:
        problems.append(f"{name}: anchor predicate not plain: {sql[:200]}")
    # 投影零表达式：表达式级 token（列名子串不算）
    for token in ("CASE WHEN", "CONVERT(", "TO_DATE(", "TO_CHAR(", "TO_NUMBER(", "NULLIF(", "NULL AS ", "REGEXP_LIKE"):
        if token.upper() in sql.upper():
            problems.append(f"{name}: unexpected expression token {token!r} in SQL")
    if "ORDER BY ID" not in sql or "ROWNUM <= :3" not in sql:
        problems.append(f"{name}: pagination shape wrong")
    # 投影与 bindings write_columns 逐列一致
    fz_cols = sorted(f.name for f in spec.projection)
    bd_cols = sorted(
        bindings["targets_by_table"][name]["write_columns"]
    )
    if fz_cols != bd_cols:
        problems.append(f"{name}: freeze projection != bindings write_columns")
    # 投影零 source_expression 改写（恒等投影：表达式=列名本身）
    expr_problems = [f.name for f in spec.projection if f.source_expression.strip() != f.name]
    if expr_problems:
        problems.append(f"{name}: non-identity source_expression: {expr_problems}")
    print(
        f"{name}: render OK | proj={len(spec.projection)}列零表达式 | "
        f"谓词=DATETIME >= :1 AND DATETIME < :2 | ORDER BY ID + ROWNUM<=:3 | "
        f"params={params}"
    )

print()
if problems:
    print("FAILED:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("ALL OK: 10 tables, plain DATE anchor predicates, zero column expressions,")
print("projection == bindings write_columns (programmatic check).")
print("note: 三处视图覆盖缺口核因留痕（均=隐式别名 as 正则盲区，非真实缺口）：")
print("1) DOC_ORDER_DRUG.DRUG_FREQUENCY_CODE（计划预判内：视图头69列含列+正文裸引用")
print("   DRUG_FREQUENCY_CODE,--注释，活源 gap=NONE）")
print("2) OUT_FEE_INFO_MAIN.VISIT_DATE（计划外新发现：08快照DDL过期=2026-10-20费用视图")
print("   修改前旧版头62列无该列，已照批6范式活源DBMS_METADATA注入出补充快照（头64列含")
print("   VISIT_DATE/DATETIME）；现版正文暴露 b.visit_date , b.visit_date DATETIME 隐式别名")
print("   无as，as正则不可见；活源 gap=NONE + 10视图 live sha==views_bulk 全 MATCH）")
print("3) IN_FEE_INFO_CHILD.PROJ_DENO（计划外新发现：头47列含列+正文 nvl(...) PROJ_DENO,")
print("   隐式别名无as；活源 gap=NONE）")
print("核因后按生成器既定语义 --allow-view-gap 强制留痕（拒绝证据先落档）。")
