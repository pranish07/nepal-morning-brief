"""LLM provider factory."""

from __future__ import annotations

from ..config import ConfigError, Settings
from .base import (
    CuratedItem,
    CuratedResponse,
    CurationResult,
    CurationValidationError,
    LlmClient,
    LlmError,
    LlmQuotaError,
    build_prompt,
    parse_curation_json,
)
from .gemini import GeminiClient


def build_llm_client(settings: Settings, api_key: str) -> LlmClient:
    if settings.llm.provider == "gemini":
        return GeminiClient(api_key, settings.llm)
    raise ConfigError(f"Unsupported LLM provider: {settings.llm.provider}")


__all__ = [
    "CurationResult",
    "CurationValidationError",
    "CuratedItem",
    "CuratedResponse",
    "LlmClient",
    "LlmError",
    "LlmQuotaError",
    "build_llm_client",
    "build_prompt",
    "parse_curation_json",
]
