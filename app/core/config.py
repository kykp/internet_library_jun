from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Настройки приложения — загружаются из окружения и/или .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # server
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_env: str = "development"
    cors_origins: str = "http://localhost:8000"

    # owner
    owner_email: EmailStr = "owner@example.com"
    owner_name: str = "Site owner"

    # smtp
    smtp_host: str = "smtp.yandex.ru"
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # rate limit
    rate_limit_max: int = Field(default=5, ge=1)
    rate_limit_window_seconds: int = Field(default=600, ge=1)

    # ai
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str = "http://localhost:8000"
    openrouter_app_title: str = "Developer Landing"
    ai_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # email via HTTP (Resend) — приоритетнее SMTP на хостингах, режущих порты
    resend_api_key: str = ""
    resend_from: str = "onboarding@resend.dev"

    # storage
    storage_dir: str = str(BASE_DIR / "storage")

    # Значения из окружения часто прилетают с лидирующим/трейлинг пробелом
    # (копипаст в UI хостинга), а httpx не пропускает пробел в заголовках.
    @field_validator(
        "cors_origins",
        "openrouter_api_key",
        "openrouter_base_url",
        "openrouter_referer",
        "openrouter_app_title",
        "resend_api_key",
        "resend_from",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        mode="before",
    )
    @classmethod
    def _strip_ws(cls, v):
        return v.strip() if isinstance(v, str) else v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in ("dev", "development", "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
