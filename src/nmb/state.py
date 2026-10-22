"""Idempotency state for one digest per Nepal calendar day."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .timeutil import NPT, now_utc, npt_date, to_utc


class StateError(RuntimeError):
    """Raised when the state file is unreadable or malformed."""


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError(f"Could not read state file {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise StateError(f"State file {self.path} must contain a JSON object")
        return data

    def last_sent_date(self) -> str | None:
        value = self.read().get("last_sent_date")
        return value if isinstance(value, str) and value else None

    def already_sent_today(self, now: datetime | None = None) -> bool:
        return self.last_sent_date() == npt_date(now)

    def mark_sent(self, now: datetime | None = None) -> str:
        instant = to_utc(now) if now is not None else now_utc()
        date_value = npt_date(instant)
        payload = {
            "last_sent_date": date_value,
            "last_sent_at": instant.astimezone(NPT).isoformat(timespec="seconds"),
            "timezone": "Asia/Kathmandu",
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(temp_path, self.path)
        except OSError as exc:
            raise StateError(f"Could not write state file {self.path}: {exc}") from exc
        return date_value
