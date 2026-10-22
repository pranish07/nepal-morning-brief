"""Hacker News stories from the public Algolia API."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..models import Article
from ..timeutil import now_utc, to_utc
from .base import Source, SourceError, parse_datetime_value


def _matches_keywords(title: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f" {title.casefold()} "
    for keyword in keywords:
        needle = keyword.casefold().strip()
        if needle and re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", text):
            return True
    return False


class HackerNewsSource(Source):
    def fetch_articles(self, since: datetime) -> list[Article]:
        params = {
            "numericFilters": f"created_at_i>{int(to_utc(since).timestamp())}",
            "hitsPerPage": str(self.config.max_items),
        }
        response = self.request(self.config.url, params=params)
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
        if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
            raise SourceError(f"{self.config.id}: unexpected Hacker News response")

        instant = to_utc(now) if now is not None else now_utc()
        since_utc = to_utc(since)
        articles: list[Article] = []

        for hit in payload["hits"]:
            if not isinstance(hit, dict):
                continue
            title = hit.get("title") or ""
            if not title or not _matches_keywords(title, self.config.keywords):
                continue

            published = (
                parse_datetime_value(hit.get("created_at_i"))
                or parse_datetime_value(hit.get("created_at"))
            )
            if published is None or published < since_utc or published > instant:
                continue

            object_id = hit.get("objectID")
            url = hit.get("url") or (
                f"https://news.ycombinator.com/item?id={object_id}" if object_id else None
            )
            points_value = hit.get("points")
            try:
                points = int(points_value) if points_value is not None else None
            except (TypeError, ValueError):
                points = None

            article = self.make_article(
                title=title,
                url=url,
                published_at=published,
                excerpt=hit.get("story_text") or "",
                points=points,
            )
            if article is not None:
                articles.append(article)

        articles.sort(key=lambda item: (item.points or 0, item.published_at), reverse=True)
        return articles[: self.config.max_items]
