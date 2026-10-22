"""Core data objects shared by the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .timeutil import format_npt, to_utc


@dataclass(slots=True)
class Article:
    title: str
    url: str
    source_id: str
    source_name: str
    section: str
    language: str
    published_at: datetime
    excerpt: str = ""
    points: int | None = None
    source_weight: float = 1.0
    score: float = 0.0
    canonical_url: str = ""
    also_sources: list[str] = field(default_factory=list)
    summary: str | None = None

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split())
        self.url = self.url.strip()
        self.published_at = to_utc(self.published_at)
        if not self.canonical_url:
            self.canonical_url = self.url

    @property
    def source_count(self) -> int:
        names = {self.source_name, *self.also_sources}
        return len(names)

    def npt_published(self) -> str:
        return format_npt(self.published_at)


@dataclass(slots=True)
class Section:
    id: str
    name: str
    count: int
    articles: list[Article] = field(default_factory=list)


@dataclass(slots=True)
class Digest:
    generated_at: datetime
    sections: list[Section]
    output_language: str = "en"

    @property
    def total_items(self) -> int:
        return sum(len(section.articles) for section in self.sections)

    @property
    def source_names(self) -> list[str]:
        names: set[str] = set()
        for section in self.sections:
            for article in section.articles:
                names.add(article.source_name)
        return sorted(names, key=str.casefold)
