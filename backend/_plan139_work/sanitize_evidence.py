"""Sanitize string literals in stored definitions per plan139 S3/section 3.

Runs on 10.10.8.83 against this run's raw snapshots. For every view the
original definition SHA-256 is computed FIRST and stored in
``definition_sha256_original.json``; then quoted literals in view/trigger/
routine definitions are masked in place. Original texts never persist.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

VIEW_KEY_TEMPLATE = "{db}.{name}"
LITERAL_RE = re.compile(r"'(?:''|[^'])*'")


def redact(text):
    return LITERAL_RE.sub("'[REDACTED]'", str(text))


def process(path: Path, sha_all: dict) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    report = {"file": path.name, "views": 0, "triggers": 0, "routines": 0}
    for row in data.get("views", []):
        definition = row.get("view_definition")
        if definition in (None, ""):
            continue
        key = "{}.{}".format(row.get("database_name"), row.get("view_name"))
        sha_all[key] = hashlib.sha256(str(definition).encode("utf-8")).hexdigest()
        row["view_definition"] = redact(definition)
        report["views"] += 1
    for row in data.get("triggers", []):
        definition = row.get("trigger_definition")
        if definition in (None, ""):
            continue
        row["trigger_definition"] = redact(definition)
        report["triggers"] += 1
    for row in data.get("routines", []):
        definition = row.get("routine_definition")
        if definition in (None, ""):
            continue
        row["routine_definition"] = redact(definition)
        report["routines"] += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    evidence = Path(sys.argv[1])
    sha_all: dict = {}
    for name in sys.argv[2:]:
        print(json.dumps(process(evidence / name, sha_all), ensure_ascii=False))
    (evidence / "raw" / "definition_sha256_original.json").write_text(
        json.dumps(sha_all, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({"definition_sha256_map": len(sha_all)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
