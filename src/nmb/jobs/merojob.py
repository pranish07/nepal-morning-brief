"""MeroJob public JSON client for weekly tech jobs."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests

from ..sources.base import SourceError, parse_datetime_value, strip_html
from .models import JobListing

logger = logging.getLogger(__name__)

MEROJOB_API_URL = "https://api.merojob.com/api/v1/jobs"
MEROJOB_BASE_URL = "https://merojob.com/"


class MeroJobClient:
    def __init__(self, *, user_agent: str, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json, */*;q=0.5",
            }
        )

    def fetch(self) -> list[JobListing]:
        try:
            response = self.session.get(MEROJOB_API_URL, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SourceError(f"merojob: request failed ({type(exc).__name__})") from exc
        if response.status_code >= 400:
            raise SourceError(f"merojob: HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError("merojob: response was not valid JSON") from exc
        jobs = self.parse_payload(payload)
        logger.info("jobs.fetched", extra={"data": {"source": "merojob", "count": len(jobs)}})
        return jobs

    def parse_payload(self, payload: Any) -> list[JobListing]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise SourceError("merojob: unexpected response shape")
        jobs: list[JobListing] = []
        for row in payload["results"]:
            if not isinstance(row, dict) or row.get("is_published") is False:
                continue
            job = self._parse_row(row)
            if job is not None:
                jobs.append(job)
        return jobs

    def _parse_row(self, row: dict[str, Any]) -> JobListing | None:
        title = strip_html(str(row.get("title") or ""), limit=300)
        relative_url = row.get("absolute_url") or (
            f"/{row.get('slug')}/" if row.get("slug") else None
        )
        posted_at = parse_datetime_value(row.get("posted_at") or row.get("posted_date"))
        if not title or not relative_url or posted_at is None:
            return None

        job_id = row.get("id")
        if job_id is None:
            return None

        client = row.get("client")
        client = client if isinstance(client, dict) else {}
        company = (
            str(client.get("client_name") or "").strip()
            or str(client.get("org_name") or "").strip()
            or "Company not stated"
        )

        raw_salary = row.get("offered_salary")
        salary = raw_salary if isinstance(raw_salary, dict) else {}
        locations = row.get("job_locations")
        location_names = []
        if isinstance(locations, list):
            for item in locations:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("address") or item.get("name") or "").strip()
                if text and text not in location_names:
                    location_names.append(text)
        if not location_names:
            fallback_location = str(client.get("location") or "").strip()
            if fallback_location:
                location_names.append(fallback_location)

        raw_skills = row.get("skills")
        skills = []
        if isinstance(raw_skills, list):
            for value in raw_skills:
                text = strip_html(str(value or ""), limit=60).strip()
                if text and text not in skills:
                    skills.append(text)

        return JobListing(
            id=str(job_id),
            title=title,
            url=urljoin(MEROJOB_BASE_URL, str(relative_url).strip()),
            company=company,
            level=str(row.get("job_level") or "").strip(),
            experience=str(row.get("experience_required") or "").strip(),
            location=", ".join(location_names),
            posted_at=posted_at,
            deadline=parse_datetime_value(row.get("deadline")),
            salary_min=_optional_float(salary.get("minimum")),
            salary_max=_optional_float(salary.get("maximum")),
            salary_currency=str(salary.get("currency") or "NPR"),
            salary_unit=str(salary.get("unit") or ""),
            salary_hidden=bool(row.get("hide_salary")),
            skills=skills,
        )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
