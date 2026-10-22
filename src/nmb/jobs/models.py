"""Job listing objects used by the weekly digest."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..timeutil import NPT, format_npt, to_utc


def _number(value: float | None) -> str | None:
    if value is None:
        return None
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _currency_label(value: str | None) -> str:
    text = (value or "NPR").strip()
    if text.lower().replace(".", "") in {"nrs", "npr", "rs", "rs."}:
        return "NPR"
    return text


@dataclass(slots=True)
class JobListing:
    id: str
    title: str
    url: str
    company: str
    level: str
    experience: str
    location: str
    posted_at: datetime
    deadline: datetime | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str
    salary_unit: str
    salary_hidden: bool
    skills: list[str] = field(default_factory=list)
    source_name: str = "MeroJob"

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split())
        self.company = " ".join(self.company.split())
        self.level = " ".join(self.level.split())
        self.experience = " ".join(self.experience.split())
        self.location = " ".join(self.location.split())
        self.url = self.url.strip()
        self.posted_at = to_utc(self.posted_at)
        if self.deadline is not None:
            self.deadline = to_utc(self.deadline)

    @property
    def salary_label(self) -> str:
        if self.salary_hidden or (self.salary_min is None and self.salary_max is None):
            return "Not disclosed"
        currency = _currency_label(self.salary_currency)
        unit_key = self.salary_unit.strip().lower()
        unit_name = {
            "monthly": "month",
            "month": "month",
            "yearly": "year",
            "year": "year",
            "daily": "day",
            "day": "day",
            "hourly": "hour",
            "hour": "hour",
        }.get(unit_key, unit_key)
        unit = f"/{unit_name}" if unit_name else ""
        minimum = _number(self.salary_min)
        maximum = _number(self.salary_max)
        if minimum and maximum:
            if self.salary_min == self.salary_max:
                return f"{currency} {minimum}{unit}"
            return f"{currency} {minimum}–{maximum}{unit}"
        if minimum:
            return f"From {currency} {minimum}{unit}"
        return f"Up to {currency} {maximum}{unit}"

    @property
    def salary_ceiling(self) -> float | None:
        if self.salary_max is not None:
            return self.salary_max
        return self.salary_min

    @property
    def salary_is_known(self) -> bool:
        return not self.salary_hidden and (
            self.salary_min is not None or self.salary_max is not None
        )

    @property
    def skills_label(self) -> str:
        return ", ".join(self.skills[:8])

    @property
    def deadline_label(self) -> str:
        if self.deadline is None:
            return "Not stated"
        return self.deadline.astimezone(NPT).strftime("%d %b %Y")

    @property
    def posted_label(self) -> str:
        return self.posted_at.astimezone(NPT).strftime("%d %b %Y")

    def npt_posted(self) -> str:
        return format_npt(self.posted_at)
