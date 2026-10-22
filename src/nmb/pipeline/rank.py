"""Cheap pre-ranking before the LLM curation step."""

from __future__ import annotations

import math
from datetime import datetime

from ..config import RankingConfig
from ..models import Article
from ..timeutil import to_utc


def score_article(
    article: Article,
    now: datetime,
    lookback_hours: int,
    ranking: RankingConfig,
) -> float:
    instant = to_utc(now)
    age_hours = max(0.0, (instant - article.published_at).total_seconds() / 3600.0)
    recency = max(0.0, 1.0 - (age_hours / lookback_hours)) * ranking.recency_weight
    source = min(article.source_weight, 3.0) * ranking.source_weight
    cross_source = min(max(article.source_count - 1, 0), 3) * ranking.cross_source_bonus
    points = 0.0
    if article.points is not None and article.points > 0:
        points = math.log10(article.points + 1) * ranking.hn_points_weight
    return round(recency + source + cross_source + points, 4)


def rank_section(
    articles: list[Article],
    *,
    now: datetime,
    lookback_hours: int,
    ranking: RankingConfig,
) -> list[Article]:
    instant = to_utc(now)
    eligible = [
        article
        for article in articles
        if article.published_at <= instant
        and (instant - article.published_at).total_seconds() <= lookback_hours * 3600
    ]
    for article in eligible:
        article.score = score_article(article, instant, lookback_hours, ranking)
    return sorted(
        eligible,
        key=lambda item: (item.score, item.published_at, item.source_weight),
        reverse=True,
    )


def rank_all(
    articles: list[Article],
    *,
    now: datetime,
    lookback_hours: int,
    ranking: RankingConfig,
) -> dict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.section, []).append(article)
    return {
        section: rank_section(
            section_articles,
            now=now,
            lookback_hours=lookback_hours,
            ranking=ranking,
        )
        for section, section_articles in grouped.items()
    }
