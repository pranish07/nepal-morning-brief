"""RSS and Atom feeds through feedparser."""

from __future__ import annotations

import logging
from datetime import datetime

import feedparser

from ..models import Article
from ..timeutil import now_utc, to_utc
from .base import Source, SourceError, date_from_url, parse_datetime_value

logger = logging.getLogger(__name__)


class RssSource(Source):
    def fetch_articles(self, since: datetime) -> list[Article]:
        response = self.request(self.config.url)
        return self.parse_feed(response.content, since)

    def parse_feed(
        self,
        content: bytes | str,
        since: datetime,
        *,
        now: datetime | None = None,
    ) -> list[Article]:
        parsed = feedparser.parse(content)
        if parsed.bozo and not parsed.entries:
            raise SourceError(f"{self.config.id}: invalid feed ({parsed.bozo_exception})")

        instant = to_utc(now) if now is not None else now_utc()
        since_utc = to_utc(since)
        feed_date = (
            parse_datetime_value(parsed.feed.get("updated_parsed"))
            or parse_datetime_value(parsed.feed.get("published_parsed"))
            or parse_datetime_value(parsed.feed.get("updated"))
            or instant
        )

        articles: list[Article] = []
        undated = 0
        for entry in parsed.entries:
            link = entry.get("link") or entry.get("id")
            if not link:
                continue

            published = (
                parse_datetime_value(entry.get("published_parsed"))
                or parse_datetime_value(entry.get("updated_parsed"))
                or parse_datetime_value(entry.get("published"))
                or parse_datetime_value(entry.get("updated"))
                or parse_datetime_value(entry.get("created"))
                or date_from_url(link)
            )
            if published is None:
                undated += 1
                published = feed_date

            if published < since_utc or published > instant:
                continue

            excerpt = entry.get("summary") or entry.get("description") or ""
            content_parts = entry.get("content") or []
            if not excerpt and content_parts:
                excerpt = content_parts[0].get("value", "")

            article = self.make_article(
                title=entry.get("title"),
                url=link,
                published_at=published,
                excerpt=excerpt,
            )
            if article is not None:
                articles.append(article)

        if undated:
            logger.info(
                "rss.undated_items",
                extra={"data": {"source": self.config.id, "count": undated}},
            )

        articles.sort(key=lambda item: item.published_at, reverse=True)
        return articles[: self.config.max_items]
