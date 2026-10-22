"""Timezone helpers for Nepal Time (NPT, UTC+05:45)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    NPT = ZoneInfo("Asia/Kathmandu")
except ZoneInfoNotFoundError:
    NPT = timezone(timedelta(hours=5, minutes=45), name="NPT")

UTC = timezone.utc


def to_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, treating naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


def npt_now() -> datetime:
    return datetime.now(NPT)


def npt_date(value: datetime | None = None) -> str:
    """Return the calendar date in Nepal as YYYY-MM-DD."""
    instant = to_utc(value) if value is not None else now_utc()
    return instant.astimezone(NPT).date().isoformat()


def format_npt(value: datetime) -> str:
    """Format an instant for display in Nepal Time."""
    return to_utc(value).astimezone(NPT).strftime("%d %b %Y, %H:%M NPT")


def email_subject(value: datetime) -> str:
    """Build the exact daily subject line using the NPT date."""
    local = to_utc(value).astimezone(NPT)
    return f"Nepal Morning Brief, {local.strftime('%A')}, {local.strftime('%d %b %Y')}"
