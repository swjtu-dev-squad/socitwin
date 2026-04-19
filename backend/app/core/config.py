from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Persona LLM（须在 Settings 声明，Pydantic 才会从 .env 加载；避免仅读 os.environ 时误用默认模型名）
    OASIS_MODEL_PLATFORM: str | None = None
    OASIS_MODEL_TYPE: str | None = None
    OASIS_MODEL_URL: str | None = None
    OASIS_MODEL_URLS: str | None = None

    # OpenAI Settings (optional - for alternative LLM support)
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None

    # DeepSeek Settings (required for OASIS)
    DEEPSEEK_API_KEY: str = ""

    # Metrics Settings
    METRICS_CACHE_TTL: int = 0  # Cache disabled for development (set to 0)
    METRICS_MAX_CACHE_SIZE: int = 1000  # Maximum cache entries
    METRICS_CALCULATION_TIMEOUT: int = 60  # seconds
    METRICS_ENABLE_DB_PERSISTENCE: bool = True  # Enable/disable database persistence

    # Polarization LLM Settings
    POLARIZATION_LLM_MODEL: str = "deepseek-chat"
    POLARIZATION_LLM_TEMPERATURE: float = 0.3
    POLARIZATION_BATCH_SIZE: int = 10  # agents per LLM batch
    POLARIZATION_CALCULATION_INTERVAL: int = 2  # Calculate every N steps

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_prefix="",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
