import os
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"
HUGGINGFACE_RUNTIME_ENV_KEYS = (
    "HF_ENDPOINT",
    "HF_HOME",
    "SENTENCE_TRANSFORMERS_HOME",
)
_HUGGINGFACE_PATH_ENV_KEYS = {
    "HF_HOME",
    "SENTENCE_TRANSFORMERS_HOME",
}


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _read_env_file_values(keys: tuple[str, ...]) -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in keys:
            values[key] = _strip_env_value(value)
    return values


def _normalize_runtime_env_value(key: str, value: str) -> str:
    value = _strip_env_value(value)
    if key not in _HUGGINGFACE_PATH_ENV_KEYS or not value:
        return value

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return str(path)


def _apply_runtime_env_values(values: Mapping[str, str | None]) -> None:
    for key in HUGGINGFACE_RUNTIME_ENV_KEYS:
        value = values.get(key)
        if not value:
            continue

        current_value = os.environ.get(key, "").strip()
        if current_value:
            continue

        os.environ[key] = _normalize_runtime_env_value(key, value)


def apply_huggingface_runtime_environment() -> None:
    """Expose HF settings before OASIS imports Hugging Face dependencies."""
    values = _read_env_file_values(HUGGINGFACE_RUNTIME_ENV_KEYS)
    for key in HUGGINGFACE_RUNTIME_ENV_KEYS:
        if os.environ.get(key, "").strip():
            values[key] = os.environ[key]
    _apply_runtime_env_values(values)



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
    OASIS_DEFAULT_MODEL: str = "deepseek-v4-flash"
    OASIS_MEMORY_MODE: str = "upstream"
    OASIS_MAX_AGENTS: int = 1000
    OASIS_DB_PATH: str = "./data/simulations"
    OASIS_CONTEXT_TOKEN_LIMIT: int = 16384
    OASIS_TIMEOUT: int = 300  # 5 minutes
    OASIS_RETRY_COUNT: int = 3
    OASIS_DEFAULT_STEPS: int = 100
    OASIS_LONGTERM_ENABLED: bool = True
    OASIS_LONGTERM_CHROMA_PATH: str = "./data/memory/chroma"
    OASIS_LONGTERM_COLLECTION_PREFIX: str = "action_v1"
    OASIS_LONGTERM_EMBEDDING_BACKEND: str = "heuristic"
    OASIS_LONGTERM_EMBEDDING_MODEL: str | None = None
    OASIS_LONGTERM_EMBEDDING_API_KEY: str | None = None
    OASIS_LONGTERM_EMBEDDING_BASE_URL: str | None = None
    OASIS_LONGTERM_DELETE_COLLECTION_ON_CLOSE: bool = False

    # Hugging Face runtime settings used by OASIS recommendation models.
    HF_ENDPOINT: str | None = None
    HF_HOME: str | None = None
    SENTENCE_TRANSFORMERS_HOME: str | None = None

    # Persona LLM（须在 Settings 声明，Pydantic 才会从 .env 加载；避免仅读 os.environ 时误用默认模型名）
    OASIS_MODEL_PLATFORM: str | None = None
    OASIS_MODEL_TYPE: str | None = None
    OASIS_MODEL_URL: str | None = None
    OASIS_MODEL_URLS: str | None = None

    # OpenAI Settings (optional - for alternative LLM support)
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None

    # Baidu NLP Sentiment Settings
    BAIDU_APP_ID: str | None = None
    BAIDU_API_KEY: str | None = None
    BAIDU_SECRET_KEY: str | None = None

    # DeepSeek Settings (required for OASIS)
    DEEPSEEK_API_KEY: str = ""

    # Metrics Settings
    METRICS_CACHE_TTL: int = 0  # Cache disabled for development (set to 0)
    METRICS_MAX_CACHE_SIZE: int = 1000  # Maximum cache entries
    METRICS_CALCULATION_TIMEOUT: int = 60  # seconds
    METRICS_ENABLE_DB_PERSISTENCE: bool = True  # Enable/disable database persistence

    # Polarization LLM Settings
    POLARIZATION_LLM_MODEL: str = "deepseek-v4-flash"
    POLARIZATION_LLM_TEMPERATURE: float = 0.3
    POLARIZATION_BATCH_SIZE: int = 10  # agents per LLM batch
    POLARIZATION_CALCULATION_INTERVAL: int = 2  # Calculate every N steps

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=True,
        env_prefix="",
        extra="ignore",
    )

    def apply_runtime_environment(self) -> None:
        """Apply settings that third-party libraries read from os.environ."""
        _apply_runtime_env_values(
            {
                "HF_ENDPOINT": self.HF_ENDPOINT,
                "HF_HOME": self.HF_HOME,
                "SENTENCE_TRANSFORMERS_HOME": self.SENTENCE_TRANSFORMERS_HOME,
            }
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    settings = Settings()
    settings.apply_runtime_environment()
    return settings
