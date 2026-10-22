from dataclasses import replace

from nmb.config import RankingConfig, SectionConfig, Settings
from nmb.llm.base import (
    CurationResult,
    CurationValidationError,
    LlmClient,
    LlmQuotaError,
)
from nmb.pipeline.rank import rank_all
from nmb.pipeline.summarize import SummarizeStats, summarize_section, summarize_sections


class FakeLlm(LlmClient):
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls = 0

    def curate(self, section, candidates, output_language):
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        selected = [
            replace(
                article,
                title=f"Curated: {article.title}",
                summary=f"Original summary for {article.title}.",
            )
            for article in candidates[: section.count]
        ]
        return CurationResult(
            articles=selected,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "output_language": "en",
            "lookback_hours": 36,
            "llm_candidates": 15,
            "senders": ["gmail_smtp"],
            "sections": [{"id": "nepal", "name": "Nepal", "count": 10}],
        }
    )


def test_section_returns_requested_count_and_tokens(make_article):
    candidates = [make_article(title=f"Story {index}", age_hours=index) for index in range(12)]
    section = SectionConfig(id="nepal", name="Nepal", count=10)
    stats = SummarizeStats()
    result = summarize_section(section, candidates, FakeLlm(), "en", stats)
    assert len(result.articles) == 10
    assert all(article.summary for article in result.articles)
    assert stats.total_tokens == 150
    assert stats.fallback_sections == []


def test_quota_error_falls_back_to_original_titles_and_links(make_article):
    candidates = [make_article(title=f"Story {index}", age_hours=index) for index in range(12)]
    section = SectionConfig(id="nepal", name="Nepal", count=10)
    stats = SummarizeStats()

    result = summarize_section(section, candidates, FakeLlm(fail=LlmQuotaError("429")), "en", stats)

    assert len(result.articles) == 10
    assert [item.url for item in result.articles] == [item.url for item in candidates[:10]]
    assert all(item.summary is None for item in result.articles)
    assert stats.fallback_sections == ["nepal"]


def test_bad_json_error_falls_back(make_article):
    candidates = [make_article(title=f"Story {index}") for index in range(11)]
    section = SectionConfig(id="nepal", name="Nepal", count=10)
    stats = SummarizeStats()
    result = summarize_section(
        section,
        candidates,
        FakeLlm(fail=CurationValidationError("bad json")),
        "en",
        stats,
    )
    assert len(result.articles) == 10
    assert all(item.summary is None for item in result.articles)
    assert stats.errors[0]["section"] == "nepal"


def test_insufficient_candidates_are_summarized_with_available_count(make_article):
    candidates = [make_article(title=f"Story {index}") for index in range(3)]
    section = SectionConfig(id="nepal", name="Nepal", count=10)
    llm = FakeLlm()
    stats = SummarizeStats()
    result = summarize_section(section, candidates, llm, "en", stats)
    assert len(result.articles) == 3
    assert llm.calls == 1
    assert all(item.summary for item in result.articles)
    assert result.count == 10


def test_summarize_sections_builds_digest(make_article, now):
    settings = _settings()
    candidates = [make_article(title=f"Story {index}", age_hours=index) for index in range(20)]
    ranked = rank_all(
        candidates,
        now=now,
        lookback_hours=36,
        ranking=RankingConfig(),
    )
    llm = FakeLlm()
    digest, stats = summarize_sections(
        settings,
        ranked,
        llm,
        settings.sections,
        now=now,
    )
    assert digest.total_items == 10
    assert digest.sections[0].count == 10
    assert stats.fallback_sections == []
