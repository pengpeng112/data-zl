from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from deploy.offline.build_hashed_lock import build_hashed_lock


def _wheel(root: Path, name: str, content: bytes) -> Path:
    path = root / name
    path.write_bytes(content)
    return path


def test_builds_sorted_fully_hashed_lock(tmp_path: Path):
    second = _wheel(tmp_path, "z_pkg-2.0-py3-none-any.whl", b"second")
    first = _wheel(tmp_path, "a_pkg-1.0-py3-none-any.whl", b"first")

    lock = build_hashed_lock(tmp_path)

    assert lock.index("a-pkg==1.0") < lock.index("z-pkg==2.0")
    assert hashlib.sha256(first.read_bytes()).hexdigest() in lock
    assert hashlib.sha256(second.read_bytes()).hexdigest() in lock
    assert lock.count("--hash=sha256:") == 2


def test_rejects_empty_wheelhouse(tmp_path: Path):
    with pytest.raises(ValueError, match="no .whl"):
        build_hashed_lock(tmp_path)


def test_rejects_multiple_versions(tmp_path: Path):
    _wheel(tmp_path, "same_pkg-1.0-py3-none-any.whl", b"one")
    _wheel(tmp_path, "same_pkg-2.0-py3-none-any.whl", b"two")

    with pytest.raises(ValueError, match="multiple versions"):
        build_hashed_lock(tmp_path)


@pytest.mark.parametrize(
    "filename",
    [
        "demo-1.0-cp310-cp310-manylinux2014_x86_64.whl",
        "demo-1.0-cp311-cp311-win_amd64.whl",
        "demo-1.0-cp311-cp311-musllinux_1_2_x86_64.whl",
        "demo-1.0-cp311-cp311-manylinux2014_aarch64.whl",
    ],
)
def test_rejects_incompatible_wheel_tags(tmp_path: Path, filename: str):
    _wheel(tmp_path, filename, b"wrong target")

    with pytest.raises(ValueError, match="incompatible"):
        build_hashed_lock(tmp_path)


def test_accepts_older_cpython_abi3_wheel(tmp_path: Path):
    _wheel(tmp_path, "demo-1.0-cp37-abi3-manylinux2014_x86_64.whl", b"abi3")

    assert "demo==1.0" in build_hashed_lock(tmp_path)


def test_rejects_nested_wheel(tmp_path: Path):
    nested = tmp_path / "nested"
    nested.mkdir()
    _wheel(nested, "demo-1.0-py3-none-any.whl", b"nested")

    with pytest.raises(ValueError, match="must be flat"):
        build_hashed_lock(tmp_path)
