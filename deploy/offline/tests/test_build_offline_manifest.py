from __future__ import annotations

import json
from pathlib import Path

import pytest

from deploy.offline.build_offline_manifest import build_manifest, collect_payload


def test_builds_matching_manifest_and_sums(tmp_path: Path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path, sums_path, count = build_manifest(
        tmp_path,
        python_version="3.11",
        os_name="linux",
        architecture="x86_64",
        source_revision="abc1234",
        source_tree_state="clean",
        created_at="2026-08-11T00:00:00Z",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert count == 1
    assert manifest["target"] == {"python_version": "3.11", "os": "linux", "arch": "x86_64"}
    assert manifest["created_at"] == "2026-08-11T00:00:00+00:00"
    assert manifest["source_tree_state"] == "clean"
    assert manifest["files"][0]["path"] == "backend/app.py"
    assert "*backend/app.py" in sums_path.read_text(encoding="utf-8")


def test_rejects_empty_package(tmp_path: Path):
    with pytest.raises(ValueError, match="no payload"):
        collect_payload(tmp_path)


def test_rejects_symlink_when_supported(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(ValueError, match="symlink"):
        collect_payload(tmp_path)


@pytest.mark.parametrize("name", ["Manifest.json", "sha256sums"])
def test_rejects_case_conflicting_control_files(tmp_path: Path, name: str):
    (tmp_path / "payload.txt").write_text("x", encoding="utf-8")
    (tmp_path / name).write_text("conflict", encoding="utf-8")

    with pytest.raises(ValueError, match="control file"):
        collect_payload(tmp_path)


def test_repeated_build_is_deterministic(tmp_path: Path):
    (tmp_path / "payload.txt").write_text("x", encoding="utf-8")
    kwargs = {
        "python_version": "3.11",
        "os_name": "linux",
        "architecture": "x86_64",
        "source_revision": "abcdef1",
        "source_tree_state": "dirty",
        "created_at": "2026-08-11T00:00:00Z",
    }

    manifest_path, sums_path, _ = build_manifest(tmp_path, **kwargs)
    first = (manifest_path.read_bytes(), sums_path.read_bytes())
    manifest_path, sums_path, _ = build_manifest(tmp_path, **kwargs)

    assert (manifest_path.read_bytes(), sums_path.read_bytes()) == first


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("python_version", "three", "Python version"),
        ("os_name", "windows", "target OS"),
        ("architecture", "sparc", "architecture"),
        ("source_revision", "not-a-sha", "source revision"),
        ("source_tree_state", "unknown", "source tree state"),
    ],
)
def test_rejects_invalid_target_metadata(tmp_path: Path, field: str, value: str, message: str):
    (tmp_path / "payload.txt").write_text("x", encoding="utf-8")
    kwargs = {
        "python_version": "3.11",
        "os_name": "linux",
        "architecture": "x86_64",
        "source_revision": "abcdef1",
        "source_tree_state": "dirty",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=message):
        build_manifest(tmp_path, **kwargs)
