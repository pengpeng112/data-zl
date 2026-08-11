"""Build a fully pinned, hash-locked requirements file from a wheelhouse."""

from __future__ import annotations

import argparse
import hashlib
import re
from collections import defaultdict
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _python_parts(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"invalid target Python version: {value}")
    return int(match.group(1)), int(match.group(2))


def _tag_matches_target(tag, *, python_version: str, os_name: str, architecture: str) -> bool:
    major, minor = _python_parts(python_version)
    os_name = os_name.lower()
    architecture = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(
        architecture.lower(), architecture.lower()
    )

    if tag.platform == "any":
        platform_matches = True
    elif os_name == "linux":
        platform_matches = (
            not tag.platform.startswith("musllinux")
            and tag.platform.endswith(f"_{architecture}")
            and (tag.platform.startswith("manylinux") or tag.platform.startswith("linux_"))
        )
    else:
        raise ValueError(f"unsupported target OS: {os_name}")
    if not platform_matches:
        return False

    if match := re.fullmatch(r"py(\d)(\d+)?", tag.interpreter):
        interpreter_major = int(match.group(1))
        interpreter_minor = int(match.group(2)) if match.group(2) else None
        return interpreter_major == major and (interpreter_minor is None or interpreter_minor == minor)
    if match := re.fullmatch(r"cp(\d)(\d+)", tag.interpreter):
        interpreter_major = int(match.group(1))
        interpreter_minor = int(match.group(2))
        if interpreter_major != major:
            return False
        if tag.abi == "abi3":
            return interpreter_minor <= minor
        return interpreter_minor == minor and tag.abi in {f"cp{major}{minor}", "none"}
    return False


def build_hashed_lock(
    wheel_dir: Path,
    *,
    python_version: str = "3.11",
    os_name: str = "linux",
    architecture: str = "x86_64",
) -> str:
    if not wheel_dir.is_dir():
        raise ValueError(f"wheel directory does not exist: {wheel_dir}")

    seen_filenames: set[str] = set()
    packages: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    nested_wheels = [wheel for wheel in wheel_dir.rglob("*.whl") if wheel.parent != wheel_dir]
    if nested_wheels:
        raise ValueError(f"wheel directory must be flat: {nested_wheels[0].relative_to(wheel_dir)}")
    wheels = sorted(wheel_dir.glob("*.whl"), key=lambda item: item.name.casefold())
    if not wheels:
        raise ValueError("wheel directory contains no .whl files")

    for wheel in wheels:
        folded = wheel.name.casefold()
        if folded in seen_filenames:
            raise ValueError(f"duplicate wheel filename: {wheel.name}")
        seen_filenames.add(folded)
        try:
            distribution, version, _build, tags = parse_wheel_filename(wheel.name)
        except Exception as exc:
            raise ValueError(f"invalid wheel filename: {wheel.name}") from exc
        if not any(
            _tag_matches_target(
                tag,
                python_version=python_version,
                os_name=os_name,
                architecture=architecture,
            )
            for tag in tags
        ):
            raise ValueError(
                f"wheel is incompatible with {os_name}/{architecture}/Python {python_version}: {wheel.name}"
            )
        name = canonicalize_name(distribution)
        packages[name][str(version)].add(_sha256(wheel))

    conflicts = {
        name: sorted(versions)
        for name, versions in packages.items()
        if len(versions) != 1
    }
    if conflicts:
        raise ValueError(f"multiple versions found for a package: {conflicts}")

    lines = [
        f"# Generated from the verified {os_name} {architecture} Python {python_version} wheelhouse.",
        "# Install with: pip install --require-hashes --no-index --find-links=wheels -r requirements.lock",
    ]
    for name in sorted(packages):
        version, hashes = next(iter(packages[name].items()))
        ordered_hashes = sorted(hashes)
        lines.append(f"{name}=={version} \\")
        for index, digest in enumerate(ordered_hashes):
            suffix = " \\" if index < len(ordered_hashes) - 1 else ""
            lines.append(f"    --hash=sha256:{digest}{suffix}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--python-version", default="3.11")
    parser.add_argument("--os", default="linux")
    parser.add_argument("--arch", default="x86_64")
    args = parser.parse_args()
    content = build_hashed_lock(
        args.wheel_dir,
        python_version=args.python_version,
        os_name=args.os,
        architecture=args.arch,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8", newline="\n")
    print(f"HASHED_LOCK_OK packages={content.count('==')} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
