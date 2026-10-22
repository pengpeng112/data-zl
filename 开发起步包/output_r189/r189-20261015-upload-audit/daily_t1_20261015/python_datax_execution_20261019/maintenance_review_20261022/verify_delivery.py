"""Check delivered links, recorded code hashes and status pointers offline."""
import hashlib
import json
import re
from pathlib import Path

root = Path.cwd()
audit = Path(__file__).resolve().parent
record = json.loads((audit / "验收记录.json").read_text(encoding="utf-8"))
for name, expected in record["code_sha256"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
for file in (audit / "T加1维护复核与修复说明.md", root / "deploy/reporting_pipeline/系统抽取与维护说明.md"):
    for reference in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        if reference.startswith(("http:", "https:", "#")):
            continue
        assert (file.parent / reference.split("#", 1)[0]).resolve().exists(), (file.name, reference)
run = root / "开发起步包/output_r189/r189-20261015-upload-audit"
checkpoint = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
daily = checkpoint["daily_t1"]
assert (run / daily["current_status_ref"]).exists()
assert (run / daily["current_review_ref"]).exists()
assert record["unit_tests"]["passed"] == 444
assert record["production"]["writes"] == 0
print("PASS: delivered links, code hashes, original status/checkpoint pointers")
