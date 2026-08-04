"""111 号 S4：production 配置失败关闭。

子进程纯逻辑测试：通过构造 pydantic Settings 实例注入 validate_production_config，
断言弱配置（占位 JWT、通配 CORS、宽松开关、缺 build-id/git_sha）被拒绝，正式强配置通过。
不连接数据库。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_SNIPPET = r"""
import sys
sys.path.insert(0, r"{BACKEND_DIR}")
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.startup_check import (
    StartupCheckError,
    validate_production_config,
    run_startup_check,
)


class _S(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")
    env: str = "dev"
    jwt_algorithm: str = "HS256"
    jwt_secret: str = ""
    jwt_private_key_path: str = ""
    jwt_public_key_path: str = ""
    cors_origins: list[str] = []
    rbac_require_bound_token: bool = False
    ops_write_enabled: bool = False
    dict_medical_push_enabled: bool = False
    identity_sync_enabled: bool = False
    identity_nightly_enabled: bool = False
    identity_jhemr_password_write_enabled: bool = False
    identity_sync_cdms_credential_ref: str = ""
    identity_sync_jhemr_credential_ref: str = ""
    identity_hmac_key_ref: str = ""
    identity_jhemr_default_password_ref: str = ""
    identity_cdms_default_password_ref: str = ""
    build_id: str = "dev-local"
    git_sha: str = ""


def good(**o):
    base = dict(
        env="production",
        jwt_secret="k" * 64,
        cors_origins=['https://data.example.com'],
        rbac_require_bound_token=True,
        ops_write_enabled=False,
        dict_medical_push_enabled=False,
        identity_sync_enabled=False,
        identity_nightly_enabled=False,
        identity_jhemr_password_write_enabled=False,
        build_id="b-2026-1234",
        git_sha="f8a9b0c1d2e3",
    )
    base.update(o)
    return validate_production_config(_S(**base))


assert good() == [], "正式 production 配置应通过"
assert good(env="dev") == [], "dev 不应被 production 校验拦截"

errs = good(jwt_secret="dev-only-change-me")
assert errs and any("JWT" in e for e in errs), errs
errs = good(jwt_secret="short")
assert errs and any("长度" in e for e in errs), errs

errs = good(cors_origins=["*"])
assert errs and any("通配" in e for e in errs), errs
errs = good(cors_origins=['http://localhost:5173'])
assert errs, "保留 localhost 必须拒绝"

errs = good(rbac_require_bound_token=False)
assert errs and any("RBAC" in e for e in errs), errs

errs = good(ops_write_enabled=True)
assert errs and any("写开关" in e for e in errs), errs

errs = good(build_id="dev-local")
assert errs and any("build_id" in e for e in errs), errs
errs = good(git_sha="")
assert errs and any("git_sha" in e for e in errs), errs

print("STARTUP_CHECK_OK")
"""


def _clean_env() -> dict:
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("APP_") and not k.startswith("PYTEST_")
    }
    return env


def test_production_weak_config_fails_closed():
    env = _clean_env()
    proc = subprocess.run(
        [sys.executable, "-c", _SNIPPET.format(BACKEND_DIR=str(BACKEND_DIR))],
        capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "STARTUP_CHECK_OK" in proc.stdout
