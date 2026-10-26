"""批7 配置卷容器装载即验：load_frozen_runtime_config 打印 environment/fingerprint/11 表
+ 锚点直谓词/无父子断言 + 14 表达式列断言（v2）。
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b7_load_verify.py
"""
import sys

sys.path.insert(0, "/app")

from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config

V2_FP = "d2f708a4004b60f44d53415e5dbde3d3d62429ba88d579d6f6bfc8f2654c3fed"
EXPR_COUNT = {"EMR_OPERATION_NURSING": 6, "EMR_HOS_PREOP_DISCUSS": 3,
              "EMR_REFERRAL_HOS_RECORD": 1, "EMR_ADMISSION_DEAD_RECORD_TF": 1,
              "EMR_AFTER_OPERA_RECORD": 1, "EMR_INFOR_ANESTHESIA": 1,
              "EMR_OUTPATIENT_RECIPE_ITEM": 1}

cfg = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch7_v2.json")
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
    want = EXPR_COUNT.get(name, 0)
    if not (plain and no_parent and spec.source_group == "ods" and exprs == want):
        ok = False
        print(f"ASSERT_FAIL {name}: anchor={spec.anchor_column} expr={spec.anchor_expression} "
              f"parent={spec.parent_table} group={spec.source_group} exprs={exprs}/{want}")
    else:
        print(f"{name}: OK exprs={exprs}")
print("anchor_plain_no_parent_expr_count_all_11:", ok)
assert cfg.environment == "production"
assert cfg.config_fingerprint == V2_FP
assert len(tables) == 11
print("fingerprint_match_local: True")
