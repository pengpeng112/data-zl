import sys
sys.path.insert(0, "/app")
from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config
import json

cfg = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch6_v1.json")
spec = cfg.tables["EMR_INFOR_TRANS_BLOOD"]
print("stable_key repr:", repr(spec.stable_key))
print("write_columns()[:5]:", spec.write_columns()[:5], "count:", len(spec.write_columns()))
bindings = json.loads(open("/opt/data-asset/t1-config/bindings_batch6.json", encoding="utf-8").read())
bd = bindings["targets_by_table"]["EMR_INFOR_TRANS_BLOOD"]
print("bd key_columns repr:", repr(bd["key_columns"]))
# 对比批5 生产件（同生成路径）如何表达
b5 = json.loads(open("/opt/data-asset/t1-config/bindings_batch5.json", encoding="utf-8").read())
print("b5 key_columns sample:", repr(b5["targets_by_table"]["EMR_ADMISSION_DIAGNOSIS"]["key_columns"]))
cfg5 = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch5_v3.json")
print("b5 freeze stable_key repr:", repr(cfg5.tables["EMR_ADMISSION_DIAGNOSIS"].stable_key))
