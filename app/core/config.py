"""Application settings loaded from environment variables or a .env file."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    log_level: str = "INFO"
