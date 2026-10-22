"""Application configuration loaded from environment variables.

Centralizes all settings, database URLs, and LLM flags.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with defaults for local development."""

    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "app_env"))
    debug: bool = Field(default=True, validation_alias=AliasChoices("DEBUG", "debug"))
    port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "port"))
    secret_key: str = Field(
        default="cineverse-dev-secret-key-32chars-minimum-length",
        validation_alias=AliasChoices("SECRET_KEY", "secret_key"),
    )

    # MySQL 8 Database Configuration & Aliases
    db_host: str = Field(default="localhost", validation_alias=AliasChoices("DATABASE_HOST", "DB_HOST", "db_host"))
    db_port: int = Field(default=3306, validation_alias=AliasChoices("DATABASE_PORT", "DB_PORT", "db_port"))
    db_user: str = Field(default="cineverse", validation_alias=AliasChoices("DATABASE_USER", "DB_USER", "db_user"))
    db_password: str = Field(
        default="cineverse_secret",
        validation_alias=AliasChoices("DATABASE_PASSWORD", "DB_PASSWORD", "db_password"),
    )
    db_name: str = Field(
        default="movie_ticket_booking",
        validation_alias=AliasChoices("DATABASE_NAME", "DB_NAME", "db_name"),
    )
    database_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # LLM Configuration (OpenAI-compatible)
    llm_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("LLM_API_KEY", "llm_api_key"))
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "llm_base_url"),
    )
    llm_model: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("LLM_MODEL", "llm_model"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sync_database_url(self) -> str:
        """Return explicit database_url or construct MySQL connection string with SQLite fallback."""
        if self.database_url:
            return self.database_url

        # If in Docker or DB host was explicitly specified as non-localhost
        has_explicit_db_env = any(
            k in os.environ for k in ("DATABASE_HOST", "DB_HOST", "DATABASE_NAME", "DB_NAME", "DATABASE_URL")
        )
        if self.db_host != "localhost" or has_explicit_db_env:
            return (
                f"mysql+pymysql://{self.db_user}:{self.db_password}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}"
            )

        # If local pre-seeded SQLite database exists, use it for zero-config offline execution
        sqlite_file = Path("cineverse_dev.db")
        if sqlite_file.exists():
            return f"sqlite:///{sqlite_file.resolve().as_posix()}"

        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def is_mock_llm(self) -> bool:
        """Return True if LLM should run in offline deterministic mock mode."""
        if not self.llm_api_key:
            return True
        cleaned = self.llm_api_key.strip().lower()
        return cleaned in ("", "mock", "dummy", "test", "none")


settings = Settings()
