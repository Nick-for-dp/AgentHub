from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentHub"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    server_host: str = "0.0.0.0"
    server_port: int = 8240
    database_url: str = "postgresql+psycopg://agenthub:agenthub@localhost:5432/agenthub"
    redis_url: str = "redis://localhost:6379/0"
    api_key_signing_secret: str = Field(default="dev-only-change-me-please", min_length=16)
    # 登录态配置
    auth_token_secret: str = Field(default="dev-auth-secret-change-me-please", min_length=32)
    auth_token_issuer: str = "agenthub"
    auth_cookie_name: str = "agenthub_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str | None = None
    access_token_expire_minutes: int = 20
    session_idle_expire_minutes: int = 60
    session_id_bytes: int = 32
    refresh_token_expire_days: int = 7
    conversation_inactive_hours: int = 24
    # Dify 集成配置
    dify_base_url: str | None = None
    dify_api_key: str | None = None
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
