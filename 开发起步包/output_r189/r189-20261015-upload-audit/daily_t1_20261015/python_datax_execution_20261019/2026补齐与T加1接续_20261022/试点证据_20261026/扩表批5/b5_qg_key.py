"""批5 ADMISSION_RECORD 解码暂存行找被隔离键与缺失列（只读）。"""
import sys


BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
import json
NOTNULL = set(json.loads(open("/tmp/b5_nn.json").read()))
from app.services.reporting_pipeline.durable_staging import _decode_json_row
rows = []
for att in __import__("os").listdir(f"/opt/data-asset/t1-stage/{BID}"):
    d = f"/opt/data-asset/t1-stage/{BID}/{att}"
    if not __import__("os").path.isdir(d):
        continue
    for fn in sorted(__import__("os").listdir(d)):
        if fn.startswith("chunk-") and fn.endswith(".bin"):
            with open(f"{d}/{fn}", "rb") as fh:
                for line in fh:
                    if line.strip():
                        rows.append(_decode_json_row(line))
print("staged rows:", len(rows))
bad = []
for r in rows:
    missing = [c for c in sorted(NOTNULL) if r.get(c) is None or r.get(c) == ""]
    if missing:
        bad.append((r.get("ID"), missing))
print("缺 NOT NULL 行:", bad if bad else "无")
# 另查值类型分布（BED_CODE/SICKBED_NUM 应全 str）
types = {}
for r in rows:
    for c in ("BED_CODE", "SICKBED_NUM"):
        types.setdefault(c, set()).add(type(r.get(c)).__name__)
print("类型:", {k: sorted(v) for k, v in types.items()})
