"""Parallel, failure-isolated source fetching."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

from ..models import Article
from ..sources.base import Source

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FailedSource:
    id: str
    name: str
    error: str


@dataclass(slots=True)
class FetchResult:
    articles: list[Article] = field(default_factory=list)
    per_source: dict[str, int] = field(default_factory=dict)
    failed_sources: list[FailedSource] = field(default_factory=list)


def _fetch_one(
    source: Source,
    since: datetime,
    retries: int,
    backoff_seconds: float,
) -> list[Article]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return source.fetch_articles(since)
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                logger.warning(
                    "fetch.retry",
                    extra={
                        "data": {
                            "source": source.config.id,
                            "attempt": attempt + 1,
                            "max_attempts": retries + 1,
                            "error_type": type(exc).__name__,
                        }
                    },
                )
                time.sleep(backoff_seconds * (2**attempt))
    assert last_error is not None
    raise last_error


def fetch_all(
    sources: list[Source],
    since: datetime,
    *,
    retries: int = 2,
    max_workers: int = 8,
    backoff_seconds: float = 0.75,
) -> FetchResult:
    result = FetchResult()
    if not sources:
        return result

    workers = min(max_workers, len(sources))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_fetch_one, source, since, retries, backoff_seconds): source
            for source in sources
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                articles = future.result()
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"[:400]
                result.failed_sources.append(
                    FailedSource(id=source.config.id, name=source.config.name, error=message)
                )
                logger.error(
                    "fetch.source_failed",
                    extra={
                        "data": {
                            "source": source.config.id,
                            "source_name": source.config.name,
                            "error": message,
                        }
                    },
                )
                continue

            result.articles.extend(articles)
            result.per_source[source.config.id] = len(articles)
            logger.info(
                "fetch.source_ok",
                extra={
                    "data": {
                        "source": source.config.id,
                        "source_name": source.config.name,
                        "items": len(articles),
                    }
                },
            )

    result.failed_sources.sort(key=lambda item: item.id)
    return result
