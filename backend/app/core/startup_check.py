"""111 号 S4：production 配置失败关闭。

APP_ENV=production 时强制校验以下配置，任何一项不满足直接拒绝启动
（抛 StartupCheckError，lifespan 启动阶段失败）：
  - JWT 密钥非占位且足够长度（与 auth_service 请求期规则同源，禁止双套阈值）；
  - CORS origin 不含通配、不保留 localhost/127.0.0.1 开发地址；
  - CORS methods/headers 按生产最小集合收敛；
  - RBAC 绑定角色开启（rbac_require_bound_token=True）；
  - 运维/字典/身份写开关关闭（ops/dict_medical/identity 写入类开关）；
  - 凭据目录存在且权限正确；
  - build ID / git SHA 存在（非 dev-local / 空）。

非 production 环境（dev/test）不强制，保持本地开发路径不受影响。
"""
from __future__ import annotations

import os
from pathlib import Path

from . import config as cfg

# 生产最小 CORS 集合（111 §112：不得写成 *；仅收敛到常用方法/头）
PROD_ALLOWED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
PROD_ALLOWED_HEADERS = (
    "Authorization",
    "Content-Type",
    "X-Requested-With",
    "X-CSRF-Token",
    "Origin",
    "Accept",
    "Cache-Control",
)
# 明确的开发地址，生产不得保留
DEV_ORIGIN_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0")
# 占位/开发密钥，生产不得使用
PLACEHOLDER_JWT_SECRETS = ("dev-only-change-me", "", "changeme", "secret")
MIN_JWT_SECRET_LENGTH = 32
# 凭据目录默认值（与 credential_store 保持一致）
DEFAULT_CREDENTIAL_DIR = Path(os.environ.get("APP_CREDENTIAL_DIR", "/etc/data-asset/credentials"))


class StartupCheckError(RuntimeError):
    """production 启动配置校验失败。"""


def _validate_jwt(settings) -> list[str]:
    errors: list[str] = []
    algo = (settings.jwt_algorithm or "HS256").upper()
    if algo.startswith("HS"):
        secret = settings.jwt_secret or ""
        if secret in PLACEHOLDER_JWT_SECRETS:
            errors.append("JWT 密钥为占位/开发值，禁止用于 production")
        elif len(secret) < MIN_JWT_SECRET_LENGTH:
            errors.append(
                f"JWT 密钥长度 {len(secret)} 小于最小要求 {MIN_JWT_SECRET_LENGTH}"
            )
    else:
        priv = settings.jwt_private_key_path or ""
        pub = settings.jwt_public_key_path or ""
        if not priv and not pub:
            errors.append("RS256 模式必须配置 jwt_private_key_path/jwt_public_key_path")
        for path in (priv, pub):
            if path and not Path(path).is_file():
                errors.append(f"JWT 密钥文件不存在: {path}")
    return errors


def _validate_cors(settings) -> list[str]:
    errors: list[str] = []
    origins = settings.cors_origins or []
    if not origins:
        errors.append("CORS origin 不得为空")
    for origin in origins:
        lowered = origin.lower()
        if "*" in lowered:
            errors.append(f"CORS origin 不得为通配: {origin!r}")
        if any(marker in lowered for marker in DEV_ORIGIN_MARKERS):
            errors.append(f"CORS origin 不得保留开发地址: {origin!r}")
    # methods/headers：main.py 已按本模块常量收敛，防止被写成通配。
    return errors


def _validate_rbac_and_switches(settings) -> list[str]:
    errors: list[str] = []
    if not settings.rbac_require_bound_token:
        errors.append("production 必须开启 rbac_require_bound_token（绑定角色 RBAC）")
    # Most write switches remain forbidden in production. Medical dictionary
    # dispatch is the narrow exception after an explicit versioned approval.
    write_switches = {
        "ops_write_enabled": settings.ops_write_enabled,
        "identity_sync_enabled": settings.identity_sync_enabled,
        "identity_nightly_enabled": settings.identity_nightly_enabled,
        "identity_jhemr_password_write_enabled": settings.identity_jhemr_password_write_enabled,
    }
    for name, value in write_switches.items():
        if value:
            errors.append(f"production 写开关必须关闭: {name}=True")
    if settings.dict_medical_push_enabled:
        approval = str(getattr(settings, "dict_medical_production_approval_version", "") or "").strip()
        confirmation = str(getattr(settings, "dict_medical_push_confirmation_token", "") or "").strip()
        if not approval:
            errors.append("production 字典自动下发必须配置批准版本")
        if not confirmation:
            errors.append("production 字典自动下发必须配置确认令牌")
    return errors


def _validate_credential_dir(settings) -> list[str]:
    errors: list[str] = []
    # 生产身份同步/夜间任务依赖的凭据目录
    refs = [
        settings.identity_sync_cdms_credential_ref,
        settings.identity_sync_jhemr_credential_ref,
        settings.identity_hmac_key_ref,
        settings.identity_jhemr_default_password_ref,
        settings.identity_cdms_default_password_ref,
    ]
    existing_refs = [ref for ref in refs if ref and ref.startswith("file://")]
    if not existing_refs:
        return errors  # 全部使用 env: 或未配置，目录校验不强求
    directory = DEFAULT_CREDENTIAL_DIR
    if not directory.is_dir():
        errors.append(f"凭据目录不存在: {directory}")
        return errors
    # 权限检查：目录不应全局可写（仅属主/组可写，其余只读）
    try:
        import stat as stat_module

        mode = directory.stat().st_mode
        if stat_module.S_IWOTH & mode:
            errors.append(f"凭据目录权限过宽（其他用户可写）: {directory}")
    except OSError:
        errors.append(f"凭据目录不可访问: {directory}")
    return errors


def _validate_identity(settings) -> list[str]:
    errors: list[str] = []
    if not settings.build_id or settings.build_id == "dev-local":
        errors.append("production 必须注入非占位 build_id")
    if not settings.git_sha:
        errors.append("production 必须注入 git_sha")
    return errors


def validate_production_config(settings=None) -> list[str]:
    """统一入口：production 校验，返回错误列表（空=通过）。非 production 恒返回空。

    settings 可注入（测试用）；默认取全局 app.core.config.settings。
    """
    settings = settings if settings is not None else cfg.settings
    env = str(getattr(settings, "env", "") or "").strip().lower()
    if env != "production":
        return []
    errors: list[str] = []
    errors += _validate_jwt(settings)
    errors += _validate_cors(settings)
    errors += _validate_rbac_and_switches(settings)
    errors += _validate_credential_dir(settings)
    errors += _validate_identity(settings)
    return errors


def run_startup_check() -> None:
    """lifespan 启动前调用；production 配置不满足抛 StartupCheckError。"""
    errors = validate_production_config()
    if errors:
        raise StartupCheckError("production 启动配置校验失败: " + "; ".join(errors))
