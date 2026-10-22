"""Render the weekly jobs email."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..timeutil import NPT, to_utc
from .config import JobsConfig
from .models import JobListing

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def render_jobs(
    jobs: list[JobListing],
    *,
    generated_at: datetime,
    config: JobsConfig,
    template_dir: Path | None = None,
) -> tuple[str, str, str]:
    env = Environment(
        loader=FileSystemLoader(str(template_dir or TEMPLATE_DIR)),
        autoescape=select_autoescape(("html", "html.j2"), default_for_string=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    generated = to_utc(generated_at).astimezone(NPT)
    context = {
        "jobs": jobs,
        "job_count": len(jobs),
        "from_name": config.email.from_name,
        "date_label": generated.strftime("%A, %d %B %Y"),
        "generated_npt": generated.strftime("%d %b %Y, %H:%M NPT"),
        "linkedin_searches": config.linkedin_searches,
        "min_salary_npr": config.min_salary_npr,
        "min_salary_label": f"{config.min_salary_npr:,}",
    }
    html_body = env.get_template("jobs.html.j2").render(**context)
    text_body = env.get_template("jobs.txt.j2").render(**context)
    subject = (
        f"{config.email.subject_prefix}, "
        f"{generated.strftime('%A')}, {generated.strftime('%d %b %Y')}"
    )
    return subject, text_body, html_body
