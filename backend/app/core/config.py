from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEV_EMBED_EXTERNAL_TOKEN_SECRET = "dev-industrial-embed-token-secret-change-me"
PRODUCTION_ENVIRONMENTS = frozenset({"prod", "production"})
PRODUCTION_EMBED_SECRET_MIN_LENGTH = 32
INSECURE_EMBED_SECRET_VALUES = frozenset(
    {
        DEV_EMBED_EXTERNAL_TOKEN_SECRET,
        "change-me-to-industrial-embed-token-secret",
    }
)
INSECURE_EMBED_SECRET_MARKERS = ("change-me", "changeme", "dev-", "dev_", "example", "placeholder")


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
    # 官网嵌入配置
    embed_enabled: bool = True
    embed_external_token_secret: str = Field(default=DEV_EMBED_EXTERNAL_TOKEN_SECRET, min_length=16)
    embed_external_token_issuer: str = "industrial-internet-mock"
    embed_external_token_audience: str = "agenthub"
    embed_session_expire_minutes: int = 10
    embed_session_cookie_name: str = "agenthub_embed_session"
    embed_cookie_secure: bool = False
    embed_cookie_samesite: str = "lax"
    embed_cookie_domain: str | None = None
    embed_default_agent_code: str = "qa"
    embed_default_org_name: str = "官网嵌入用户"
    embed_allowed_parent_origins: str | None = None
    # Dify 集成配置
    dify_base_url: str | None = None
    dify_api_key: str | None = None
    # 火山引擎语音配置（新版控制台，使用 X-Api-Key）
    volc_audio_api_key: str | None = None
    volc_asr_ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
    volc_asr_resource_id: str = "volc.bigasr.sauc.duration"
    volc_asr_audio_format: str = "pcm"
    volc_asr_sample_rate: int = 16000
    volc_asr_language: str = "zh-CN"
    volc_tts_ws_url: str = "wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream"
    volc_tts_resource_id: str = "seed-tts-2.0"
    volc_tts_speaker: str | None = None
    volc_tts_audio_format: str = "mp3"
    volc_tts_sample_rate: int = 24000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def embed_allowed_parent_origin_list(self) -> list[str]:
        if not self.embed_allowed_parent_origins:
            return []
        return [
            origin.strip()
            for origin in self.embed_allowed_parent_origins.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def validate_production_embed_secrets(self) -> "Settings":
        if self.environment.strip().lower() not in PRODUCTION_ENVIRONMENTS or not self.embed_enabled:
            return self

        _validate_production_embed_secret(
            "EMBED_EXTERNAL_TOKEN_SECRET",
            self.embed_external_token_secret,
        )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _validate_production_embed_secret(name: str, value: str) -> None:
    normalized = value.strip()
    if normalized in INSECURE_EMBED_SECRET_VALUES:
        raise ValueError(f"{name} must be changed from the public development placeholder")
    if len(normalized) < PRODUCTION_EMBED_SECRET_MIN_LENGTH:
        raise ValueError(
            f"{name} must be at least {PRODUCTION_EMBED_SECRET_MIN_LENGTH} characters "
            "in production"
        )
    lowered = normalized.lower()
    if any(marker in lowered for marker in INSECURE_EMBED_SECRET_MARKERS):
        raise ValueError(f"{name} must not contain placeholder text in production")
