import pytest

from nmb.config import Settings
from nmb.env import ConfigurationError, validate_run_env


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "senders": ["gmail_smtp"],
            "sections": [{"id": "nepal", "name": "Nepal", "count": 10}],
        }
    )


def test_missing_gemini_key_fails_fast(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_run_env(_settings())
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_missing_gmail_env_fails_fast_for_send(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_run_env(_settings())
    assert "GMAIL_USER" in str(exc_info.value)


def test_dry_run_only_needs_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)
    assert validate_run_env(_settings(), dry_run=True) == "key"
