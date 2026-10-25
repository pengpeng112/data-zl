"""批5 ADMISSION_RECORD stage att001 质量明细（只读）。"""
import glob
import json
from collections import Counter

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
files = sorted(glob.glob(f"/opt/data-asset/t1-stage/{BID}/att001/*"))
print("files:", [f.split('/')[-1] for f in files])
for f in files:
    if f.endswith(".jsonl"):
        with open(f, encoding="utf-8") as fh:
            first = fh.readline()
        print(f"-- {f.split('/')[-1]} jsonl first200:", first[:200])
        continue
    try:
        data = json.loads(open(f, encoding="utf-8").read())
    except Exception as exc:
        print(f, "err", exc)
        continue
    if isinstance(data, dict):
        print(f"-- {f.split('/')[-1]} keys:", list(data.keys())[:15])
        q = data.get("quality") or {}
        if q:
            print("   quality keys:", list(q.keys()))
            iss = q.get("issues") or data.get("issues")
            if iss:
                c = Counter()
                for i in iss:
                    if isinstance(i, dict):
                        c[(i.get("rule") or i.get("code") or i.get("reason"),
                           i.get("column") or i.get("field") or "")] += 1
                    else:
                        c[str(i)[:100]] += 1
                for k, n in c.most_common(10):
                    print(f"   {n}x {k}")
        for key in ("issues", "groups"):
            if data.get(key):
                print(f"   {key} sample:", str(data[key][:2])[:300])
