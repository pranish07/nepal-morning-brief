import json
from datetime import datetime
from pathlib import Path

from nmb.config import SourceConfig
from nmb.sources.devto import DevToSource
from nmb.sources.hn import HackerNewsSource
from nmb.timeutil import UTC

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
SINCE = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)


def test_hn_filters_keywords_and_uses_item_link_for_self_posts():
    config = SourceConfig(
        id="hn-ai",
        name="Hacker News",
        section="ai",
        url="https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI",
        type="hn_api",
        language="en",
        weight=0.9,
        keywords=["AI", "LLM", "agent"],
    )
    source = HackerNewsSource(config, user_agent="NepalMorningBrief/test")
    payload = json.loads((FIXTURES / "hn_ai.json").read_text(encoding="utf-8"))

    articles = source.parse_payload(payload, SINCE, now=NOW)

    assert len(articles) == 2
    assert articles[0].points == 240
    assert articles[0].title == "A new open source LLM is released"
    self_post = next(item for item in articles if item.title.startswith("Ask HN"))
    assert self_post.url == "https://news.ycombinator.com/item?id=1003"


def test_hn_payload_without_hits_is_a_source_error():
    config = SourceConfig(
        id="hn-ai",
        name="Hacker News",
        section="ai",
        url="https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI",
        type="hn_api",
    )
    source = HackerNewsSource(config, user_agent="NepalMorningBrief/test")
    try:
        source.parse_payload({}, SINCE, now=NOW)
    except Exception as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("expected SourceError")


def test_devto_parses_only_recent_articles():
    config = SourceConfig(
        id="devto",
        name="DEV Community",
        section="programming",
        url="https://dev.to/api/articles?top=1&per_page=30",
        type="devto_api",
        language="en",
        weight=0.9,
    )
    source = DevToSource(config, user_agent="NepalMorningBrief/test")
    payload = json.loads((FIXTURES / "devto.json").read_text(encoding="utf-8"))

    articles = source.parse_payload(payload, SINCE, now=NOW)

    assert len(articles) == 1
    assert articles[0].title == "Writing reliable background jobs"
    assert articles[0].points == 49
