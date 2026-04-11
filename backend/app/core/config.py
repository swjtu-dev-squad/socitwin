from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Socitwin Backend"

    # CORS Settings
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]

    # Database Settings (if needed later)
    DATABASE_URL: str = "sqlite:///./socitwin.db"

    # Simulation Settings
    SIMULATION_MAX_AGENTS: int = 1000
    SIMULATION_DEFAULT_STEPS: int = 100

    # OASIS Settings
    OASIS_DEFAULT_PLATFORM: str = "twitter"
    OASIS_DEFAULT_MODEL: str = "gpt-4o-mini"
    OASIS_MAX_AGENTS: int = 1000
    OASIS_DB_PATH: str = "./data/simulations"
    OASIS_TIMEOUT: int = 300  # 5 minutes
    OASIS_RETRY_COUNT: int = 3
    OASIS_DEFAULT_STEPS: int = 100

    # OpenAI Settings (optional - for alternative LLM support)
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None

    # DeepSeek Settings (required for OASIS)
    DEEPSEEK_API_KEY: str

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_prefix=""
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
