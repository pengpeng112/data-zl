from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    db_url: str
    # 144 §15.2 feature flags (fixed names, default off)
    ff_ai_context_v2: bool = False
    ff_metric_calc_write: bool = False
    ff_g5_eval_gate: bool = False
    ff_ai_feedback: bool = False
    ff_eval_scheduler: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8848"]
    # 108号 P0-02/P0-03：发布原子化版本身份。由构建脚本注入，不得写死生产值。
    build_id: str = "dev-local"
    git_sha: str = ""
    frontend_build_id: str = ""
    snapshot_retention_days: int = 90
    event_retention_days: int = 365
    credential_encrypt_key: str = ""
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

    rbac_require_bound_token: bool = False
    env: str = "dev"
    ops_write_enabled: bool = False
    ops_write_d1_d5_confirmed: bool = False
    ops_write_confirmation_token: str = ""
    ops_approval_ui_enabled: bool = False

    # Medical dict push to HIS / JHEMR (plan 96): default off; single-row insert/stop only.
    dict_medical_push_enabled: bool = False
    dict_medical_production_approval_version: str = ""
    dict_medical_auto_approve_enabled: bool = False
    dict_medical_worker_interval_seconds: int = 5
    dict_medical_worker_batch_size: int = 10
    dict_medical_push_confirmation_token: str = ""
    dict_medical_push_default_hospital_no: str = "49557032X"
    dict_medical_his_source_code: str = "HIS_SOURCE"
    dict_medical_jhemr_source_code: str = "JHEMR_VASTBASE"
    # serial_no defaults to fail-closed and may only come from a DBA-whitelisted
    # sequence. MAX+1 allocation is prohibited even when a caller claims to be
    # the sole writer.
    jhemr_serial_whitelisted_sequence: str = ""

    # HIS identity sync to CDMS/JHEMR (plan 103/107): default OFF.
    identity_sync_enabled: bool = False
    # identity_sync_confirmation_token removed per plan 107: no confirmation token for nightly batches
    identity_sync_jhemr_hospital_no: str = "49557032X"
    identity_sync_cdms_credential_ref: str = "file:///etc/data-asset/credentials/cdms_identity_sync.write"
    identity_sync_jhemr_credential_ref: str = "file:///etc/data-asset/credentials/jhemr_identity_sync.write"
    identity_sync_cdms_host: str = "10.10.10.93"
    identity_sync_cdms_port: int = 1521
    identity_sync_cdms_service: str = "orcl"
    identity_sync_jhemr_host: str = "10.10.8.177"
    identity_sync_jhemr_port: int = 5432
    identity_sync_jhemr_dbname: str = "jhemr"
    identity_sync_lock_timeout_seconds: int = 300
    identity_sync_lookback_hours: int = 24
    identity_sync_managed_since: str = "2026-07-20"
    identity_sync_modified_since: str = "2026-08-04T00:00:00"

    # 126 P3: scheduled query runs — default OFF; enable only after explicit authorization.
    query_schedule_enabled: bool = False

    # Nightly scheduler (plan 107): default OFF until Phase D validation passes.
    identity_nightly_enabled: bool = False
    identity_nightly_cron: str = "0 2 * * *"  # 02:00 Asia/Shanghai
    identity_nightly_max_runtime_seconds: int = 3600
    identity_nightly_max_retries: int = 2
    identity_nightly_misfire_grace_seconds: int = 600
    # 122: one authoritative provider is declared by deployment.  The local
    # default is disabled; host cron and in-process APScheduler must not both
    # be treated as active.
    identity_scheduler_provider: str = "disabled"  # host_cron | systemd | apscheduler | disabled
    identity_scheduler_overdue_hours: int = 26
    identity_scheduler_heartbeat_seconds: int = 300

    # Circuit breaker thresholds (plan 107 §3)
    identity_cb_max_candidates: int = 200
    identity_cb_max_new: int = 50
    identity_cb_max_update: int = 100
    identity_cb_max_deactivate: int = 20
    identity_cb_max_change_ratio: float = 0.3
    # W10 方案 C（2026-08-29 用户授权）：JHEMR 现存用户首次纳管对齐不计入
    # max_new / max_change_ratio，单设上限防群体性误对齐（55 📌 熔断裁决项）。
    # 默认 150：须低于 max_candidates(200)，否则该维度不可达；当前批次 112 可过。
    identity_cb_max_align: int = 150
    # W10 二次修复（2026-08-30 用户授权选项1）：水位连续性阈值原写死 48h，
    # 连续失败后形成"失败→水位不推进→更失败"死锁；改为可配置以便恢复性
    # 运行临时放宽（方案 A 同款临时阈值先例），默认值保持 48 不变。
    identity_cb_max_watermark_gap_hours: int = 48
    identity_cb_max_failure_rate: float = 0.2
    identity_cb_consecutive_failure_limit: int = 3

    # HMAC account fingerprint key (from secret provider, never in code/git)
    identity_hmac_key_ref: str = "file:///etc/data-asset/credentials/identity_hmac.key"

    # JHEMR default password (from secret provider only, never in code/git)
    identity_jhemr_default_password_ref: str = "file:///etc/data-asset/credentials/jhemr_default_password"
    # 107 §5.2：SM4 算法经第二个受控账号交叉验证前，密码写入（及依赖密码的建号）保持关闭
    identity_jhemr_password_write_enabled: bool = False
    # CDMS default password template (from secret provider only)
    identity_cdms_default_password_ref: str = "file:///etc/data-asset/credentials/cdms_default_password"

    # 112 B2 fail-closed：CDMS FID/FUSER/FUPDATEUSER 语义未经活库/厂商证据确认
    # 前，任何 CDMS 写必须失败关闭；FTYPE 8/32 永远禁止写入。
    identity_cdms_fid_semantics_confirmed: bool = False
    identity_cdms_ftype_write_forbidden: bool = True
    # Phase D is a separate operational approval, not implied by enabling sync.
    identity_phase_d_approval_version: str = ""

    # Local account auth / JWT (59 号计划)
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
    auth_cookie_secure: bool = False
    auth_password_min_length: int = 8
    auth_password_max_length: int = 18
    auth_login_rate_limit: str = "5/minute"
    auth_refresh_rate_limit: str = "30/minute"
    rate_limit_enabled: bool = True

    # S5: internal Dify quality analysis is fail-closed by default.
    dify_quality_enabled: bool = False
    dify_base_url: str = "http://10.10.8.53/v1"
    dify_allowed_hosts: list[str] = ["10.10.8.53"]
    dify_quality_api_key_ref: str = "file:///etc/data-asset/credentials/dify_quality_workflow.api_key"
    dify_quality_workflow_name: str = "data-quality-control"
    dify_quality_prompt_version: str = "quality-control-v1"
    dify_connect_timeout_seconds: float = 3
    dify_read_timeout_seconds: float = 90
    dify_max_findings_per_job: int = 50
    dify_max_payload_bytes: int = 65536
    dify_max_response_bytes: int = 262144
    dify_stale_running_seconds: int = 600
    dify_tls_verify: bool = True
    dify_ca_bundle: str = ""

    # Hospital OpenAI-compatible chat: analysis/report only, never writes databases.
    hospital_llm_enabled: bool = True
    hospital_llm_base_url: str = "http://10.255.255.10:9000"
    hospital_llm_allowed_hosts: list[str] = ["10.255.255.10"]
    hospital_llm_api_key_ref: str = "file:///etc/data-asset/credentials/hospital_llm.api_key"
    hospital_llm_model: str = "deepseek-r1"
    hospital_llm_connect_timeout_seconds: float = 5
    hospital_llm_read_timeout_seconds: float = 90
    hospital_llm_max_tokens: int = 1800
    hospital_llm_max_payload_bytes: int = 24000
    hospital_llm_max_response_bytes: int = 131072


settings = Settings()
