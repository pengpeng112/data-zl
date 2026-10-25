"""批5 冻结件 v1 本地核验：装载即验 + Oracle 渲染断言（零表达式）+ 投影与 bindings 逐列一致。
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
FREEZE = TASK_DIR / "扩表冻结件_批5_ODS首波_v1_20261025.json"
BINDINGS = TASK_DIR / "扩表bindings_批5_20261025.json"

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
    for token in ("CASE WHEN", "CONVERT(", "TO_DATE(", "NULLIF(", "NULL AS "):
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
print("ALL OK: 8 tables, plain DATE anchor predicates, zero column expressions,")
print("projection == bindings write_columns (programmatic check).")
print("note: EMR_ADMISSION_RECORD ADMISSION_COUNT 覆盖缺口=DDL 隐式别名正则盲区，")
print("活源 ALL_TAB_COLUMNS 已证 gap=NONE（见 生产实况复核与活源列对齐_20261026.out）。")
