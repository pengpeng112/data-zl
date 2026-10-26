"""批6 配置卷容器装载即验：load_frozen_runtime_config 打印 environment/fingerprint/11 表
+ 锚点直谓词/无父子断言；随后容器外由 shell 列配置卷时间戳（批1/2/4/5/首组未动）。
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b6_load_verify.py
"""
import sys

sys.path.insert(0, "/app")

from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config

cfg = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch6_v1.json")
print("environment:", cfg.environment)
print("config_fingerprint:", cfg.config_fingerprint)
tables = sorted(cfg.tables)
print("tables:", tables)
ok = True
for name in tables:
    spec = cfg.tables[name]
    plain = spec.anchor_column == "DATETIME" and spec.anchor_expression is None
    no_parent = not spec.parent_table
    if not (plain and no_parent and spec.source_group == "ods"):
        ok = False
        print(f"ASSERT_FAIL {name}: anchor={spec.anchor_column} expr={spec.anchor_expression} "
              f"parent={spec.parent_table} group={spec.source_group}")
print("anchor_plain_and_no_parent_all_11:", ok)
assert cfg.environment == "production"
assert cfg.config_fingerprint == "776a394e7ab68317acbec45924fbe48ec3c4f6667d8b56d902acbe23d8f69900"
assert len(tables) == 11
print("fingerprint_match_local: True")
