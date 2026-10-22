"""YAML configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=120)
    section: str = Field(min_length=2, max_length=40)
    url: str = Field(min_length=8)
    type: Literal["rss", "hn_api", "devto_api"]
    language: Literal["en", "ne"] = "en"
    weight: float = Field(default=1.0, ge=0.0, le=5.0)
    enabled: bool = True
    keywords: list[str] = Field(default_factory=list)
    max_items: int = Field(default=40, ge=1, le=200)

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        return value


class SourcesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceConfig]

    @model_validator(mode="after")
    def unique_ids(self) -> "SourcesFile":
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return self


class SectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=60)
    count: int = Field(ge=1, le=50)


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["gemini"] = "gemini"
    model: str = "gemini-2.5-flash"
    timeout_seconds: int = Field(default=90, ge=10, le=300)
    temperature: float = Field(default=0.25, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=6144, ge=512, le=32768)


class RankingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recency_weight: float = Field(default=5.0, ge=0.0, le=20.0)
    source_weight: float = Field(default=1.5, ge=0.0, le=10.0)
    cross_source_bonus: float = Field(default=2.0, ge=0.0, le=10.0)
    hn_points_weight: float = Field(default=1.2, ge=0.0, le=10.0)
    fuzzy_title_threshold: int = Field(default=90, ge=70, le=100)


class EmailConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_name: str = Field(default="Nepal Morning Brief", min_length=2, max_length=80)


class FileSenderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_dir: str = "public"
    site_url: str = ""


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_language: Literal["en", "ne", "both"] = "en"
    lookback_hours: int = Field(default=36, ge=12, le=72)
    llm_candidates: int = Field(default=15, ge=5, le=50)
    request_timeout_seconds: int = Field(default=10, ge=3, le=60)
    fetch_retries: int = Field(default=2, ge=0, le=5)
    max_workers: int = Field(default=8, ge=1, le=24)
    user_agent: str = "NepalMorningBrief/1.0 (daily RSS/API digest)"
    senders: list[Literal["gmail_smtp", "file"]] = Field(default_factory=lambda: ["gmail_smtp"])
    sections: list[SectionConfig]
    llm: LlmConfig = Field(default_factory=LlmConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    file_sender: FileSenderConfig = Field(default_factory=FileSenderConfig)

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        section_ids = [section.id for section in self.sections]
        if not section_ids:
            raise ValueError("at least one section is required")
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section ids must be unique")
        if not self.senders:
            raise ValueError("at least one sender must be configured")
        if len(self.senders) != len(set(self.senders)):
            raise ValueError("senders must not contain duplicates")
        if self.llm_candidates < max(section.count for section in self.sections):
            raise ValueError("llm_candidates must be at least the largest section count")
        return self


@dataclass(slots=True)
class AppConfig:
    settings: Settings
    sources: list[SourceConfig]
    config_dir: Path
    project_root: Path

    def enabled_sources(self, section_id: str | None = None) -> list[SourceConfig]:
        return [
            source
            for source in self.sources
            if source.enabled and (section_id is None or source.section == section_id)
        ]


def _read_yaml(path: Path) -> object:
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc


def load_settings(path: Path) -> Settings:
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid settings in {path}: {exc}") from exc


def load_sources(path: Path) -> list[SourceConfig]:
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping with a 'sources' list")
    try:
        return SourcesFile.model_validate(data).sources
    except ValidationError as exc:
        raise ConfigError(f"Invalid sources in {path}: {exc}") from exc


def load_config(
    config_dir: Path | str | None = None,
    *,
    settings_path: Path | str | None = None,
    sources_path: Path | str | None = None,
) -> AppConfig:
    base = Path(config_dir) if config_dir is not None else PROJECT_ROOT / "config"
    settings_file = Path(settings_path) if settings_path is not None else base / "settings.yaml"
    sources_file = Path(sources_path) if sources_path is not None else base / "sources.yaml"

    settings = load_settings(settings_file)
    sources = load_sources(sources_file)

    known_sections = {section.id for section in settings.sections}
    unknown = sorted({source.section for source in sources} - known_sections)
    if unknown:
        raise ConfigError(
            "Sources reference unknown section(s): "
            + ", ".join(unknown)
            + ". Add them under settings.sections or fix sources.yaml."
        )

    for section in settings.sections:
        if not any(source.enabled and source.section == section.id for source in sources):
            raise ConfigError(f"Section '{section.id}' has no enabled sources")

    return AppConfig(
        settings=settings,
        sources=sources,
        config_dir=base,
        project_root=PROJECT_ROOT,
    )
