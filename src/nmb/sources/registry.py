"""Factory for source implementations."""

from __future__ import annotations

from ..config import ConfigError, SourceConfig
from .base import Source
from .devto import DevToSource
from .hn import HackerNewsSource
from .rss import RssSource

_SOURCE_TYPES: dict[str, type[Source]] = {
    "rss": RssSource,
    "hn_api": HackerNewsSource,
    "devto_api": DevToSource,
}


def build_source(config: SourceConfig, user_agent: str, timeout: float = 10.0) -> Source:
    source_class = _SOURCE_TYPES.get(config.type)
    if source_class is None:
        raise ConfigError(f"Unsupported source type: {config.type}")
    return source_class(config, user_agent=user_agent, timeout=timeout)


def build_sources(
    configs: list[SourceConfig],
    user_agent: str,
    timeout: float = 10.0,
) -> list[Source]:
    return [build_source(config, user_agent=user_agent, timeout=timeout) for config in configs]
