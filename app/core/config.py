from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "OHS Management API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "local"

    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "ohs"
    POSTGRES_PASSWORD: str = "ohs"
    POSTGRES_DB: str = "ohs"
    DATABASE_URL: Optional[str] = None

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    UPLOAD_DIR: str = "uploads"
    ATTACHMENT_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 25
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "no-reply@ohs.local"
    SMTP_USE_TLS: bool = False
    SMS_ENABLED: bool = False
    SMS_PROVIDER_NAME: str = "noop"
    SCHEDULER_ENABLED: bool = False
    SCHEDULER_POLL_SECONDS: int = 3600
    PERMIT_EXPIRY_WARNING_DAYS: int = 90

    BACKEND_CORS_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, value: Optional[str], info: Any) -> str:
        if value:
            return value
        data = info.data
        return (
            f"postgresql+psycopg://{data.get('POSTGRES_USER')}:{data.get('POSTGRES_PASSWORD')}"
            f"@{data.get('POSTGRES_SERVER')}:{data.get('POSTGRES_PORT')}/{data.get('POSTGRES_DB')}"
        )

    @property
    def upload_root_path(self) -> Path:
        upload_path = Path(self.UPLOAD_DIR)
        if upload_path.is_absolute():
            return upload_path
        return Path(__file__).resolve().parents[2] / upload_path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
