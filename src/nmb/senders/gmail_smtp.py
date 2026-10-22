"""Gmail SMTP delivery using a Google App Password."""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from ..logging_utils import redact
from ..models import Digest
from .base import Sender, SenderError

logger = logging.getLogger(__name__)


class GmailSmtpSender(Sender):
    name = "gmail_smtp"
    host = "smtp.gmail.com"
    port = 465
    max_attempts = 3

    def __init__(
        self,
        *,
        user: str,
        app_password: str,
        recipient: str,
        from_name: str = "Nepal Morning Brief",
        smtp_factory=smtplib.SMTP_SSL,
        sleep_func=time.sleep,
    ) -> None:
        self.user = user
        self.app_password = app_password
        self.recipient = recipient
        self.from_name = from_name
        self.smtp_factory = smtp_factory
        self.sleep_func = sleep_func

    def _redact(self, value: str) -> str:
        return redact(value, [self.user, self.app_password, self.recipient])

    def build_message(self, subject: str, text_body: str, html_body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((self.from_name, self.user))
        message["To"] = self.recipient
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=False)
        message.set_content(text_body, charset="utf-8")
        message.add_alternative(html_body, subtype="html", charset="utf-8")
        return message

    def send(self, subject: str, text_body: str, html_body: str, digest: Digest) -> None:
        message = self.build_message(subject, text_body, html_body)
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                context = ssl.create_default_context()
                with self.smtp_factory(self.host, self.port, timeout=30, context=context) as smtp:
                    smtp.login(self.user, self.app_password)
                    smtp.send_message(message)
                logger.info(
                    "sender.sent",
                    extra={"data": {"sender": self.name, "subject": subject}},
                )
                return
            except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused) as exc:
                detail = self._redact(f"{type(exc).__name__}: {exc}")
                raise SenderError(
                    "Gmail rejected authentication or the recipient. "
                    "Check GMAIL_USER, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL. "
                    f"Detail: {detail}"
                ) from None
            except (smtplib.SMTPException, OSError) as exc:
                last_error = exc
                logger.warning(
                    "sender.retry",
                    extra={
                        "data": {
                            "sender": self.name,
                            "attempt": attempt,
                            "max_attempts": self.max_attempts,
                            "error": self._redact(f"{type(exc).__name__}: {exc}")[:300],
                        }
                    },
                )
                if attempt < self.max_attempts:
                    self.sleep_func(2 ** (attempt - 1))

        detail = self._redact(
            f"{type(last_error).__name__}: {last_error}" if last_error else "unknown error"
        )
        raise SenderError(f"Gmail SMTP failed after {self.max_attempts} attempts: {detail}")
