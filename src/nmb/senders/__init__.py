"""Sender factory."""

from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..env import require_gmail_env
from .base import Sender, SenderError
from .file import FileSender
from .gmail_smtp import GmailSmtpSender


def build_senders(settings: Settings, project_root: Path) -> list[Sender]:
    senders: list[Sender] = []
    for name in settings.senders:
        if name == "gmail_smtp":
            credentials = require_gmail_env()
            senders.append(
                GmailSmtpSender(
                    user=credentials.user,
                    app_password=credentials.app_password,
                    recipient=credentials.recipient,
                    from_name=settings.email.from_name,
                )
            )
        elif name == "file":
            senders.append(
                FileSender(
                    output_dir=project_root / settings.file_sender.output_dir,
                    site_url=settings.file_sender.site_url,
                )
            )
        else:
            raise SenderError(f"Unsupported sender: {name}")
    return senders


__all__ = ["FileSender", "GmailSmtpSender", "Sender", "SenderError", "build_senders"]
