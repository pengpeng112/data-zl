import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "verify_offline_package.py"
spec = importlib.util.spec_from_file_location("verify_offline_package", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def make_package(tmp_path, *, content=b"wheel", manifest_files=None, sums_files=None, target=None):
    (tmp_path / "wheels").mkdir()
    file_path = tmp_path / "wheels" / "demo.whl"
    file_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    manifest_files = manifest_files or [{"path": "wheels/demo.whl", "sha256": digest}]
    sums_files = sums_files or [("wheels/demo.whl", digest)]
    manifest = {"files": manifest_files}
    manifest["target"] = target or {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "os": platform.system().lower(),
        "arch": platform.machine(),
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "SHA256SUMS").write_text(
        "\n".join(f"{digest}  {path}" for path, digest in sums_files) + "\n", encoding="utf-8"
    )
    return tmp_path


def test_valid_package_is_verified(tmp_path):
    assert module.validate_package(make_package(tmp_path)) == 1


def test_missing_file_fails_closed(tmp_path):
    package = make_package(tmp_path)
    (package / "wheels/demo.whl").unlink()
    with pytest.raises(module.PackageValidationError, match="missing"):
        module.validate_package(package)


def test_hash_mismatch_fails_closed(tmp_path):
    package = make_package(tmp_path)
    (package / "wheels/demo.whl").write_bytes(b"tampered")
    with pytest.raises(module.PackageValidationError, match="mismatch"):
        module.validate_package(package)


@pytest.mark.parametrize("path", ["/tmp/a.whl", "C:/tmp/a.whl", "../a.whl", "wheels/../a.whl", "wheels\\a.whl"])
def test_unsafe_paths_fail_closed(tmp_path, path):
    digest = "0" * 64
    package = make_package(tmp_path, manifest_files=[{"path": path, "sha256": digest}], sums_files=[(path, digest)])
    with pytest.raises(module.PackageValidationError, match="path"):
        module.validate_package(package)


def test_duplicate_manifest_entries_fail_closed(tmp_path):
    digest = hashlib.sha256(b"wheel").hexdigest()
    package = make_package(
        tmp_path,
        manifest_files=[{"path": "wheels/demo.whl", "sha256": digest}, {"path": "WHEELS/demo.whl", "sha256": digest}],
        sums_files=[("wheels/demo.whl", digest), ("WHEELS/demo.whl", digest)],
    )
    with pytest.raises(module.PackageValidationError, match="duplicate"):
        module.validate_package(package)


def test_manifest_and_sums_must_match(tmp_path):
    package = make_package(tmp_path, sums_files=[("other.whl", "0" * 64)])
    with pytest.raises(module.PackageValidationError, match="lists differ"):
        module.validate_package(package)


def test_declared_runtime_mismatch_fails_closed(tmp_path, monkeypatch):
    package = make_package(tmp_path, target={"python_version": "0.0", "os": "linux", "arch": platform.machine()})
    with pytest.raises(module.PackageValidationError, match="Python version"):
        module.validate_package(package)


def test_cli_returns_nonzero_for_incomplete_package(tmp_path):
    assert module.main([str(tmp_path)]) != 0


def test_runtime_declarations_are_required(tmp_path):
    package = make_package(tmp_path)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("target")
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(module.PackageValidationError, match="target Python"):
        module.validate_package(package)


def test_unlisted_payload_file_fails_closed(tmp_path):
    package = make_package(tmp_path)
    (package / "unexpected.bin").write_bytes(b"not declared")
    with pytest.raises(module.PackageValidationError, match="unlisted"):
        module.validate_package(package)


@pytest.mark.parametrize(
    ("manifest_name", "sums_name"),
    [("../manifest.json", "SHA256SUMS"), ("manifest.json", "../SHA256SUMS"), ("other.json", "SHA256SUMS")],
)
def test_control_file_paths_cannot_escape_or_be_replaced(tmp_path, manifest_name, sums_name):
    package = make_package(tmp_path)
    with pytest.raises(module.PackageValidationError, match="control files"):
        module.validate_package(package, manifest_name, sums_name)


def test_r8_profile_rejects_incomplete_generic_package(tmp_path):
    package = make_package(tmp_path)
    with pytest.raises(module.PackageValidationError, match="R8 package"):
        module.validate_package(package, profile="r8")


@pytest.mark.parametrize(
    "wheel_name",
    [
        "demo-1.0-py3-none-any.whl",
        f"demo-1.0-cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-manylinux2014_{platform.machine()}.whl",
        "demo-1.0-cp37-abi3-manylinux2014_x86_64.whl",
    ],
)
def test_compatible_wheel_tags(wheel_name):
    if platform.system().lower() != "linux" and "manylinux" in wheel_name:
        pytest.skip("manylinux compatibility is checked on the Linux target runtime")
    if wheel_name.endswith("x86_64.whl") and platform.machine().lower() not in {"x86_64", "amd64", "x64"}:
        pytest.skip("x86_64 compatibility is checked on an x86_64 runtime")
    assert module._wheel_is_compatible(wheel_name)


@pytest.mark.parametrize(
    "wheel_name",
    [
        "demo-1.0-cp310-cp310-manylinux2014_x86_64.whl",
        "demo-1.0-cp311-cp311-win_amd64.whl",
        "demo-1.0-cp311-cp311-musllinux_1_2_x86_64.whl",
        "demo-1.0-cp311-cp311-manylinux2014_aarch64.whl",
    ],
)
def test_incompatible_wheel_tags(wheel_name):
    assert not module._wheel_is_compatible(wheel_name)
