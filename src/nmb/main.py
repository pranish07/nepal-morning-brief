"""CLI entry point for Nepal Morning Brief."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import timedelta

from .config import AppConfig, ConfigError, load_config
from .env import (
    ConfigurationError,
    require_gmail_env,
    validate_run_env,
)
from .llm import build_llm_client
from .logging_utils import configure_logging
from .models import Digest
from .pipeline.dedupe import dedupe_articles
from .pipeline.fetch import FetchResult, fetch_all
from .pipeline.rank import rank_all
from .pipeline.summarize import summarize_sections
from .render import render_digest
from .senders import GmailSmtpSender, build_senders
from .sources.registry import build_sources
from .state import StateError, StateStore
from .timeutil import NPT, now_utc

logger = logging.getLogger("nmb.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nmb",
        description="Build and email the Nepal Morning Brief.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest and send nothing.",
    )
    mode.add_argument(
        "--send-test",
        action="store_true",
        help="Send a short test email and exit.",
    )
    parser.add_argument(
        "--section",
        metavar="ID",
        help="Run only the configured section with this id.",
    )
    return parser.parse_args(argv)


def _send_test(config: AppConfig) -> int:
    credentials = require_gmail_env()
    now = now_utc()
    subject = f"Nepal Morning Brief test, {now.astimezone(NPT).strftime('%d %b %Y')}"
    text = (
        "This is a test email from Nepal Morning Brief.\n\n"
        "If you received it, Gmail SMTP and your App Password are configured correctly.\n"
    )
    html = (
        "<html><body style=\"font-family:Arial,sans-serif;color:#1f2933;\">"
        "<h1 style=\"color:#9f1239;\">Nepal Morning Brief</h1>"
        "<p>This is a test email. Gmail SMTP and your App Password are configured correctly.</p>"
        "</body></html>"
    )
    sender = GmailSmtpSender(
        user=credentials.user,
        app_password=credentials.app_password,
        recipient=credentials.recipient,
        from_name=config.settings.email.from_name,
    )
    sender.send(
        subject,
        text,
        html,
        Digest(generated_at=now, sections=[], output_language=config.settings.output_language),
    )
    logger.info("send_test.sent", extra={"data": {"sender": sender.name}})
    return 0


def _run_summary(
    *,
    started: float,
    fetch_result: FetchResult,
    deduped_count: int,
    digest: Digest,
    tokens: int,
    fallback_sections: list[str],
    errors: list[dict[str, str]],
    senders: list[str],
    subject: str,
) -> dict:
    return {
        "duration_seconds": round(time.perf_counter() - started, 2),
        "items_fetched": len(fetch_result.articles),
        "items_deduped": deduped_count,
        "per_source": fetch_result.per_source,
        "failed_sources": [
            {"id": item.id, "name": item.name, "error": item.error}
            for item in fetch_result.failed_sources
        ],
        "llm_tokens": tokens,
        "fallback_sections": fallback_sections,
        "errors": errors,
        "sent": {
            "senders": senders,
            "subject": subject,
            "sections": {section.name: len(section.articles) for section in digest.sections},
            "total_items": digest.total_items,
        },
    }


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    started = time.perf_counter()

    try:
        config = load_config()
        settings = config.settings

        if args.section and args.section not in {section.id for section in settings.sections}:
            raise ConfigurationError(
                f"Unknown section '{args.section}'. "
                "Use one of: " + ", ".join(section.id for section in settings.sections)
            )

        if args.send_test:
            return _send_test(config)

        gemini_key = validate_run_env(settings, dry_run=args.dry_run)
        now = now_utc()
        state = StateStore(config.project_root / "state" / "last_sent.json")
        if not args.dry_run and state.already_sent_today(now):
            logger.info(
                "run.already_sent",
                extra={"data": {"date": state.last_sent_date(), "senders": settings.senders}},
            )
            return 0

        selected_sections = (
            [section for section in settings.sections if section.id == args.section]
            if args.section
            else settings.sections
        )

        sources = build_sources(
            config.enabled_sources(args.section),
            user_agent=settings.user_agent,
            timeout=settings.request_timeout_seconds,
        )
        since = now - timedelta(hours=settings.lookback_hours)
        logger.info(
            "run.start",
            extra={
                "data": {
                    "sources": len(sources),
                    "sections": [section.id for section in selected_sections],
                    "lookback_hours": settings.lookback_hours,
                    "dry_run": args.dry_run,
                }
            },
        )

        fetch_result = fetch_all(
            sources,
            since,
            retries=settings.fetch_retries,
            max_workers=settings.max_workers,
        )
        deduped = dedupe_articles(
            fetch_result.articles,
            threshold=settings.ranking.fuzzy_title_threshold,
        )
        ranked = rank_all(
            deduped,
            now=now,
            lookback_hours=settings.lookback_hours,
            ranking=settings.ranking,
        )
        llm = build_llm_client(settings, gemini_key)
        digest, summarize_stats = summarize_sections(
            settings,
            ranked,
            llm,
            selected_sections,
            now=now,
        )
        subject, text_body, html_body = render_digest(
            digest,
            from_name=settings.email.from_name,
        )

        if args.dry_run:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stdout.write(text_body)
            sys.stdout.write("\n")
            logger.info(
                "run.dry_run",
                extra={
                    "data": {
                        "duration_seconds": round(time.perf_counter() - started, 2),
                        "items_fetched": len(fetch_result.articles),
                        "items_deduped": len(deduped),
                        "per_source": fetch_result.per_source,
                        "failed_sources": [item.id for item in fetch_result.failed_sources],
                        "llm_tokens": summarize_stats.total_tokens,
                        "fallback_sections": summarize_stats.fallback_sections,
                        "sections": {
                            section.name: len(section.articles) for section in digest.sections
                        },
                    }
                },
            )
            return 0

        senders = build_senders(settings, config.project_root)
        for sender in senders:
            sender.send(subject, text_body, html_body, digest)

        state.mark_sent(now)
        logger.info(
            "run.complete",
            extra={
                "data": _run_summary(
                    started=started,
                    fetch_result=fetch_result,
                    deduped_count=len(deduped),
                    digest=digest,
                    tokens=summarize_stats.total_tokens,
                    fallback_sections=summarize_stats.fallback_sections,
                    errors=summarize_stats.errors,
                    senders=[sender.name for sender in senders],
                    subject=subject,
                )
            },
        )
        return 0

    except (ConfigurationError, ConfigError) as exc:
        logger.error("run.config_error", extra={"data": {"error": str(exc)}})
        return 2
    except StateError as exc:
        logger.error("run.state_error", extra={"data": {"error": str(exc)}})
        return 1
    except Exception as exc:
        logger.exception(
            "run.failed",
            extra={"data": {"error_type": type(exc).__name__, "error": str(exc)[:400]}},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
