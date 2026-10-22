"""Source interface and shared parsing helpers."""

from __future__ import annotations

import html
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from dateutil import parser as date_parser

from ..config import SourceConfig
from ..models import Article
from ..timeutil import NPT, UTC


class SourceError(RuntimeError):
    """A recoverable source-level failure."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(value: str | None, limit: int = 600) -> str:
    if not value:
        return ""
    extractor = _TextExtractor()
    try:
        extractor.feed(value)
        text = " ".join(extractor.parts)
    except Exception:
        text = html.unescape(re.sub(r"<[^>]+>", " ", value))
    text = " ".join(html.unescape(text).split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def parse_datetime_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=NPT).astimezone(UTC)
            if value.tzinfo is None
            else value.astimezone(UTC)
        )
    if isinstance(value, (time.struct_time, tuple)):
        try:
            return datetime(*tuple(value)[:6], tzinfo=UTC)
        except (TypeError, ValueError):
            return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = date_parser.parse(text)
        except (ValueError, OverflowError):
            return None
        return (
            parsed.replace(tzinfo=NPT).astimezone(UTC)
            if parsed.tzinfo is None
            else parsed.astimezone(UTC)
        )
    return None


def date_from_url(url: str) -> datetime | None:
    """Read a /YYYY/MM/DD/ date from a URL, if present."""
    path = urlparse(url).path
    match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})(?:/|$)", path)
    if not match:
        return None
    try:
        local_midnight = datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            tzinfo=NPT,
        )
        return local_midnight.astimezone(UTC)
    except ValueError:
        return None


class Source(ABC):
    def __init__(self, config: SourceConfig, user_agent: str, timeout: float = 10.0) -> None:
        self.config = config
        self.user_agent = user_agent
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": (
                    "application/rss+xml, application/atom+xml, application/xml, "
                    "application/json, text/xml;q=0.9, */*;q=0.5"
                ),
            }
        )

    @abstractmethod
    def fetch_articles(self, since: datetime) -> list[Article]:
        """Fetch and normalize articles published at or after `since` (UTC)."""

    def request(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SourceError(f"{self.config.id}: request failed ({type(exc).__name__})") from exc
        if response.status_code >= 400:
            raise SourceError(f"{self.config.id}: HTTP {response.status_code}")
        return response

    def make_article(
        self,
        *,
        title: str | None,
        url: str | None,
        published_at: datetime,
        excerpt: str = "",
        points: int | None = None,
    ) -> Article | None:
        if not title or not url:
            return None
        absolute_url = urljoin(self.config.url, url.strip())
        if urlparse(absolute_url).scheme not in {"http", "https"}:
            return None
        return Article(
            title=strip_html(title, limit=300),
            url=absolute_url,
            source_id=self.config.id,
            source_name=self.config.name,
            section=self.config.section,
            language=self.config.language,
            published_at=published_at,
            excerpt=strip_html(excerpt, limit=600),
            points=points,
            source_weight=self.config.weight,
        )
