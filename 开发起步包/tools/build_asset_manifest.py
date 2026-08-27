# -*- coding: utf-8 -*-
"""144 S9: 通用资产包 manifest 生成与验证工具。

用法:
  python 开发起步包/tools/build_asset_manifest.py 开发起步包/数据资产_资产包
  python 开得起步包/tools/build_asset_manifest.py <dir> --verify   # 校验既有 manifest

manifest.json 契约（144 §11.1）:
- schema_version / asset_version / generated_at / data_as_of
- 每个文件的角色（summary/full/candidate/evidence）、行数、SHA-256、编码
- catalog.json 明确标注"摘要非全量"，外部 AI 不得当全量清单
- PII/凭据扫描结论（文件名与内容抽样关键字）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "asset-manifest/v1"
BUILDER_VERSION = "build_asset_manifest/1"

# 文件角色映射：后缀/名称 → role
ROLE_RULES = [
    ("manifest.json", "manifest"),
    ("catalog.json", "summary"),
    ("import_result", "evidence"),
    ("validation", "evidence"),
    ("candidates", "candidate"),
    ("_draft", "candidate"),
]

PII_PATTERNS = [
    (re.compile(r"\b\d{17}[\dXx]\b"), "possible_id_card"),
    (re.compile(r"\b1[3-9]\d{9}\b"), "possible_phone"),
    (re.compile(r"(?i)(password|passwd|token)\s*[:=]\s*\S+"), "possible_credential"),
]


def detect_role(name: str) -> str:
    lower = name.lower()
    for key, role in ROLE_RULES:
        if key in lower:
            return role
    if lower.endswith((".csv",)) and any(
        k in lower for k in ("columns", "tables", "objects", "relationships", "constraints", "indexes")
    ):
        return "full"
    return "evidence"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int | None:
    if path.suffix.lower() == ".csv":
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                return max(sum(1 for _ in csv.reader(f)) - 1, 0)
        except Exception:
            return None
    if path.suffix.lower() == ".json":
        try:
            data = json.load(open(path, encoding="utf-8"))
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                for key in ("tables", "columns", "relationships", "items", "objects"):
                    if isinstance(data.get(key), list):
                        return len(data[key])
                return 1
        except Exception:
            return None
    return None


def scan_pii(path: Path, sample_bytes: int = 1 << 22) -> list[str]:
    hits: set[str] = set()
    try:
        blob = open(path, "rb").read(sample_bytes).decode("utf-8", errors="ignore")
    except Exception:
        return []
    for pattern, label in PII_PATTERNS:
        if pattern.search(blob):
            hits.add(label)
    return sorted(hits)


def build_manifest(pkg_dir: Path) -> dict:
    files = []
    total_pii: set[str] = set()
    for path in sorted(pkg_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        rel = path.relative_to(pkg_dir).as_posix()
        pii = scan_pii(path)
        total_pii.update(pii)
        files.append(
            {
                "path": rel,
                "role": detect_role(rel),
                "bytes": path.stat().st_size,
                "rows": count_rows(path),
                "sha256": sha256_file(path),
                "pii_scan": pii,
            }
        )
    catalog_path = pkg_dir / "catalog.json"
    catalog_summary = None
    if catalog_path.exists():
        try:
            cat = json.load(open(catalog_path, encoding="utf-8"))
            catalog_summary = {
                "note": "catalog.json 是核心摘要，不是全量清单；全量见 role=full 的 CSV",
                "top_keys": sorted(cat.keys())[:12] if isinstance(cat, dict) else [],
            }
        except Exception:
            catalog_summary = {"note": "catalog.json 不可解析"}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "asset_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "builder_version": BUILDER_VERSION,
        "package": pkg_dir.name,
        "file_count": len(files),
        "files": files,
        "catalog_summary": catalog_summary,
        "pii_scan_conclusion": {
            "hits": sorted(total_pii),
            "clean": not total_pii,
            "note": "仅模式抽样扫描（前 4MB/文件）；不含凭据原文，命中不代表泄露，需人工确认",
        },
    }
    return manifest


def verify_manifest(pkg_dir: Path) -> int:
    manifest_path = pkg_dir / "manifest.json"
    if not manifest_path.exists():
        print("FAIL: manifest.json 不存在")
        return 2
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    failures = []
    for entry in manifest.get("files", []):
        path = pkg_dir / entry["path"]
        if not path.exists():
            failures.append(f"missing: {entry['path']}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != entry["sha256"]:
            failures.append(f"hash_mismatch: {entry['path']}")
        actual_rows = count_rows(path)
        if entry.get("rows") is not None and actual_rows != entry["rows"]:
            failures.append(f"rows_mismatch: {entry['path']} manifest={entry['rows']} actual={actual_rows}")
    ok = not failures
    print(json.dumps({"ok": ok, "checked": len(manifest.get("files", [])), "failures": failures[:50]}, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pkg_dir")
    ap.add_argument("--verify", action="store_true", help="校验既有 manifest 与文件一致")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    pkg = Path(args.pkg_dir)
    if not pkg.is_dir():
        print(f"FAIL: 目录不存在 {pkg}")
        return 2
    if args.verify:
        return verify_manifest(pkg)
    manifest = build_manifest(pkg)
    out = pkg / "manifest.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    if not args.quiet:
        print(
            f"manifest_ok files={manifest['file_count']} pii_hits={manifest['pii_scan_conclusion']['hits']} -> {out}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
