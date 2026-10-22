"""CLI runner for the weekly Nepal tech-jobs digest."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from ..config import PROJECT_ROOT, ConfigError
from ..env import ConfigurationError, require_gmail_env
from ..logging_utils import configure_logging
from ..senders.base import SenderError
from ..senders.gmail_smtp import GmailSmtpSender
from ..sources.base import SourceError
from ..state import StateError, StateStore
from ..timeutil import now_utc
from .config import JobsConfig, load_jobs_config
from .filter import select_jobs
from .merojob import MeroJobClient
from .render import render_jobs

logger = logging.getLogger("nmb.jobs")

STATE_PATH = PROJECT_ROOT / "state" / "jobs_last_sent.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nmb-jobs",
        description="Build and email the weekly Nepal tech-jobs digest.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the jobs email and send nothing.",
    )
    return parser.parse_args(argv)


def _build_sender(config: JobsConfig) -> GmailSmtpSender:
    credentials = require_gmail_env()
    return GmailSmtpSender(
        user=credentials.user,
        app_password=credentials.app_password,
        recipient=credentials.recipient,
        from_name=config.email.from_name,
    )


def run_once(
    *,
    config: JobsConfig,
    now: datetime,
    state: StateStore,
    client: MeroJobClient,
    sender_factory,
    dry_run: bool,
) -> int:
    if not config.enabled:
        logger.info("jobs.disabled")
        return 0

    if not dry_run and state.already_sent_today(now):
        logger.info(
            "jobs.already_sent",
            extra={"data": {"date": state.last_sent_date()}},
        )
        return 0

    jobs = client.fetch()
    selected = select_jobs(jobs, config, now=now)
    if not selected:
        logger.info(
            "jobs.no_matches",
            extra={"data": {"fetched": len(jobs)}},
        )
        return 0

    subject, text_body, html_body = render_jobs(
        selected,
        generated_at=now,
        config=config,
    )

    if dry_run:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.write(text_body)
        sys.stdout.write("\n")
        logger.info(
            "jobs.dry_run",
            extra={"data": {"fetched": len(jobs), "selected": len(selected)}},
        )
        return 0

    sender = sender_factory()
    sender.send_content(subject, text_body, html_body)
    state.mark_sent(now)
    logger.info(
        "jobs.sent",
        extra={
            "data": {
                "subject": subject,
                "items": len(selected),
                "sender": sender.name,
            }
        },
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    try:
        config = load_jobs_config()
        now = now_utc()
        state = StateStore(STATE_PATH)
        client = MeroJobClient(
            user_agent=config.user_agent,
            timeout=config.request_timeout_seconds,
        )
        return run_once(
            config=config,
            now=now,
            state=state,
            client=client,
            sender_factory=lambda: _build_sender(config),
            dry_run=args.dry_run,
        )
    except (ConfigError, ConfigurationError) as exc:
        logger.error("jobs.config_error", extra={"data": {"error": str(exc)}})
        return 2
    except (StateError, SourceError, SenderError) as exc:
        logger.error("jobs.run_error", extra={"data": {"error": str(exc)}})
        return 1
    except Exception as exc:
        logger.exception(
            "jobs.run.failed",
            extra={"data": {"error_type": type(exc).__name__, "error": str(exc)[:400]}},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
