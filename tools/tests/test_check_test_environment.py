"""tools/check_test_environment.py 单测（185 号 C2）。

五类用例：缺 URL / 生产 URL / 共享不可清理库（denylist，子进程隔离 env）/
端口被占（预期 integration_ready + WARN 就绪）/ 合法隔离库（含端口未监听的
integration_blocked 反例）。全部纯逻辑，不连真实数据库、不杀进程。
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_test_environment as cte  # noqa: E402

VENV_PY = Path(__file__).resolve().parents[2] / "backend" / ".venv" / "Scripts" / "python.exe"


def test_missing_url_pure_logic(monkeypatch):
    monkeypatch.delenv("APP_TEST_DB_URL", raising=False)
    report = cte.evaluate("", None)
    assert report["state"] == "pure_logic_ready"
    assert report["commands"]


def test_production_url_invalid():
    report = cte.evaluate(
        "postgresql+psycopg://u:secret@127.0.0.1:5432/data_asset", None
    )
    assert report["state"] == "invalid_url"
    assert "test" in report["reasons"][0]


def test_app_db_url_inconsistency():
    report = cte.evaluate(
        "postgresql+psycopg://u:s@127.0.0.1:15432/data_asset_test",
        "postgresql+psycopg://u:s@127.0.0.1:5432/data_asset",
    )
    assert report["state"] == "invalid_url"
    assert any("一致" in r for r in report["reasons"])


def _listening_socket():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(8)  # 背积压 8：探测连接不 accept，防止 Windows 拒绝后续连接
    return s, s.getsockname()[1]


def test_port_occupied_is_integration_ready_with_warn():
    s, port = _listening_socket()
    try:
        report = cte.evaluate(
            f"postgresql+psycopg://u:s@127.0.0.1:{port}/data_asset_test", None
        )
        assert report["state"] == "integration_ready"
        assert any("复用" in w for w in report["warns"])  # 占用=就绪 WARN，非 FAIL
        assert cte.main(["--url", f"postgresql+psycopg://u:s@127.0.0.1:{port}/data_asset_test"]) == 0
    finally:
        s.close()


def test_valid_isolated_db_and_blocked_case():
    s, port = _listening_socket()
    try:
        report = cte.evaluate(
            f"postgresql+psycopg://u:s@127.0.0.1:{port}/data_asset_test", None
        )
        assert report["state"] == "integration_ready"  # 合法隔离库：URL 规则过 + 端口在听
    finally:
        s.close()
    # 同一 URL 端口关停后 → integration_blocked（不臆造就绪）
    report = cte.evaluate(
        f"postgresql+psycopg://u:s@127.0.0.1:{port}/data_asset_test", None
    )
    assert report["state"] == "integration_blocked"


def test_shared_non_cleanable_via_denylist_subprocess(tmp_path):
    """共享不可清理库：APP_TEST_DATABASE_DENYLIST 命中含 test 的库名（database_guard
    导入时读取 env，须用子进程隔离；同时验证 CLI 全链路）。"""
    url = "postgresql+psycopg://u:s@127.0.0.1:15432/data_asset_test_shared"
    env = dict(os.environ)
    env["APP_TEST_DATABASE_DENYLIST"] = "data_asset_test_shared"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [str(VENV_PY), str(Path(__file__).resolve().parents[1] / "check_test_environment.py"),
         "--url", url, "--json"],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["state"] == "invalid_url"
    assert any("拒绝清单" in r for r in report["reasons"])


def test_mask_url_never_leaks_password():
    masked = cte.mask_url("postgresql+psycopg://alice:topsecret@10.0.0.1:5432/data_asset_test")
    assert "topsecret" not in masked
    assert "***" in masked and "alice" in masked
