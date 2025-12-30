"""
Application configuration using pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"

    # Environment
    environment: str = "development"
    debug: bool = True

    # API
    api_v1_prefix: str = "/api/v1"
    project_name: str = "CHALDEAS"

    # AI Keys (for SHEBA/LOGOS)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # CORS - CHALDEAS uses port 5100 for frontend
    backend_cors_origins: list[str] = [
        "http://localhost:5100",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
