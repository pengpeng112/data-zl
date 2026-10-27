"""批8 配置卷容器装载即验：load_frozen_runtime_config 打印 environment/fingerprint/10 表
+ 锚点直谓词/无父子/零表达式断言 + bindings 容器内比对（write_columns/key/target vs 冻结件投影）。
运行：ssh -F .ssh/config_ai data-asset-83 "docker exec -i data-asset-api python -" < b8_load_verify.py
"""
import json
import sys

sys.path.insert(0, "/app")

from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config

V1_FP = "f09d6b0ae74c697acad3ba830b8adae3e886c5c7a40ae01d9c602581749035a0"

cfg = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch8_v1.json")
print("environment:", cfg.environment)
print("config_fingerprint:", cfg.config_fingerprint)
tables = sorted(cfg.tables)
print("tables:", tables)
ok = True
for name in tables:
    spec = cfg.tables[name]
    plain = spec.anchor_column == "DATETIME" and spec.anchor_expression is None
    no_parent = not spec.parent_table
    exprs = sum(1 for f in spec.projection if f.source_expression.strip() != f.name)
    budget = spec.budget if isinstance(spec.budget, dict) else spec.budget.__dict__
    if not (plain and no_parent and spec.source_group == "ods" and exprs == 0
            and budget.get("max_rows_per_slice") == 50000):
        ok = False
        print(f"ASSERT_FAIL {name}: anchor={spec.anchor_column} expr={spec.anchor_expression} "
              f"parent={spec.parent_table} group={spec.source_group} exprs={exprs} budget={budget}")
    else:
        print(f"{name}: OK proj={len(spec.projection)} exprs=0 budget=50000")
print("anchor_plain_no_parent_zero_expr_all_10:", ok)
assert cfg.environment == "production"
assert cfg.config_fingerprint == V1_FP, "指纹漂移！"
assert len(tables) == 10
print("fingerprint_match_local: True")

# bindings 容器内比对（批6 笔误教训：cols/key/target 与冻结件投影比对）
bd = json.load(open("/opt/data-asset/t1-config/bindings_batch8.json", encoding="utf-8"))
print()
print("== bindings 容器内比对 ==")
all_ok = True
for name in tables:
    spec = cfg.tables[name]
    fz_cols = sorted(f.name for f in spec.projection)
    tb = bd["targets_by_table"][name]
    checks = {
        "write_columns": sorted(tb["write_columns"]) == fz_cols,
        "key_columns": tb["key_columns"] == ["ID"],
        "table": tb["table"] == f"DBOPER.{name}",
        "tenant": tb["tenant"] == "DBOPER",
        "target_instance": tb["target_instance"] == "10.10.8.74:1521/orcl",
    }
    ab = [a for a in bd["action_bindings"] if a["canonical_table"] == name]
    checks["approval_ref"] = len(ab) == 1 and ab[0]["approval_ref"] == f"T1-EXPAND-B8-20261026:{name.lower()}"
    if all(checks.values()):
        print(f"{name}: 6/6 OK")
    else:
        all_ok = False
        print(f"{name}: FAIL {checks}")
assert len(bd["action_bindings"]) == 10 and all_ok
print("bindings_10表比对全绿: True")
print("executor:", bd["executor_id"], "| receipt:", bd["receipt_table"])
