"""Small JSON logging helper with explicit, structured run events."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Iterable

from .timeutil import UTC


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        data = getattr(record, "data", None)
        if isinstance(data, dict):
            payload.update(data)
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def redact(value: str, secrets: Iterable[str | None]) -> str:
    """Remove sensitive values from text that is about to be logged."""
    result = value
    for secret in secrets:
        if secret and len(secret) >= 3:
            result = result.replace(secret, "[REDACTED]")
    return result
