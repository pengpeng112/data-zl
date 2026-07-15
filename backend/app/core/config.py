from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    db_url: str
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8848"]
    # 数据生命周期（P5.9-T14）
    snapshot_retention_days: int = 90
    event_retention_days: int = 365
    # 凭据加密密钥（P5.9-T5）
    credential_encrypt_key: str = ""
    # APScheduler 时区
    scheduler_timezone: str = "Asia/Shanghai"

    # HIS identity sync source. Password must come from APP_HIS_SOURCE_PASSWORD.
    his_source_host: str = "10.10.10.15"
    his_source_port: int = 1521
    his_source_service: str = "his"
    his_source_user: str = "ready_his"
    his_source_password: str = ""
    his_source_connection_mode: str = "direct"
    his_source_oracle_client_lib: str = "/opt/oracle"
    his_source_jump_host: str = "10.10.8.83"
    his_source_jump_port: int = 22
    his_source_jump_user: str = "root"
    his_source_jump_key: str = ""
    his_identity_sync_max_rows: int = 20000

    # Production deployments must explicitly enable strict bound-user enforcement.
    rbac_require_bound_token: bool = False
    env: str = "dev"
    # Ops write channel is code-ready but production writes stay disabled until D1-D5 are confirmed.
    ops_write_enabled: bool = False
    ops_write_d1_d5_confirmed: bool = False
    ops_write_confirmation_token: str = ""
    # Plan 76: hide template/run approval UI for admin-simplified flow (API kept).
    ops_approval_ui_enabled: bool = False

    # Local account auth / JWT (59 号计划)
    # 本地开发默认 HS256 + jwt_secret；生产用 RS256 + 密钥文件路径。
    jwt_algorithm: str = "HS256"
    jwt_secret: str = "dev-only-change-me"
    jwt_private_key_path: str = ""
    jwt_public_key_path: str = ""
    auth_access_token_ttl_minutes: int = 15
    auth_refresh_token_ttl_hours: int = 8
    auth_max_failed_login: int = 5
    auth_lockout_minutes: int = 15
    auth_cookie_name: str = "refresh_token"
    auth_cookie_path: str = "/api/v1/auth"
    auth_cookie_samesite: str = "lax"
    # 内网 HTTP 部署必须 false；仅 HTTPS 才可 true（否则浏览器不存 Cookie）
    auth_cookie_secure: bool = False
    # 密码策略：与前端登录页一致 — 8-18 位，数字/字母/符号任意两类
    auth_password_min_length: int = 8
    auth_password_max_length: int = 18
    # 登录限流（次/分钟）；测试环境可设 0 关闭
    auth_login_rate_limit: str = "5/minute"
    auth_refresh_rate_limit: str = "30/minute"
    # 全局限流开关；pytest 通过 APP_RATE_LIMIT_ENABLED=false 关闭
    rate_limit_enabled: bool = True


settings = Settings()
