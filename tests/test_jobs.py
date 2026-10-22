import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from nmb.config import ConfigError
from nmb.jobs.config import JobsConfig, load_jobs_config
from nmb.jobs.filter import select_jobs
from nmb.jobs.merojob import MeroJobClient
from nmb.jobs.models import JobListing
from nmb.jobs.render import render_jobs
from nmb.jobs.runner import run_once
from nmb.state import StateStore
from nmb.timeutil import UTC

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _config() -> JobsConfig:
    return load_jobs_config(ROOT / "config" / "jobs.yaml")


def _jobs() -> list[JobListing]:
    payload = json.loads((FIXTURES / "merojob_jobs.json").read_text(encoding="utf-8"))
    return MeroJobClient(user_agent="NepalMorningBrief/test").parse_payload(payload)


def _job(**overrides) -> JobListing:
    data = {
        "id": "test-1",
        "title": "Senior Full Stack Developer",
        "url": "https://merojob.com/test-1/",
        "company": "Test Co",
        "level": "Senior Level",
        "experience": "More than 3 years",
        "location": "Kathmandu",
        "posted_at": NOW - timedelta(days=2),
        "deadline": NOW + timedelta(days=5),
        "salary_min": 80000,
        "salary_max": 100000,
        "salary_currency": "NRs",
        "salary_unit": "Monthly",
        "salary_hidden": False,
        "skills": ["React", "Node.js"],
    }
    data.update(overrides)
    return JobListing(**data)


def test_checked_in_jobs_config_loads():
    config = _config()
    assert config.max_items == 10
    assert config.min_salary_npr == 40000
    assert "Mid Level" in config.levels
    assert len(config.linkedin_searches) == 2


def test_jobs_config_rejects_invalid_regex(tmp_path):
    path = tmp_path / "jobs.yaml"
    path.write_text(
        """
max_items: 5
levels: [Mid Level]
title_patterns: ['[unclosed']
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_jobs_config(path)


def test_merojob_parser_maps_fields_and_respects_hidden_salary():
    jobs = _jobs()
    assert len(jobs) == 8
    first = next(job for job in jobs if job.id == "1")
    assert first.company == "Universal Outsourcing"
    assert first.url == "https://merojob.com/senior-full-stack-developer-29/"
    assert first.salary_label == "NPR 300,000–350,000/month"
    assert first.location == "Kathmandu"

    hidden = next(job for job in jobs if job.id == "2")
    assert hidden.salary_label == "Not disclosed"
    assert hidden.url == "https://merojob.com/full-stack-developer-nextjs/"


def test_select_jobs_applies_level_title_salary_and_deadline_rules():
    selected = select_jobs(_jobs(), _config(), now=NOW)
    assert [job.id for job in selected] == ["8", "1", "2"]
    assert all(job.level != "Entry Level" for job in selected)
    assert all("junior" not in job.title.casefold() for job in selected)


def test_salary_floor_excludes_disclosed_low_pay():
    low_pay = _job(
        id="low",
        title="Mid Level Full Stack Developer",
        level="Mid Level",
        salary_min=25000,
        salary_max=35000,
    )
    assert select_jobs([low_pay], _config(), now=NOW) == []


def test_hidden_salary_is_included_when_configured():
    hidden = _job(
        id="hidden",
        title="Full Stack Developer",
        level="Mid Level",
        salary_min=90000,
        salary_max=120000,
        salary_hidden=True,
    )
    selected = select_jobs([hidden], _config(), now=NOW)
    assert len(selected) == 1
    assert selected[0].salary_label == "Not disclosed"


def test_render_jobs_contains_details_and_linkedin_links():
    jobs = select_jobs(_jobs(), _config(), now=NOW)
    subject, text, html = render_jobs(jobs, generated_at=NOW, config=_config())

    assert subject == "Nepal Tech Jobs, Thursday, 22 Oct 2026"
    assert "Universal Outsourcing" in text
    assert "NPR 300,000–350,000/month" in text
    assert "Skills: React, Node.js, TypeScript" in text
    assert "Frontend roles on LinkedIn" in text
    assert "linkedin.com/jobs/search" in text
    assert "Universal Outsourcing" in html
    assert "Not disclosed" in html
    assert "linkedin.com/jobs/search" in html


class FakeClient:
    def __init__(self, jobs):
        self.jobs = jobs
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return self.jobs


class FakeSender:
    name = "fake"

    def __init__(self):
        self.calls = 0
        self.subject = None

    def send_content(self, subject, text_body, html_body):
        self.calls += 1
        self.subject = subject


def test_weekly_runner_sends_once_and_then_skips(tmp_path):
    state = StateStore(tmp_path / "jobs_last_sent.json")
    sender = FakeSender()
    client = FakeClient([_job()])

    first = run_once(
        config=_config(),
        now=NOW,
        state=state,
        client=client,
        sender_factory=lambda: sender,
        dry_run=False,
    )
    second = run_once(
        config=_config(),
        now=NOW + timedelta(hours=1),
        state=state,
        client=client,
        sender_factory=lambda: sender,
        dry_run=False,
    )

    assert first == 0
    assert second == 0
    assert sender.calls == 1
    assert client.calls == 1
    assert state.last_sent_date() == "2026-10-22"


def test_weekly_runner_with_no_matches_does_not_send_or_mark_state(tmp_path):
    state = StateStore(tmp_path / "jobs_last_sent.json")
    sender = FakeSender()
    client = FakeClient([])

    result = run_once(
        config=_config(),
        now=NOW,
        state=state,
        client=client,
        sender_factory=lambda: sender,
        dry_run=False,
    )

    assert result == 0
    assert sender.calls == 0
    assert state.last_sent_date() is None
