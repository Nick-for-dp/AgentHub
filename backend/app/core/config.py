from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import DeploymentProfile


DEV_EMBED_EXTERNAL_TOKEN_SECRET = "dev-industrial-embed-token-secret-change-me"
DEV_API_KEY_SIGNING_SECRET = "dev-only-change-me-please"
DEV_AUTH_TOKEN_SECRET = "dev-auth-secret-change-me-please"
PRODUCTION_ENVIRONMENTS = frozenset({"prod", "production"})
PRODUCTION_EMBED_SECRET_MIN_LENGTH = 32
INSECURE_EMBED_SECRET_VALUES = frozenset(
    {
        DEV_EMBED_EXTERNAL_TOKEN_SECRET,
        DEV_API_KEY_SIGNING_SECRET,
        DEV_AUTH_TOKEN_SECRET,
        "change-me-to-industrial-embed-token-secret",
    }
)
INSECURE_EMBED_SECRET_MARKERS = ("change-me", "changeme", "dev-", "dev_", "example", "placeholder")


class Settings(BaseSettings):
    app_name: str = "AgentHub"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = False
    deployment_profile: DeploymentProfile = DeploymentProfile.EXTERNAL
    api_v1_prefix: str = "/api/v1"
    server_host: str = "0.0.0.0"
    server_port: int = 8240
    database_url: str = "mysql+pymysql://agenthub:agenthub@localhost:3306/agenthub?charset=utf8mb4"
    # 单元测试使用的独立数据库；必须与开发/生产库分开，测试会反复建表删表。
    # 必须在 .env 显式配置 TEST_DATABASE_URL；未配置时运行测试会直接报错，避免误连业务库。
    test_database_url: str | None = None
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
    # 普通 API CORS 与 iframe parent origin 是两套安全边界，不能复用配置。
    cors_allowed_origins: str | None = None
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
    # 合同审查正式 workflow 的 Agent 级 Dify API Key。
    # 本字段只用于初始化/更新 contract-review Agent 的 config_snapshot，不进入 Dify inputs。
    contract_review_dify_api_key: str | None = None
    # 兼容昨天全文实验 workflow 的本地配置；正式配置为空时 seed 可临时回退使用。
    contract_review_full_context_dify_api_key: str | None = None
    contract_review_block_loop_dify_api_key: str | None = None
    # MinIO / S3 兼容对象存储配置
    object_storage_endpoint: str | None = None
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_region: str = "us-east-1"
    object_storage_bucket_raw: str = "int-agenthub-raw"
    object_storage_bucket_parsed: str = "int-agenthub-parsed"
    object_storage_presign_expires_seconds: int = 900
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

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        """解析普通 API CORS origin 白名单。

        该配置只用于浏览器跨域 API 访问，不控制 iframe 是否允许被父页面嵌入。
        iframe 的父页面白名单必须继续使用 ``EMBED_ALLOWED_PARENT_ORIGINS``。
        """
        if not self.cors_allowed_origins:
            return []
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """生产环境强校验关键密钥，禁止使用公开默认值或带占位标记的弱密钥。

        覆盖签发 API Key、登录 token 以及（启用嵌入时）产业互联网 embed 验签密钥，
        避免生产误用代码内置的开发默认值导致凭证可被伪造。
        """
        if self.environment.strip().lower() not in PRODUCTION_ENVIRONMENTS:
            return self

        _validate_production_secret("API_KEY_SIGNING_SECRET", self.api_key_signing_secret)
        _validate_production_secret("AUTH_TOKEN_SECRET", self.auth_token_secret)
        if self.embed_enabled:
            _validate_production_secret(
                "EMBED_EXTERNAL_TOKEN_SECRET",
                self.embed_external_token_secret,
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _validate_production_secret(name: str, value: str) -> None:
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
