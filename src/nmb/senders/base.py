"""Delivery interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Digest


class SenderError(RuntimeError):
    """Raised when a sender cannot deliver the digest."""


class Sender(ABC):
    name: str

    @abstractmethod
    def send(self, subject: str, text_body: str, html_body: str, digest: Digest) -> None:
        """Deliver the rendered digest. Raise SenderError on failure."""
