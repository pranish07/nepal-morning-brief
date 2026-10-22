"""LLM curation with a guaranteed non-LLM fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime

from ..config import SectionConfig, Settings
from ..llm.base import LlmClient
from ..models import Article, Digest, Section

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SummarizeStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    fallback_sections: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


def _fallback(candidates: list[Article], count: int) -> list[Article]:
    return [replace(article, summary=None) for article in candidates[:count]]


def summarize_section(
    section: SectionConfig,
    candidates: list[Article],
    llm: LlmClient,
    output_language: str,
    stats: SummarizeStats,
) -> Section:
    if not candidates:
        return Section(id=section.id, name=section.name, count=section.count, articles=[])

    effective_count = min(section.count, len(candidates))
    prompt_section = section.model_copy(update={"count": effective_count})
    try:
        result = llm.curate(prompt_section, candidates, output_language)
        stats.prompt_tokens += result.prompt_tokens
        stats.completion_tokens += result.completion_tokens
        stats.total_tokens += result.total_tokens
        return Section(
            id=section.id,
            name=section.name,
            count=section.count,
            articles=result.articles[:effective_count],
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:400]
        stats.fallback_sections.append(section.id)
        stats.errors.append({"section": section.id, "error": error})
        logger.error(
            "llm.fallback",
            extra={"data": {"section": section.id, "error": error}},
        )
        return Section(
            id=section.id,
            name=section.name,
            count=section.count,
            articles=_fallback(candidates, effective_count),
        )


def summarize_sections(
    settings: Settings,
    ranked: dict[str, list[Article]],
    llm: LlmClient,
    sections: list[SectionConfig],
    *,
    now: datetime,
) -> tuple[Digest, SummarizeStats]:
    stats = SummarizeStats()
    output: list[Section] = []
    for section in sections:
        candidates = ranked.get(section.id, [])[: settings.llm_candidates]
        output.append(
            summarize_section(
                section,
                candidates,
                llm,
                settings.output_language,
                stats,
            )
        )
    return (
        Digest(
            generated_at=now,
            sections=output,
            output_language=settings.output_language,
        ),
        stats,
    )
