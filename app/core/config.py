import logging
import os
import secrets
from functools import lru_cache
from typing import ClassVar, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Follows secure configuration guidelines:
    - Never hardcodes production secrets in source code.
    - Uses ephemeral cryptographic keys for local development if not configured.
    - Fails safely in production if mandatory credentials are missing.
    """
    APP_NAME: str = "FindWorker"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Security: In production, SECRET_KEY must be provided via environment or AWS Secrets Manager.
    # In development/test, fallback to an ephemeral cryptographically secure token.
    SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Process-level persistent ephemeral key storage for dev/testing
    _ephemeral_jwt_secret: ClassVar[Optional[str]] = None

    # Database connection parameters
    DB_NAME: str = "findworker"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DATABASE_URL: Optional[str] = None

    # Redis connection parameter
    REDIS_URL: str = "redis://localhost:6379/0"

    def get_jwt_secret(self) -> str:
        """
        Returns the JWT secret key.
        If in production and SECRET_KEY is not set, raises a ValueError.
        If in development/testing, generates an ephemeral 256-bit cryptographic token
        that remains consistent for the lifetime of this process.
        """
        if self.SECRET_KEY:
            return self.SECRET_KEY
        if self.ENVIRONMENT.lower() == "production":
            raise ValueError(
                "CRITICAL SECURITY ERROR: SECRET_KEY environment variable is required in production!"
            )
        if not Settings._ephemeral_jwt_secret:
            Settings._ephemeral_jwt_secret = secrets.token_hex(32)
            # TODO(security): Ensure SECRET_KEY is set via AWS Secrets Manager in production.
            logger.warning(
                "SECRET_KEY not set. Generating ephemeral 256-bit cryptographic secret for development process. "
                "Tokens will remain valid for this process only."
            )
        return Settings._ephemeral_jwt_secret

    @property
    def effective_database_url(self) -> str:
        """
        Computes the effective database connection URL.
        Priority:
        1. Explicit DATABASE_URL (e.g. SQLite for dev or AWS RDS URL)
        2. PostgreSQL connection built from DB_* parameters if DB_PASSWORD is provided
        3. Local SQLite file fallback for effortless local testing
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if self.DB_PASSWORD:
            return (
                f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        # Local development fallback
        return "sqlite:///./findworker_dev.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
