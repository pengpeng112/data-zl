import sys
sys.path.insert(0, "/app")
from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config

cfg = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch6_v1.json")
import json
bindings = json.loads(open("/opt/data-asset/t1-config/bindings_batch6.json", encoding="utf-8").read())
for name in sorted(cfg.tables):
    spec = cfg.tables[name]
    wc = spec.write_columns()
    bd = bindings["targets_by_table"][name]
    a = tuple(sorted(bd["write_columns"]))
    b = tuple(sorted(wc))
    same_cols = a == b
    same_key = tuple(spec.stable_key) == tuple(bd["key_columns"])
    st = "SYSTEM_TIME" in bd["write_columns"]
    frozen = (spec.target_instance, spec.tenant, spec.target_table)
    actual = (bd["target_instance"], bd["tenant"], bd["table"])
    print(name, "| cols_eq=", same_cols, "| key_eq=", same_key, "| st_in=", st, "| target_eq=", frozen == actual)
    if not same_cols:
        print("   freeze-only:", sorted(set(b) - set(a))[:8])
        print("   binds-only:", sorted(set(a) - set(b))[:8])
