from __future__ import annotations

import itertools
from datetime import datetime, timedelta

import pytest

from nmb.models import Article
from nmb.timeutil import UTC

NOW = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def make_article():
    counter = itertools.count(1)

    def _make(
        *,
        title: str = "A test headline",
        url: str | None = None,
        source_id: str = "test-source",
        source_name: str = "Test Source",
        section: str = "nepal",
        language: str = "en",
        age_hours: float = 1.0,
        source_weight: float = 1.0,
        points: int | None = None,
        published_at: datetime | None = None,
        excerpt: str = "",
    ) -> Article:
        published = published_at or (NOW - timedelta(hours=age_hours))
        return Article(
            title=title,
            url=url or f"https://example.com/article/{next(counter)}",
            source_id=source_id,
            source_name=source_name,
            section=section,
            language=language,
            published_at=published,
            excerpt=excerpt,
            points=points,
            source_weight=source_weight,
        )

    return _make
