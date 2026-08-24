import pytest
from backend.app.core.config import Settings, settings


def test_settings_load_defaults():
    """Verify that default system settings load correctly."""
    assert settings.PROJECT_NAME == "RecoverAI"
    assert settings.ENVIRONMENT in ["development", "production", "testing"]
    assert settings.DEFAULT_MAX_RECOVERY_AMOUNT == 50000.00
    assert settings.DEFAULT_MIN_ENRV_THRESHOLD == 0.15
    assert settings.DEFAULT_MAX_RECOVERY_ATTEMPTS == 3
    assert settings.DEFAULT_ATTRIBUTION_WINDOW_HOURS == 72
    assert settings.DEFAULT_COOLDOWN_HOURS == 24


def test_custom_settings_override(monkeypatch):
    """Verify that environment variables cleanly override default settings."""
    monkeypatch.setenv("PROJECT_NAME", "RecoverAI-Custom")
    monkeypatch.setenv("DEFAULT_MAX_RECOVERY_AMOUNT", "100000.00")
    monkeypatch.setenv("DEFAULT_MIN_ENRV_THRESHOLD", "0.20")
    
    custom_settings = Settings()
    assert custom_settings.PROJECT_NAME == "RecoverAI-Custom"
    assert custom_settings.DEFAULT_MAX_RECOVERY_AMOUNT == 100000.00
    assert custom_settings.DEFAULT_MIN_ENRV_THRESHOLD == 0.20


def test_database_url_settings():
    """Verify that database connection string settings format correctly."""
    assert settings.DATABASE_URL.startswith("postgresql")
    assert settings.SYNC_DATABASE_URL.startswith("postgresql")
