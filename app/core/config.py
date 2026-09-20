from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_cors_origins: str = "*"
    app_max_request_bytes: int = Field(default=131072, ge=1024, le=1048576)
    app_rate_limit_requests: int = Field(default=20, ge=1, le=10000)
    app_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    app_trust_proxy_headers: bool = False
    app_device_hash_secret: str = "change-this-in-production"
    app_access_token_secret: str = "change-this-access-token-secret-in-production"
    app_access_token_minutes: int = Field(default=30, ge=5, le=1440)
    app_refresh_token_days: int = Field(default=30, ge=1, le=365)
    app_email_token_minutes: int = Field(default=30, ge=5, le=1440)
    app_media_root: str = "media"
    app_avatar_max_bytes: int = Field(default=2097152, ge=65536, le=10485760)
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/zhaoxingzhai"

    ai_base_url: str = "https://api.siliconflow.cn/v1"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = Field(default=90, ge=1, le=120)
    ai_temperature: float = Field(default=0.4, ge=0, le=1)

    @field_validator("ai_base_url")
    @classmethod
    def normalize_ai_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.app_cors_origins.split(",") if item.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key.strip() and self.ai_model.strip() and self.ai_base_url)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from_email.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
