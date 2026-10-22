import smtplib
from datetime import datetime

import pytest

from nmb.env import ConfigurationError, require_gmail_env
from nmb.models import Digest
from nmb.senders.gmail_smtp import GmailSmtpSender
from nmb.timeutil import UTC, email_subject


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.messages = []
        self.logged_in = False
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message):
        self.messages.append(message)


def _sender(factory=FakeSMTP) -> GmailSmtpSender:
    return GmailSmtpSender(
        user="sender@example.com",
        app_password="app-password",
        recipient="you@example.com",
        smtp_factory=factory,
        sleep_func=lambda _: None,
    )


def test_message_builder_sets_headers_and_both_parts():
    sender = _sender()
    subject = email_subject(datetime(2026, 10, 21, 18, 15, tzinfo=UTC))
    message = sender.build_message(subject, "Plain body", "<p>HTML body</p>")

    assert subject == "Nepal Morning Brief, Thursday, 22 Oct 2026"
    assert message["From"] == "Nepal Morning Brief <sender@example.com>"
    assert message["To"] == "you@example.com"
    assert message["Subject"] == subject
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == "Plain body"
    assert "HTML body" in message.get_body(preferencelist=("html",)).get_content()


def test_gmail_sender_connects_with_ssl_and_sends():
    FakeSMTP.instances.clear()
    sender = _sender()
    digest = Digest(generated_at=datetime(2026, 10, 21, 18, 15, tzinfo=UTC), sections=[])

    sender.send("Subject", "Text", "<p>HTML</p>", digest)

    assert len(FakeSMTP.instances) == 1
    instance = FakeSMTP.instances[0]
    assert instance.args == ("smtp.gmail.com", 465)
    assert instance.logged_in == ("sender@example.com", "app-password")
    assert len(instance.messages) == 1


def test_transient_smtp_failure_is_retried():
    attempts = []

    def factory(*args, **kwargs):
        class RetrySMTP(FakeSMTP):
            def send_message(self, message):
                attempts.append(message)
                if len(attempts) == 1:
                    raise smtplib.SMTPServerDisconnected("try again")

        return RetrySMTP(*args, **kwargs)

    sender = _sender(factory=factory)
    digest = Digest(generated_at=datetime(2026, 10, 21, 18, 15, tzinfo=UTC), sections=[])
    sender.send("Subject", "Text", "<p>HTML</p>", digest)
    assert len(attempts) == 2


def test_authentication_failure_is_not_retried():
    calls = []

    def factory(*args, **kwargs):
        class AuthSMTP(FakeSMTP):
            def login(self, user, password):
                raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

        calls.append(1)
        return AuthSMTP(*args, **kwargs)

    sender = _sender(factory=factory)
    digest = Digest(generated_at=datetime(2026, 10, 21, 18, 15, tzinfo=UTC), sections=[])
    with pytest.raises(Exception) as exc_info:
        sender.send("Subject", "Text", "<p>HTML</p>", digest)
    message = str(exc_info.value)
    assert "Gmail rejected authentication" in message
    assert "you@example.com" not in message
    assert "app-password" not in message
    assert len(calls) == 1


def test_missing_env_var_has_clear_error(monkeypatch):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        require_gmail_env()
    assert "GMAIL_USER" in str(exc_info.value)
