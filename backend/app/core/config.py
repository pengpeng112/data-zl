from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    db_url: str = "postgresql+psycopg://asset_app:admin123@10.20.1.153:5432/data_asset"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8848"]
    # 数据生命周期（P5.9-T14）
    snapshot_retention_days: int = 90
    event_retention_days: int = 365
    # 凭据加密密钥（P5.9-T5）
    credential_encrypt_key: str = ""
    # APScheduler 时区
    scheduler_timezone: str = "Asia/Shanghai"


settings = Settings()
