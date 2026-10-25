"""批5 用 v3 spec 的 nullable 重扫被隔离行（只读）。"""
import json

from app.services.reporting_pipeline.runtime_config import load_frozen_runtime_config

cfg = load_frozen_runtime_config("/opt/data-asset/t1-config/freeze_batch5_v3.json")
spec = cfg.tables["EMR_ADMISSION_RECORD"]
not_null = [f.name for f in spec.projection if not getattr(f, "nullable", True)]
keys = list(spec.stable_key)
print("spec not_null 列数:", len(not_null), "| stable_key:", keys)

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
from app.services.reporting_pipeline.durable_staging import _decode_json_row
import os
rows = []
base = f"/opt/data-asset/t1-stage/{BID}"
for att in sorted(os.listdir(base)):
    d = f"{base}/{att}"
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        if fn.startswith("chunk-") and fn.endswith(".bin"):
            with open(f"{d}/{fn}", "rb") as fh:
                for line in fh:
                    if line.strip():
                        rows.append(_decode_json_row(line))
print("staged rows:", len(rows))
for r in rows:
    missing = [c for c in not_null if r.get(c) is None or r.get(c) == ""]
    keymiss = [k for k in keys if r.get(k) is None or r.get(k) == ""]
    if missing or keymiss:
        print("违规行 ID=", r.get("ID"), "| NOT NULL 缺失:", missing, "| 键缺失:", keymiss)
from collections import Counter
c = Counter(r.get("ID") for r in rows)
dups = {k: n for k, n in c.items() if n > 1}
print("重复键:", dups if dups else "无")
print("== 扫描结束 ==")
