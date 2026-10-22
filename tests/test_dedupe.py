from nmb.pipeline.dedupe import canonicalize_url, dedupe_articles, normalize_title


def test_canonicalize_strips_tracking_and_fragment():
    url = "https://Example.com/a/?utm_source=rss&b=2&a=1#section"
    assert canonicalize_url(url) == "https://example.com/a?a=1&b=2"


def test_canonicalize_removes_default_port_and_trailing_slash():
    assert canonicalize_url("http://Example.com:80/news/") == "http://example.com/news"
    assert canonicalize_url("https://example.com:443") == "https://example.com/"


def test_normalize_title_handles_unicode_and_punctuation():
    assert normalize_title("  Kathmandu’s   New FLYOVER! ") == "kathmandu s new flyover"


def test_dedupe_by_canonical_url_merges_source_mentions(make_article):
    first = make_article(
        title="Flood response plan announced",
        url="https://one.example/story?utm_source=rss&utm_medium=feed",
        source_id="one",
        source_name="One",
        source_weight=1.0,
    )
    second = make_article(
        title="Flood response plan announced",
        url="https://two.example/story",
        source_id="two",
        source_name="Two",
        source_weight=2.0,
    )
    result = dedupe_articles([first, second], threshold=90)
    assert len(result) == 1
    assert result[0].source_name == "Two"
    assert result[0].source_count == 2


def test_dedupe_by_fuzzy_title_keeps_primary_link(make_article):
    first = make_article(
        title="Nepal announces a new flood response plan",
        url="https://one.example/a",
        source_id="one",
        source_name="One",
    )
    second = make_article(
        title="Nepal announces new flood-response plan!",
        url="https://two.example/b",
        source_id="two",
        source_name="Two",
    )
    result = dedupe_articles([first, second], threshold=88)
    assert len(result) == 1
    assert result[0].url == "https://one.example/a"
    assert result[0].also_sources == ["Two"]


def test_dedupe_does_not_merge_unrelated_items(make_article):
    first = make_article(title="Nepal budget approved", url="https://example.com/budget")
    second = make_article(title="Nepal cricket team wins", url="https://example.com/cricket")
    assert len(dedupe_articles([first, second])) == 2


def test_dedupe_is_scoped_to_sections(make_article):
    first = make_article(
        title="Shared headline",
        url="https://example.com/shared",
        section="nepal",
    )
    second = make_article(
        title="Shared headline",
        url="https://example.com/shared",
        section="world",
    )
    assert len(dedupe_articles([first, second])) == 2
