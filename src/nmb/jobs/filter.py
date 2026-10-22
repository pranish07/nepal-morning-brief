"""Filter and rank MeroJob listings for the weekly email."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from ..timeutil import to_utc
from .config import JobsConfig
from .models import JobListing

_LEVEL_RANK = {"mid level": 2, "senior level": 3, "top level": 4}


def _currency_code(value: str) -> str:
    text = value.strip().lower().replace(".", "")
    if text in {"nrs", "npr", "rs"}:
        return "NPR"
    return text.upper()


def salary_acceptable(job: JobListing, config: JobsConfig) -> bool:
    if not job.salary_is_known:
        return config.include_salary_not_disclosed
    if _currency_code(job.salary_currency) != "NPR":
        return True
    ceiling = job.salary_ceiling
    return ceiling is not None and ceiling >= config.min_salary_npr


def select_jobs(
    jobs: list[JobListing],
    config: JobsConfig,
    *,
    now: datetime,
) -> list[JobListing]:
    instant = to_utc(now)
    cutoff = instant - timedelta(days=config.lookback_days)
    allowed_levels = {level.casefold() for level in config.levels}
    include_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config.title_patterns]
    exclude_patterns = [
        re.compile(pattern, re.IGNORECASE) for pattern in config.exclude_title_patterns
    ]

    selected: list[JobListing] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for job in jobs:
        if job.id in seen_ids or job.url in seen_urls:
            continue
        if job.level.casefold() not in allowed_levels:
            continue
        if any(pattern.search(job.title) for pattern in exclude_patterns):
            continue
        if not any(pattern.search(job.title) for pattern in include_patterns):
            continue
        if job.posted_at < cutoff or job.posted_at > instant:
            continue
        if job.deadline is not None and job.deadline <= instant:
            continue
        if not salary_acceptable(job, config):
            continue
        selected.append(job)
        seen_ids.add(job.id)
        seen_urls.add(job.url)

    selected.sort(
        key=lambda job: (
            job.posted_at,
            _LEVEL_RANK.get(job.level.casefold(), 0),
            job.salary_ceiling or 0.0,
        ),
        reverse=True,
    )
    return selected[: config.max_items]
