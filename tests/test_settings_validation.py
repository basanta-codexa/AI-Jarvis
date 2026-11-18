from ai_jarvis.config import settings


def test_env_number_parses_valid_values(monkeypatch):
    monkeypatch.setenv("AI_TEMPERATURE", "0.9")
    assert settings._env_number("AI_TEMPERATURE", 0.7, float) == 0.9

    monkeypatch.setenv("AI_MAX_TOKENS", "512")
    assert settings._env_number("AI_MAX_TOKENS", 600, int) == 512


def test_env_number_uses_default_for_garbage(monkeypatch):
    monkeypatch.setenv("AI_MAX_RETRIES", "not-a-number")
    assert settings._env_number("AI_MAX_RETRIES", 1, int) == 1


def test_env_number_uses_default_for_out_of_range(monkeypatch):
    monkeypatch.setenv("AI_TEMPERATURE", "99")
    assert settings._env_number(
        "AI_TEMPERATURE", 0.7, float, minimum=0.0, maximum=2.0
    ) == 0.7

    monkeypatch.setenv("AI_MAX_TOKENS", "-5")
    assert settings._env_number("AI_MAX_TOKENS", 600, int, minimum=1) == 600


def test_current_settings_are_sane_types():
    assert 0.0 <= settings.AI_TEMPERATURE <= 2.0
    assert settings.AI_MAX_TOKENS >= 1
    assert settings.AI_REQUEST_TIMEOUT >= 1.0
    assert settings.AI_MAX_RETRIES >= 0
    assert settings.AI_PROVIDER in settings._VALID_PROVIDERS
