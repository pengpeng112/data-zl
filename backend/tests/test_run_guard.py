"""215 E2：pytest 运行期守卫测试（advisory lock 互斥 + 纯逻辑哨兵作用域）。

- 锁：根 conftest 已在本进程持有 APP_TEST_DB_URL 的 advisory lock，
  同库第二连接/第二 pytest 进程必须取锁失败并 fail-fast。
- 哨兵：无真实测试库配置时落哨兵；有真实配置（典型=混合目录运行）时
  原样保留，不得覆盖；哨兵落下后具备幂等性（后续子目录不再改写）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests._run_guard import (
    apply_pure_logic_env_sentinel,
    run_lock_key,
    try_acquire_run_lock,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_run_lock_key_stable_and_url_sensitive():
    url = "postgresql+psycopg://user@127.0.0.1:15432/asset_test"
    key = run_lock_key(url)
    assert key == run_lock_key(url)
    assert key != run_lock_key("postgresql+psycopg://user@127.0.0.1:15432/other_test")
    # pg_try_advisory_lock 参数为 bigint：键必须落在有符号 64 位区间。
    assert -(2**63) <= key <= 2**63 - 1


def test_run_lock_held_by_this_pytest_process():
    """根 conftest 导入期应已持锁，且跨连接视角锁不可再取（会话级语义）。"""
    from tests import conftest as root_conftest

    assert root_conftest._RUN_LOCK_CONNECTION is not None
    conn, acquired = try_acquire_run_lock(os.environ["APP_TEST_DB_URL"])
    try:
        assert acquired is False
        assert conn is None
    finally:
        if conn is not None:  # pragma: no cover - 防御：取到即测试失败，别漏连接
            conn.close()


def test_second_pytest_process_fails_fast_on_same_db():
    """DEF212-001 场景回归：父进程持锁时，同库第二 pytest 进程启动即退出。"""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_run_guard.py::test_run_lock_key_stable_and_url_sensitive",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        env=dict(os.environ),
    )
    # pytest.exit 在 conftest 导入期被 pytest 包装为 UsageError（exit 4），
    # 在收集/运行期为 Exit（exit 3）。语义契约=带提示 fail-fast，两种码都接受。
    assert result.returncode in (3, 4), (
        f"expected fail-fast exit 3/4, got {result.returncode}; "
        f"stdout={result.stdout[-500:]}; stderr={result.stderr[-500:]}"
    )
    combined = result.stdout + result.stderr
    assert "advisory lock" in combined
    assert "Another pytest session" in combined


def test_sentinel_skipped_when_real_test_url_present(monkeypatch):
    """混合目录运行：真实 APP_TEST_DB_URL 已配置时哨兵必须让位。"""
    real = "postgresql+psycopg://user@127.0.0.1:15432/asset_test"
    monkeypatch.setenv("APP_TEST_DB_URL", real)
    monkeypatch.setenv("APP_DB_URL", real)

    applied = apply_pure_logic_env_sentinel("postgresql+psycopg://sentinel-x/test")

    assert applied is False
    assert os.environ["APP_TEST_DB_URL"] == real
    assert os.environ["APP_DB_URL"] == real


def test_sentinel_applied_when_no_test_url(monkeypatch):
    """纯逻辑独立运行：无任何配置时哨兵落位并满足含 test 的守卫口径。"""
    monkeypatch.delenv("APP_TEST_DB_URL", raising=False)
    monkeypatch.delenv("APP_DB_URL", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    applied = apply_pure_logic_env_sentinel("postgresql+psycopg://sentinel-y/test")

    assert applied is True
    assert os.environ["APP_TEST_DB_URL"] == "postgresql+psycopg://sentinel-y/test"
    assert os.environ["APP_DB_URL"] == "postgresql+psycopg://sentinel-y/test"
    assert os.environ["APP_ENV"] == "test"


def test_sentinel_idempotent_once_applied(monkeypatch):
    """哨兵含 "test"：先落位的哨兵对后续子目录 conftest 视同真实配置。"""
    monkeypatch.delenv("APP_TEST_DB_URL", raising=False)
    monkeypatch.delenv("APP_DB_URL", raising=False)

    assert apply_pure_logic_env_sentinel("postgresql+psycopg://sentinel-z/test") is True
    assert apply_pure_logic_env_sentinel("postgresql+psycopg://sentinel-w/test") is False
    assert os.environ["APP_TEST_DB_URL"] == "postgresql+psycopg://sentinel-z/test"


def test_live_env_not_polluted_by_sentinel_subdirs():
    """混合目录运行现场探针：与纯逻辑子目录同进程收集时 env 必须保持真实测试库。

    本用例不做 monkeypatch——在「pytest tests/plan144 tests/test_run_guard.py」
    这类混合选择下，若子目录哨兵仍无条件全局写，此处会看到 sentinel 字样。
    """
    url = os.environ.get("APP_TEST_DB_URL", "")
    assert url and "test" in url.lower()
    assert "sentinel" not in url.lower()
    assert "sentinel" not in os.environ.get("APP_DB_URL", "").lower()
