#!/usr/bin/env python3
"""Fail-closed integrity and target-runtime checks for an offline package."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class PackageValidationError(ValueError):
    """Raised when an offline package is unsafe or incomplete."""


def _safe_path(raw: Any) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise PackageValidationError(f"invalid path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise PackageValidationError(f"absolute path is not allowed: {raw!r}")
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PackageValidationError(f"path traversal or ambiguous path: {raw!r}")
    return "/".join(parts)


def _entries(value: Any, source: str) -> dict[str, str]:
    if isinstance(value, dict):
        items = [{"path": key, "sha256": digest} for key, digest in value.items()]
    elif isinstance(value, list):
        items = value
    else:
        raise PackageValidationError(f"{source} files must be a list or object")
    result: dict[str, str] = {}
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise PackageValidationError(f"{source} contains a non-object entry")
        path = _safe_path(item.get("path"))
        key = path.casefold()
        if key in seen:
            raise PackageValidationError(f"duplicate file entry: {path}")
        digest = item.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise PackageValidationError(f"invalid SHA-256 for {path}")
        seen.add(key)
        result[path] = digest.lower()
    return result


def parse_sha256sums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PackageValidationError(f"cannot read SHA256SUMS: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*([0-9a-fA-F]{64})\s+[ *](.+?)\s*", line)
        if not match:
            raise PackageValidationError(f"invalid SHA256SUMS line {line_number}")
        digest, raw_path = match.groups()
        file_path = _safe_path(raw_path)
        key = file_path.casefold()
        if key in seen:
            raise PackageValidationError(f"duplicate SHA256SUMS entry: {file_path}")
        seen.add(key)
        result[file_path] = digest.lower()
    if not result:
        raise PackageValidationError("SHA256SUMS contains no file entries")
    return result


def _declared(manifest: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in manifest:
            return manifest[name]
    targets = manifest.get("target")
    if isinstance(targets, dict):
        for name in names:
            if name in targets:
                return targets[name]
    return None


def _check_runtime(manifest: dict[str, Any]) -> None:
    declared_python = _declared(manifest, "python_version", "python")
    if isinstance(declared_python, dict):
        declared_python = declared_python.get("version")
    if declared_python is None:
        raise PackageValidationError("target Python version is required")
    expected = str(declared_python)
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    if expected not in (actual, f"{actual}.{sys.version_info.micro}"):
        raise PackageValidationError(f"Python version mismatch: package={expected}, runtime={actual}")

    declared_os = _declared(manifest, "os", "platform")
    if isinstance(declared_os, dict):
        declared_os = declared_os.get("os") or declared_os.get("name")
    if declared_os is None:
        raise PackageValidationError("target OS is required")
    expected = str(declared_os).lower()
    actual = platform.system().lower()
    aliases = {"linux": "linux", "gnu/linux": "linux", "windows": "windows", "win": "windows", "darwin": "darwin", "macos": "darwin"}
    if aliases.get(expected, expected) != actual:
        raise PackageValidationError(f"OS mismatch: package={declared_os}, runtime={platform.system()}")

    declared_arch = _declared(manifest, "architecture", "arch")
    if isinstance(declared_arch, dict):
        declared_arch = declared_arch.get("architecture") or declared_arch.get("arch")
    if declared_arch is None:
        raise PackageValidationError("target architecture is required")
    aliases = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
    expected = aliases.get(str(declared_arch).lower(), str(declared_arch).lower())
    actual = aliases.get(platform.machine().lower(), platform.machine().lower())
    if expected != actual:
        raise PackageValidationError(f"architecture mismatch: package={declared_arch}, runtime={platform.machine()}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _python_tag_compatible(python_tag: str, abi_tag: str) -> bool:
    major, minor = sys.version_info[:2]
    if match := re.fullmatch(r"py(\d)(\d+)?", python_tag):
        tag_major = int(match.group(1))
        tag_minor = int(match.group(2)) if match.group(2) else None
        return abi_tag == "none" and tag_major == major and (tag_minor is None or tag_minor == minor)
    if match := re.fullmatch(r"cp(\d)(\d+)", python_tag):
        tag_major = int(match.group(1))
        tag_minor = int(match.group(2))
        if tag_major != major:
            return False
        if abi_tag == "abi3":
            return tag_minor <= minor
        return tag_minor == minor and abi_tag in {f"cp{major}{minor}", "none"}
    return False


def _platform_tag_compatible(platform_tag: str) -> bool:
    if platform_tag == "any":
        return True
    if platform.system().lower() != "linux" or platform_tag.startswith("musllinux"):
        return False
    arch = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    if not platform_tag.endswith(f"_{arch}"):
        return False
    if platform_tag == f"linux_{arch}":
        return True
    required_glibc = {
        f"manylinux1_{arch}": (2, 5),
        f"manylinux2010_{arch}": (2, 12),
        f"manylinux2014_{arch}": (2, 17),
    }.get(platform_tag)
    if required_glibc is None:
        match = re.fullmatch(rf"manylinux_(\d+)_(\d+)_{re.escape(arch)}", platform_tag)
        if not match:
            return False
        required_glibc = (int(match.group(1)), int(match.group(2)))
    libc_name, libc_version = platform.libc_ver()
    if libc_name.lower() != "glibc" or not re.fullmatch(r"\d+(?:\.\d+)+", libc_version):
        return False
    actual_glibc = tuple(int(part) for part in libc_version.split(".")[:2])
    return actual_glibc >= required_glibc


def _wheel_is_compatible(wheel_name: str) -> bool:
    if not wheel_name.endswith(".whl"):
        raise PackageValidationError(f"invalid wheel filename: {wheel_name}")
    parts = wheel_name[:-4].rsplit("-", 3)
    if len(parts) != 4 or not parts[0]:
        raise PackageValidationError(f"invalid wheel filename: {wheel_name}")
    _prefix, python_tags_raw, abi_tags_raw, platform_tags_raw = parts
    python_tags = python_tags_raw.split(".")
    abi_tags = abi_tags_raw.split(".")
    platform_tags = platform_tags_raw.split(".")
    return any(
        _python_tag_compatible(python_tag, abi_tag) and _platform_tag_compatible(platform_tag)
        for python_tag in python_tags
        for abi_tag in abi_tags
        for platform_tag in platform_tags
    )


def _check_r8_profile(package_dir: Path, manifest_entries: dict[str, str]) -> None:
    required = {
        "backend/requirements.lock",
        "frontend/dist/index.html",
        "deploy/offline/README.md",
    }
    missing = sorted(required - set(manifest_entries))
    if missing:
        raise PackageValidationError(f"R8 package is missing required files: {', '.join(missing)}")
    if not any(path.startswith("pnpm-store/") for path in manifest_entries):
        raise PackageValidationError("R8 package is missing the pnpm offline store")
    if not any(re.fullmatch(r"pnpm-[^/]+\.tgz", path) for path in manifest_entries):
        raise PackageValidationError("R8 package is missing the offline pnpm CLI tarball")

    wheel_paths = sorted(path for path in manifest_entries if path.startswith("wheels/") and path.endswith(".whl"))
    if not wheel_paths:
        raise PackageValidationError("R8 package contains no wheels")
    wheel_hashes: set[str] = set()
    for relative in wheel_paths:
        wheel = package_dir / Path(*relative.split("/"))
        if not _wheel_is_compatible(wheel.name):
            raise PackageValidationError(f"wheel is incompatible with the current runtime: {wheel.name}")
        wheel_hashes.add(manifest_entries[relative])

    lock_path = package_dir / "backend" / "requirements.lock"
    lock_text = lock_path.read_text(encoding="utf-8")
    lock_hashes = {digest.lower() for digest in re.findall(r"--hash=sha256:([0-9a-fA-F]{64})", lock_text)}
    if lock_hashes != wheel_hashes:
        raise PackageValidationError("requirements.lock hashes do not exactly match the wheelhouse")


def validate_package(
    package_dir: Path,
    manifest_name: str = "manifest.json",
    sums_name: str = "SHA256SUMS",
    *,
    profile: str | None = None,
) -> int:
    package_dir = package_dir.resolve()
    if manifest_name != "manifest.json" or sums_name != "SHA256SUMS":
        raise PackageValidationError("control files must be package-root manifest.json and SHA256SUMS")
    if profile not in {None, "r8"}:
        raise PackageValidationError(f"unknown validation profile: {profile}")
    manifest_path = package_dir / manifest_name
    sums_path = package_dir / sums_name
    if not manifest_path.is_file() or not sums_path.is_file():
        raise PackageValidationError("manifest.json and SHA256SUMS are required")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageValidationError(f"invalid manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PackageValidationError("manifest root must be an object")
    manifest_files = manifest.get("files")
    if manifest_files is None:
        raise PackageValidationError("manifest.files is required")
    manifest_entries = _entries(manifest_files, "manifest")
    sums_entries = parse_sha256sums(sums_path)
    manifest_keys = {path.casefold() for path in manifest_entries}
    sums_by_key = {path.casefold(): digest for path, digest in sums_entries.items()}
    if manifest_keys != set(sums_by_key):
        raise PackageValidationError("manifest and SHA256SUMS file lists differ")
    _check_runtime(manifest)
    actual_files: set[str] = set()
    for candidate in package_dir.rglob("*"):
        relative = candidate.relative_to(package_dir).as_posix()
        if _is_link(candidate):
            raise PackageValidationError(f"package contains a symlink or junction: {relative}")
        if candidate.is_file() and relative not in {manifest_name, sums_name}:
            actual_files.add(relative.casefold())
    if actual_files != manifest_keys:
        raise PackageValidationError("package contains missing or unlisted payload files")
    for path, expected in manifest_entries.items():
        target = package_dir / Path(*path.split("/"))
        try:
            target.resolve(strict=False).relative_to(package_dir)
        except ValueError as exc:
            raise PackageValidationError(f"listed file escapes package directory: {path}") from exc
        if any(_is_link(part) for part in [package_dir, *target.parents] if part != package_dir):
            raise PackageValidationError(f"listed file uses a symlinked path: {path}")
        if not target.is_file() or _is_link(target):
            raise PackageValidationError(f"listed file is missing or not a regular file: {path}")
        actual = _sha256_file(target)
        if actual != expected or actual != sums_by_key[path.casefold()]:
            raise PackageValidationError(f"SHA-256 mismatch: {path}")
    if profile == "r8":
        _check_r8_profile(package_dir, manifest_entries)
    return len(manifest_entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--profile", choices=["r8"])
    args = parser.parse_args(argv)
    try:
        count = validate_package(args.package_dir, profile=args.profile)
    except PackageValidationError as exc:
        print(f"OFFLINE PACKAGE INVALID: {exc}", file=sys.stderr)
        return 2
    print(f"OFFLINE PACKAGE OK: {count} files verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
