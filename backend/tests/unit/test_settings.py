import os
from pathlib import Path

from app.core.config import BACKEND_ROOT, ENV_FILE, Settings, get_settings


def test_env_file_points_to_backend_root() -> None:
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent.name == "backend"


def test_get_settings_uses_backend_env_file_independent_of_cwd() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert Path(ENV_FILE).exists()
    assert isinstance(settings.DEEPSEEK_API_KEY, str)
    assert settings.DEEPSEEK_API_KEY != ""


def test_settings_exports_huggingface_runtime_env(monkeypatch) -> None:
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("SENTENCE_TRANSFORMERS_HOME", raising=False)

    settings = Settings(
        DEEPSEEK_API_KEY="test-key",
        HF_ENDPOINT="https://hf-mirror.com",
        HF_HOME="./data/huggingface",
        SENTENCE_TRANSFORMERS_HOME="./data/huggingface/sentence-transformers",
    )

    settings.apply_runtime_environment()

    assert os.environ["HF_ENDPOINT"] == "https://hf-mirror.com"
    assert os.environ["HF_HOME"] == str(BACKEND_ROOT / "data/huggingface")
    assert os.environ["SENTENCE_TRANSFORMERS_HOME"] == str(
        BACKEND_ROOT / "data/huggingface/sentence-transformers"
    )
