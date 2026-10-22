"""Configuration for the weekly tech-jobs digest."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..config import PROJECT_ROOT, ConfigError


class LinkedInSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=2, max_length=80)
    url: str = Field(min_length=8)

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        return value


class JobsEmailConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_name: str = Field(default="Nepal Tech Jobs", min_length=2, max_length=80)
    subject_prefix: str = Field(default="Nepal Tech Jobs", min_length=2, max_length=80)


class JobsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    max_items: int = Field(default=10, ge=1, le=30)
    lookback_days: int = Field(default=30, ge=1, le=90)
    min_salary_npr: int = Field(default=40000, ge=0, le=1_000_000)
    include_salary_not_disclosed: bool = True
    request_timeout_seconds: int = Field(default=20, ge=5, le=60)
    user_agent: str = "NepalMorningBrief-Jobs/1.0 (weekly jobs digest)"
    levels: list[str] = Field(min_length=1)
    title_patterns: list[str] = Field(min_length=1)
    exclude_title_patterns: list[str] = Field(default_factory=list)
    linkedin_searches: list[LinkedInSearch] = Field(default_factory=list)
    email: JobsEmailConfig = Field(default_factory=JobsEmailConfig)

    @field_validator("title_patterns", "exclude_title_patterns")
    @classmethod
    def validate_patterns(cls, values: list[str]) -> list[str]:
        for value in values:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"invalid regular expression {value!r}: {exc}") from exc
        return values


def load_jobs_config(path: Path | str | None = None) -> JobsConfig:
    config_path = Path(path) if path is not None else PROJECT_ROOT / "config" / "jobs.yaml"
    if not config_path.is_file():
        raise ConfigError(f"Jobs configuration file not found: {config_path}")
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{config_path} must contain a YAML mapping")
    try:
        return JobsConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid jobs configuration in {config_path}: {exc}") from exc
