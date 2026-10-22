"""Environment validation. Errors name variables but never print their values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from email.utils import parseaddr

from .config import Settings


class ConfigurationError(RuntimeError):
    """Raised when required environment variables are missing or invalid."""


@dataclass(frozen=True, slots=True)
class GmailEnv:
    user: str
    app_password: str
    recipient: str


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"Missing required environment variable {name}. "
            "See README.md for the GitHub Secrets setup."
        )
    return value


def require_gemini_key() -> str:
    return require_env("GEMINI_API_KEY")


def require_gmail_env() -> GmailEnv:
    user = require_env("GMAIL_USER")
    app_password = require_env("GMAIL_APP_PASSWORD")
    recipient = require_env("RECIPIENT_EMAIL")

    parsed_user = parseaddr(user)[1]
    parsed_recipient = parseaddr(recipient)[1]
    if "@" not in parsed_user:
        raise ConfigurationError("GMAIL_USER must be a valid email address")
    if "@" not in parsed_recipient:
        raise ConfigurationError("RECIPIENT_EMAIL must be a valid email address")

    return GmailEnv(user=parsed_user, app_password=app_password, recipient=parsed_recipient)


def validate_run_env(settings: Settings, *, dry_run: bool = False) -> str:
    """Validate variables needed for a normal (or dry) digest run."""
    gemini_key = require_gemini_key()
    if not dry_run and "gmail_smtp" in settings.senders:
        require_gmail_env()
    return gemini_key
