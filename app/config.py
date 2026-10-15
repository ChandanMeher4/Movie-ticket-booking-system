"""Application configuration loaded from environment variables.

Centralizes all settings, database URLs, and LLM flags.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with defaults for local development."""

    app_env: str = "development"
    debug: bool = True
    port: int = 8000
    secret_key: str = "cineverse-dev-secret-key-32chars-minimum-length"

    # MySQL 8 Database Configuration
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "rootpassword"
    db_name: str = "movie_booking"
    database_url: Optional[str] = None

    # LLM Configuration (OpenAI-compatible)
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sync_database_url(self) -> str:
        """Return explicit database_url or construct MySQL connection string."""
        if self.database_url:
            return self.database_url
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
