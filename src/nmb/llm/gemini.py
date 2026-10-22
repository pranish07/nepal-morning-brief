"""Gemini free-tier REST client."""

from __future__ import annotations

import logging
from typing import Any

import requests

from ..config import LlmConfig, SectionConfig
from ..models import Article
from .base import (
    CurationResult,
    LlmClient,
    LlmError,
    LlmQuotaError,
    build_prompt,
    parse_curation_json,
)

logger = logging.getLogger(__name__)


class GeminiClient(LlmClient):
    def __init__(
        self,
        api_key: str,
        config: LlmConfig,
        *,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        self.api_key = api_key
        self.config = config
        self.session = session or requests.Session()
        self.url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.model}:generateContent"
        )

    def curate(
        self,
        section: SectionConfig,
        candidates: list[Article],
        output_language: str,
    ) -> CurationResult:
        system, user = build_prompt(section, candidates, output_language)
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        try:
            response = self.session.post(
                self.url,
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise LlmError(f"Gemini request failed ({type(exc).__name__})") from exc

        if response.status_code == 429:
            raise LlmQuotaError("Gemini quota or rate limit returned HTTP 429")
        if response.status_code >= 400:
            detail = _error_detail(response)
            raise LlmError(f"Gemini returned HTTP {response.status_code}: {detail}")

        try:
            data = response.json()
        except ValueError as exc:
            raise LlmError("Gemini returned invalid JSON") from exc

        text = _response_text(data)
        if not text:
            raise LlmError("Gemini returned no text")

        articles = parse_curation_json(text, candidates, section.count)
        usage = data.get("usageMetadata") if isinstance(data, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
        completion_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
        total_tokens = int(usage.get("totalTokenCount", 0) or 0)

        logger.info(
            "llm.curated",
            extra={
                "data": {
                    "provider": "gemini",
                    "model": self.config.model,
                    "section": section.id,
                    "items": len(articles),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
            },
        )
        return CurationResult(
            articles=articles,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


def _response_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    first = candidates[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "".join(texts).strip()


def _error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "request rejected"
    if not isinstance(payload, dict):
        return "request rejected"
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message[:300]
    return "request rejected"
