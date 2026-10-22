from datetime import datetime
from pathlib import Path

from nmb.config import SourceConfig
from nmb.sources.base import parse_datetime_value
from nmb.sources.rss import RssSource
from nmb.timeutil import UTC

FIXTURES = Path(__file__).parent / "fixtures"


def _source(**overrides) -> RssSource:
    data = {
        "id": "kathmandu-post",
        "name": "The Kathmandu Post",
        "section": "nepal",
        "url": "https://kathmandupost.com/rss",
        "type": "rss",
        "language": "en",
        "weight": 1.3,
        "enabled": True,
    }
    data.update(overrides)
    return RssSource(SourceConfig(**data), user_agent="NepalMorningBrief/test")


def test_rss_fixture_filters_old_items_and_strips_html():
    source = _source()
    body = (FIXTURES / "nepal_rss.xml").read_bytes()
    now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    since = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)

    articles = source.parse_feed(body, since, now=now)

    assert len(articles) == 2
    assert articles[0].title == "Nepal announces new flood response plan"
    assert articles[0].source_name == "The Kathmandu Post"
    assert articles[0].language == "en"
    assert "<strong>" not in articles[0].excerpt
    assert "new plan" in articles[0].excerpt
    assert articles[0].published_at.tzinfo is not None
    assert articles[0].published_at.astimezone(UTC).hour == 2


def test_atom_fixture_parses():
    source = _source(
        id="verge-ai",
        name="The Verge AI",
        section="ai",
        url="https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    )
    body = (FIXTURES / "verge_ai.xml").read_bytes()
    now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    since = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)

    articles = source.parse_feed(body, since, now=now)

    assert len(articles) == 1
    assert articles[0].url == "https://www.theverge.com/ai/2026/10/22/small-model-benchmark"
    assert articles[0].section == "ai"


def test_naive_feed_timestamp_is_assumed_npt():
    parsed = parse_datetime_value("2026-10-22 09:00:00")

    assert parsed.hour == 3
    assert parsed.minute == 15
    assert parsed.tzinfo == UTC


def test_url_date_is_used_when_feed_has_no_item_date():
    source = _source()
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Test</title><link>https://example.com</link>
    <item><title>Budget story</title>
    <link>https://kathmandupost.com/national/2026/10/22/budget</link>
    <description>Summary</description></item></channel></rss>"""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    since = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)

    articles = source.parse_feed(body, since, now=now)

    assert len(articles) == 1
    assert articles[0].published_at.astimezone(UTC).year == 2026
    assert articles[0].published_at.astimezone(UTC).month == 10
