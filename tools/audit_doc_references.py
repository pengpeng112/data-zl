#!/usr/bin/env python3
"""Read-only reference inventory for numbered documents and companion assets.

Outputs paths, line numbers and match kinds only; never source snippets. This
inventory does not decide archive eligibility or replace README/55. Private,
patient-export and generated domains are excluded explicitly; no symlink is
followed and large text is recorded as uninspected. No database or Git writes.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TEXT_SUFFIXES = {".md", ".py", ".json", ".csv", ".sql", ".ts", ".tsx", ".vue", ".js",
                 ".mjs", ".cjs", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
                 ".sh", ".bat", ".cmd", ".ps1", ".txt"}
EXCLUDED_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
                  ".mypy_cache", ".cache", ".ssh", ".zcode", ".v2c", ".video_agent",
                  ".workbuddy", "backups", ".history", ".idea", ".vscode"}
EXCLUDED_PREFIXES = {"取数", "_scratch", "artifacts", "frontend/dist", "frontend/coverage",
                     "backend/ds_export_artifacts", "backend/static", ".agents/collaboration",
                     "开发起步包/output_r204", "开发起步包/docs"}
NUMBER = re.compile(r"^(\d+)_")
FAMILY_ALIAS = re.compile(r"(?<![\w])(?P<num>\d{2,3})_(?:\*|…|\.\.\.)")
OUTPUT_ALIAS = re.compile(r"(?<![\w])output_r(?P<num>\d+)(?![\w])")
UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def targets_for(root: Path) -> list[dict]:
    kb = root / "开发起步包"
    targets = []
    for path in sorted(kb.iterdir()):
        if path.is_symlink():
            continue
        number = NUMBER.match(path.name)
        if path.is_file() and number and path.suffix in TEXT_SUFFIXES:
            kind = "body" if path.suffix == ".md" and "执行报告" not in path.name else "companion"
        elif path.is_dir() and re.fullmatch(r"output_r\d+", path.name):
            number = re.search(r"(\d+)$", path.name)
            kind = "run_directory"
        elif path.is_dir() and path.name.startswith("数据资产_"):
            kind = "machine_asset_directory"
        else:
            continue
        targets.append({"path": path.relative_to(root).as_posix(), "name": path.name,
                        "family": int(number.group(1)) if number else None, "kind": kind})
    return targets


def excluded(relative: str) -> bool:
    parts = relative.split("/")
    return (any(part in EXCLUDED_NAMES for part in parts)
            or any(part.startswith("数据资产_") for part in parts)
            or any(relative == prefix or relative.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES))


def inventory(root: Path, max_bytes: int = 1024 * 1024) -> dict:
    root = root.resolve(strict=True)
    targets = targets_for(root)
    by_name = {item["name"]: item for item in targets}
    pattern = re.compile("|".join(re.escape(name) for name in sorted(by_name, key=len, reverse=True))) if by_name else None
    refs, aliases, skipped = [], [], []
    scanned = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        kept = []
        for name in sorted(dirs):
            candidate = current / name
            relative = candidate.relative_to(root).as_posix()
            if candidate.is_symlink() or not inside(candidate.resolve(), root):
                skipped.append({"path": relative, "reason": "symlink_or_outside"})
            elif excluded(relative):
                skipped.append({"path": relative, "reason": "excluded_domain"})
            else:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(files):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if excluded(relative) or name.startswith(".env") or name in {"credentials.json", "credentials.yml"}:
                continue
            if path.is_symlink() or not inside(path.resolve(), root):
                skipped.append({"path": relative, "reason": "symlink_or_outside"})
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            size = path.stat().st_size
            # Reports/code/config are inspected; bulk rows are data, not a
            # safe substitute for checking their producer and manifest.
            file_budget = min(max_bytes, 256 * 1024) if path.suffix.lower() in {".json", ".csv"} else max_bytes
            if size > file_budget:
                skipped.append({"path": relative, "reason": "text_size_budget", "bytes": size})
                continue
            try:
                with path.open(encoding="utf-8-sig", errors="strict") as stream:
                    local_refs, local_aliases = [], []
                    for line_number, line in enumerate(stream, 1):
                        # Interpret JSON Unicode escapes without printing/retaining values.
                        if path.suffix.lower() == ".json":
                            line = UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), line)
                        if pattern:
                            for match in pattern.finditer(line):
                                target = by_name[match.group()]
                                # Directory literal needs a right boundary to avoid output_r20 matching output_r200.
                                if target["kind"].endswith("directory") and match.end() < len(line) and re.match(r"[\w]", line[match.end()]):
                                    continue
                                local_refs.append({"target": target["path"], "referrer": relative,
                                                   "line": line_number, "match_kind": "literal_name"})
                        for match in FAMILY_ALIAS.finditer(line):
                            local_aliases.append({"family": int(match["num"]), "referrer": relative,
                                                  "line": line_number, "match_kind": "family_wildcard"})
                        for match in OUTPUT_ALIAS.finditer(line):
                            local_aliases.append({"family": int(match["num"]), "referrer": relative,
                                                  "line": line_number, "match_kind": "output_family"})
                refs.extend(local_refs)
                aliases.extend(local_aliases)
                scanned += 1
                if scanned % 500 == 0:
                    print(f"reference scan: {scanned} text files inspected", flush=True)
            except (UnicodeError, OSError):
                skipped.append({"path": relative, "reason": "unreadable_utf8"})
    counts = Counter(item["target"] for item in refs)
    for item in targets:
        item["literal_reference_count"] = counts[item["path"]]
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "contract": {"authority": "README/55; this is an evidence inventory",
                         "max_text_bytes": max_bytes, "no_snippets": True,
                         "json_csv_max_bytes": min(max_bytes, 256 * 1024),
                         "machine_asset_contents": "excluded; inspect producers and manifests separately",
                         "limitations": "literal names and explicit family wildcards only; dynamic paths and private consumers require review",
                         "excluded_prefixes": sorted(EXCLUDED_PREFIXES), "excluded_directory_names": sorted(EXCLUDED_NAMES)},
            "scanned_files": scanned, "targets": targets, "references": refs,
            "family_aliases": aliases, "uninspected": skipped}


def write_inventory(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "reference_inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    with (output / "reference_inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["target", "referrer", "line", "match_kind"])
        writer.writeheader()
        writer.writerows(result["references"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-text-mib", type=int, default=1)
    args = parser.parse_args()
    root = args.repo.resolve(strict=True)
    output = args.output.resolve()
    if not 1 <= args.max_text_mib <= 64 or not inside(output, root) or output == root:
        parser.error("output must be a task directory inside the repository; text budget 1..64 MiB")
    result = inventory(root, args.max_text_mib * 1024 * 1024)
    write_inventory(result, output)
    print(json.dumps({"scanned_files": result["scanned_files"], "targets": len(result["targets"]),
                      "references": len(result["references"]), "uninspected": len(result["uninspected"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
