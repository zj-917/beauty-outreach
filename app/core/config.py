"""Application settings loaded from environment variables or a .env file."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security import PhoneCipher


class ConfigurationError(RuntimeError):
    """Raised when required environment configuration is missing or invalid."""


class Settings(BaseSettings):
    """Runtime configuration; secrets must be provided by the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = "sqlite:///./data/app.db"
    admin_token: str = Field(min_length=1)
    phone_enc_key: str = Field(min_length=1)
    phone_hash_key: str = Field(min_length=1)
    webhook_secret: str = Field(min_length=1)

    messenger_provider: Literal["mock", "whatsapp_cloud"] = "mock"
    worker_enabled: bool = True
    tick_seconds: float = Field(default=1.0, gt=0)
    demo_mode: bool = True
    seed_defaults: bool = False
    log_level: str = "INFO"


def validate_runtime_settings(settings: Settings) -> None:
    """Validate values Pydantic cannot express, naming the offending variable."""
    try:
        PhoneCipher(settings.phone_enc_key, settings.phone_hash_key)
    except ValueError as exc:
        raise ConfigurationError("PHONE_ENC_KEY is not a valid Fernet key") from exc


def load_settings() -> Settings:
    """Load settings, converting Pydantic failures into named configuration errors."""
    try:
        settings = Settings()
    except ValidationError as exc:
        names = sorted(
            {
                str(error["loc"][0]).upper()
                for error in exc.errors()
                if error.get("loc")
            }
        )
        detail = ", ".join(names) if names else "unknown variables"
        raise ConfigurationError(
            f"Missing or invalid environment variables: {detail}"
        ) from exc
    validate_runtime_settings(settings)
    return settings
