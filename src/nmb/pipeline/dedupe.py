"""URL canonicalization and fuzzy title deduplication."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunsplit

from rapidfuzz import fuzz

from ..models import Article

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "_hsenc",
    "_hsmi",
    "ref",
    "source",
    "campaign",
}


def canonicalize_url(url: str) -> str:
    """Normalize a URL and remove common tracking parameters."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return ""

    scheme = parsed.scheme.casefold()
    host = parsed.netloc.casefold()
    if (scheme == "http" and host.endswith(":80")) or (scheme == "https" and host.endswith(":443")):
        host = host.rsplit(":", 1)[0]

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    kept_params: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.casefold()
        if lowered.startswith("utm_") or lowered in _TRACKING_PARAMS:
            continue
        kept_params.append((key, value))
    kept_params.sort()

    return urlunsplit((scheme, host, path, urlencode(kept_params, doseq=True), ""))


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"\w+", text, flags=re.UNICODE))


def _titles_match(left: str, right: str, threshold: int) -> bool:
    left_norm = normalize_title(left)
    right_norm = normalize_title(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    shorter, longer = sorted((left_norm, right_norm), key=len)
    if len(shorter) / len(longer) < 0.55:
        return False
    return (
        fuzz.token_sort_ratio(left_norm, right_norm) >= threshold
        or fuzz.token_set_ratio(left_norm, right_norm) >= threshold
    )


def _merge(existing: Article, candidate: Article) -> None:
    names = {
        existing.source_name,
        candidate.source_name,
        *existing.also_sources,
        *candidate.also_sources,
    }
    prefer_candidate = (
        candidate.source_weight > existing.source_weight
        or (
            candidate.source_weight == existing.source_weight
            and candidate.published_at > existing.published_at
        )
    )
    if prefer_candidate:
        existing.title = candidate.title
        existing.url = candidate.url
        existing.source_id = candidate.source_id
        existing.source_name = candidate.source_name
        existing.language = candidate.language
        existing.published_at = candidate.published_at
        existing.excerpt = candidate.excerpt
        existing.points = candidate.points
        existing.source_weight = candidate.source_weight
        existing.canonical_url = candidate.canonical_url
    names.discard(existing.source_name)
    existing.also_sources = sorted(names, key=str.casefold)


def dedupe_articles(articles: list[Article], *, threshold: int = 90) -> list[Article]:
    """Deduplicate within each section by canonical URL and similar titles."""
    by_section: dict[str, list[Article]] = {}
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        canonical = canonicalize_url(article.url)
        if not canonical:
            continue
        article.canonical_url = canonical

        retained = by_section.setdefault(article.section, [])
        match: Article | None = None
        for existing in retained:
            if existing.canonical_url == canonical or _titles_match(
                existing.title, article.title, threshold
            ):
                match = existing
                break

        if match is None:
            retained.append(article)
        else:
            _merge(match, article)

    return [article for section_articles in by_section.values() for article in section_articles]
