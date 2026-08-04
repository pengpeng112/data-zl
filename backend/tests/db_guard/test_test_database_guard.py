"""111 号 S1：测试数据库不可绕过门禁的子进程负向/正向测试。

纯逻辑子进程测试：每个用例在独立解释器进程 + 受控环境变量下运行，
验证任意 pytest 入口在缺少合法隔离测试 URL 时建连前失败，且不触碰数据库。
子目录自带 conftest（no-op clean_test_database），不要求本机提供测试库。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _clean_env() -> dict:
    """继承完整环境，仅清空全部 APP_*/PYTEST_* 与测试库变量，再按用例显式设置。

    PYTEST_CURRENT_TEST/PYTEST_VERSION 会被父进程继承并导致子进程被误判为
    pytest 进程，必须显式剔除。不能过度裁剪（Windows 子进程依赖完整环境）。
    """
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("APP_") and not k.startswith("PYTEST_")
    }
    env["APP_ENV"] = "test"
    return env


def _run(args: list[str], env: dict, expect_fail: bool) -> subprocess.CompletedProcess:
    cmd = [sys.executable, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120)
    if expect_fail and proc.returncode == 0:
        raise AssertionError(f"预期失败但返回 0\nstdout={proc.stdout}\nstderr={proc.stderr}")
    if not expect_fail and proc.returncode != 0:
        raise AssertionError(f"预期成功但返回 {proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def _test_url(dbname: str = "asset_test") -> str:
    # 哨兵 URL：仅门禁字符串校验，绝不真实连接。
    return f"postgresql://u:p@127.0.0.1:5432/{dbname}"


# ---- 直接 import app.core.db（覆盖单文件 / 无 conftest 场景） ----

def test_import_engine_missing_test_url_fails():
    env = _clean_env()
    env.pop("APP_TEST_DB_URL", None)
    env.pop("APP_DB_URL", None)
    proc = _run(["-c", "import app.core.db"], env, expect_fail=True)
    assert "APP_TEST_DB_URL" in proc.stdout + proc.stderr


def test_import_engine_fake_test_dbname_fails():
    env = _clean_env()
    env["APP_TEST_DB_URL"] = _test_url("production_db")  # 库名不含 test
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = _run(["-c", "import app.core.db"], env, expect_fail=True)
    assert "test" in proc.stdout + proc.stderr


def test_import_engine_db_url_mismatch_fails():
    """APP_DB_URL 与 APP_TEST_DB_URL 不一致（指向生产）建连前失败。"""
    env = _clean_env()
    env["APP_TEST_DB_URL"] = _test_url("asset_test")
    env["APP_DB_URL"] = "postgresql://u:p@10.10.8.83:5432/asset"  # 生产
    proc = _run(["-c", "import app.core.db"], env, expect_fail=True)
    assert "完全一致" in proc.stdout + proc.stderr


def test_import_engine_prod_env_dev_fails():
    """测试进程以 APP_ENV=dev/production 建连前失败（真实 pytest 进程 + --noconftest）。"""
    for bad_env in ("dev", "production"):
        env = _clean_env()
        env["APP_ENV"] = bad_env
        env["RUN_TEST_TARGET"] = "1"
        env["APP_TEST_DB_URL"] = _test_url("asset_test")
        env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/db_guard/test_target.py", "--noconftest", "-q"],
            capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120,
        )
        assert proc.returncode != 0, f"APP_ENV={bad_env} 应失败"
        assert "APP_ENV" in proc.stdout + proc.stderr


def test_import_engine_prod_url_denied():
    """生产主库（库名无 test）作为伪测试库必须失败。"""
    env = _clean_env()
    env["APP_TEST_DB_URL"] = "postgresql://u:p@10.10.8.83:5432/asset"
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = _run(["-c", "import app.core.db"], env, expect_fail=True)
    assert "test" in proc.stdout + proc.stderr


def test_import_engine_stale_env_dbname_denied():
    """111 S2：误连的陈旧非测试环境（data_asset 库名）作为测试目标必须失败。"""
    env = _clean_env()
    env["APP_TEST_DB_URL"] = "postgresql://u:p@10.20.1.153:5432/data_asset"
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = _run(["-c", "import app.core.db"], env, expect_fail=True)
    assert "拒绝" in proc.stdout + proc.stderr or "test" in proc.stdout + proc.stderr


def test_import_engine_denylist_via_env_works():
    """通过 APP_TEST_DATABASE_DENYLIST 扩展拒绝清单。"""
    env = _clean_env()
    env["APP_TEST_DATABASE_DENYLIST"] = "data_asset_test_dup"
    env["APP_TEST_DB_URL"] = "postgresql://u:p@127.0.0.1:5432/data_asset_test_dup"
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = _run(["-c", "import app.core.db"], env, expect_fail=True)
    assert "拒绝" in proc.stdout + proc.stderr


def test_valid_isolated_test_url_imports_ok():
    """显式隔离测试 URL 下 import 不抛门禁错误（不要求目标真实可达）。"""
    env = _clean_env()
    env["APP_TEST_DB_URL"] = _test_url("asset_test")
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = _run(["-c", "import app.core.db; print('IMPORT_OK')"], env, expect_fail=False)
    assert "IMPORT_OK" in proc.stdout


# ---- 生产/运维非测试进程不误伤 ----

def test_plain_script_not_disturbed():
    """普通进程（非 pytest、APP_ENV=production、合法 URL）不受门禁拦截。"""
    env = _clean_env()
    env["APP_ENV"] = "production"
    env["APP_TEST_DB_URL"] = _test_url("asset_test")
    env["APP_DB_URL"] = "postgresql://u:p@127.0.0.1:5432/asset"
    proc = _run(
        ["-c", "from app.core.database_guard import is_pytest_process; print(is_pytest_process())"],
        env, expect_fail=False,
    )
    assert "False" in proc.stdout


def test_plain_script_with_no_test_url_not_disturbed():
    """生产/运维脚本未配置 APP_TEST_DB_URL 也不被门禁拦截。"""
    env = _clean_env()
    env["APP_ENV"] = "production"
    env.pop("APP_TEST_DB_URL", None)
    proc = _run(
        ["-c", "from app.core.database_guard import validate_test_database_url; "
               "validate_test_database_url('postgresql://u:p@10.10.8.83:5432/asset'); print('PROD_OK')"],
        env, expect_fail=False,
    )
    assert "PROD_OK" in proc.stdout


# ---- --noconftest 必须失败 ----

def test_noconftest_guard_fails_before_connect():
    """--noconftest 运行导入探针必须在建连前失败（DatabaseGuardError）。"""
    env = _clean_env()
    env.pop("APP_TEST_DB_URL", None)
    env.pop("APP_DB_URL", None)
    env["APP_ENV"] = "test"
    env["RUN_TEST_TARGET"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/db_guard/test_target.py", "--noconftest", "-q"],
        capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120,
    )
    assert proc.returncode != 0
    assert "APP_TEST_DB_URL" in proc.stdout + proc.stderr