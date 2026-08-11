"""Generate manifest.json and SHA256SUMS for a complete offline package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


CONTROL_FILES = {"manifest.json", "SHA256SUMS"}
CONTROL_FILES_CASEFOLDED = {name.casefold() for name in CONTROL_FILES}
SOURCE_REVISION_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def collect_payload(package_dir: Path) -> list[dict[str, str]]:
    root = package_dir.resolve()
    if not root.is_dir():
        raise ValueError(f"package directory does not exist: {root}")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = candidate.relative_to(root).as_posix()
        if _is_link(candidate):
            raise ValueError(f"package contains a symlink or junction: {relative}")
        if relative.casefold() in CONTROL_FILES_CASEFOLDED:
            if relative not in CONTROL_FILES:
                raise ValueError(f"case-conflicting control file: {relative}")
            continue
        if not candidate.is_file():
            continue
        folded = relative.casefold()
        if folded in seen:
            raise ValueError(f"case-insensitive duplicate path: {relative}")
        seen.add(folded)
        entries.append({"path": relative, "sha256": _sha256(candidate)})
    if not entries:
        raise ValueError("package contains no payload files")
    return entries


def build_manifest(
    package_dir: Path,
    *,
    python_version: str,
    os_name: str,
    architecture: str,
    source_revision: str,
    source_tree_state: str = "dirty",
    created_at: str | None = None,
) -> tuple[Path, Path, int]:
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", python_version):
        raise ValueError(f"invalid Python version: {python_version}")
    os_name = os_name.lower()
    if os_name != "linux":
        raise ValueError(f"unsupported target OS: {os_name}")
    architecture = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(
        architecture.lower(), architecture.lower()
    )
    if architecture not in {"x86_64", "aarch64"}:
        raise ValueError(f"unsupported target architecture: {architecture}")
    if not SOURCE_REVISION_RE.fullmatch(source_revision):
        raise ValueError("source revision must be a 7-64 character hexadecimal Git revision")
    if source_tree_state not in {"clean", "dirty"}:
        raise ValueError("source tree state must be clean or dirty")

    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if created_at is not None and source_date_epoch:
        raise ValueError("created_at and SOURCE_DATE_EPOCH cannot both be set")
    if source_date_epoch:
        try:
            build_time = datetime.fromtimestamp(int(source_date_epoch), timezone.utc)
        except (ValueError, OSError) as exc:
            raise ValueError("SOURCE_DATE_EPOCH must be a valid Unix timestamp") from exc
        created_at = build_time.isoformat()
    elif created_at is not None:
        try:
            build_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO-8601 timestamp") from exc
        if build_time.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        created_at = build_time.astimezone(timezone.utc).isoformat()

    package_dir = package_dir.resolve()
    entries = collect_payload(package_dir)
    manifest = {
        "format_version": 1,
        "target": {
            "python_version": python_version,
            "os": os_name,
            "arch": architecture,
        },
        "source_revision": source_revision,
        "source_tree_state": source_tree_state,
        "files": entries,
    }
    if created_at is not None:
        manifest["created_at"] = created_at
    manifest_path = package_dir / "manifest.json"
    sums_path = package_dir / "SHA256SUMS"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sums_path.write_text(
        "".join(f"{entry['sha256']} *{entry['path']}\n" for entry in entries),
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path, sums_path, len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--os", default="linux")
    parser.add_argument("--arch", default="x86_64")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-state", choices=["clean", "dirty"], required=True)
    parser.add_argument(
        "--created-at",
        help="fixed ISO-8601 timestamp; omit for deterministic output without a build timestamp",
    )
    args = parser.parse_args()
    _manifest, _sums, count = build_manifest(
        args.package_dir,
        python_version=args.python_version,
        os_name=args.os,
        architecture=args.arch,
        source_revision=args.source_revision,
        source_tree_state=args.source_tree_state,
        created_at=args.created_at,
    )
    print(f"OFFLINE_MANIFEST_OK files={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
