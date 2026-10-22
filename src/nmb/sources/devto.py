"""dev.to articles from the public JSON API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import Article
from ..timeutil import now_utc, to_utc
from .base import Source, SourceError, parse_datetime_value


class DevToSource(Source):
    def fetch_articles(self, since: datetime) -> list[Article]:
        response = self.request(self.config.url)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(f"{self.config.id}: invalid JSON") from exc
        return self.parse_payload(payload, since)

    def parse_payload(
        self,
        payload: Any,
        since: datetime,
        *,
        now: datetime | None = None,
    ) -> list[Article]:
        if not isinstance(payload, list):
            raise SourceError(f"{self.config.id}: unexpected dev.to response")

        instant = to_utc(now) if now is not None else now_utc()
        since_utc = to_utc(since)
        articles: list[Article] = []

        for item in payload:
            if not isinstance(item, dict):
                continue
            published = parse_datetime_value(item.get("published_at"))
            if published is None or published < since_utc or published > instant:
                continue

            reactions = item.get("positive_reactions_count") or 0
            comments = item.get("comments_count") or 0
            try:
                points = int(reactions) + int(comments)
            except (TypeError, ValueError):
                points = None

            article = self.make_article(
                title=item.get("title"),
                url=item.get("url") or item.get("canonical_url"),
                published_at=published,
                excerpt=item.get("description") or "",
                points=points,
            )
            if article is not None:
                articles.append(article)

        articles.sort(key=lambda item: (item.points or 0, item.published_at), reverse=True)
        return articles[: self.config.max_items]
