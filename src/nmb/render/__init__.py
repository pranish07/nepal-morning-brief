"""Jinja rendering for the email and plain-text digest."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..models import Digest
from ..timeutil import NPT, email_subject, format_npt, to_utc

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _autoescape(template_name: str | None) -> bool:
    return bool(template_name and template_name.endswith(".html.j2"))


def render_digest(
    digest: Digest,
    *,
    template_dir: Path | None = None,
    from_name: str = "Nepal Morning Brief",
) -> tuple[str, str, str]:
    env = Environment(
        loader=FileSystemLoader(str(template_dir or TEMPLATE_DIR)),
        autoescape=_autoescape,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["npt"] = format_npt
    generated = to_utc(digest.generated_at).astimezone(NPT)
    context = {
        "digest": digest,
        "sections": digest.sections,
        "sources": digest.source_names,
        "from_name": from_name,
        "date_label": generated.strftime("%A, %d %B %Y"),
        "generated_npt": generated.strftime("%d %b %Y, %H:%M NPT"),
    }
    html_body = env.get_template("digest.html.j2").render(**context)
    text_body = env.get_template("digest.txt.j2").render(**context)
    subject = email_subject(digest.generated_at)
    return subject, text_body, html_body
