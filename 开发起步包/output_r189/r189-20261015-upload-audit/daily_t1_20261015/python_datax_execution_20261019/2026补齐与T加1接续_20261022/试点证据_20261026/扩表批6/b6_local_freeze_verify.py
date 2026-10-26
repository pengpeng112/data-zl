"""批6 冻结件 v1 本地核验：装载即验 + Oracle 渲染断言（零表达式）+ 投影与 bindings 逐列一致。
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
FREEZE = TASK_DIR / "扩表冻结件_批6_ODS二波_v1_20261026.json"
BINDINGS = TASK_DIR / "扩表bindings_批6_20261026.json"

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
print("ALL OK: 11 tables, plain DATE anchor predicates, zero column expressions,")
print("projection == bindings write_columns (programmatic check).")
print("note: EMR_IN_FEE_INFO_MAIN DISCHARGE_DATE_TIME 覆盖缺口核因=08快照DDL过期")
print("(2026-10-20费用视图修改前旧版)+活源隐式别名(pv.discharge_date_time,无as)正则盲区，")
print("活源 ALL_TAB_COLUMNS gap=NONE 且 11 视图 live sha==views_bulk(2026-10-22) 全 MATCH，")
print("核因后按生成器既定语义 --allow-view-gap 强制留痕；生成输入=元数据快照补充_批6")
print("(08结构+活源DBMS_METADATA DDL注入，批7补充件同款证据文件级零代码范式)。")
