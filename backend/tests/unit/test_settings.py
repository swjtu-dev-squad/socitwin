from pathlib import Path

from app.core.config import ENV_FILE, get_settings


def test_env_file_points_to_backend_root() -> None:
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent.name == "backend"


def test_get_settings_uses_backend_env_file_independent_of_cwd() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert Path(ENV_FILE).exists()
    assert isinstance(settings.DEEPSEEK_API_KEY, str)
    assert settings.DEEPSEEK_API_KEY != ""
