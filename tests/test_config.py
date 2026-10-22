from pathlib import Path

import pytest

from nmb.config import ConfigError, load_config
from nmb.timeutil import UTC

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_config_loads_with_required_counts():
    config = load_config(ROOT / "config")
    counts = {section.id: section.count for section in config.settings.sections}
    assert counts == {"nepal": 10, "world": 5, "ai": 5, "programming": 5}
    assert config.settings.senders == ["gmail_smtp"]


def test_sources_are_unique_and_have_known_sections():
    config = load_config(ROOT / "config")
    ids = [source.id for source in config.sources]
    assert len(ids) == len(set(ids))
    sections = {section.id for section in config.settings.sections}
    assert all(source.section in sections for source in config.sources)


def test_all_source_urls_are_absolute_http():
    config = load_config(ROOT / "config")
    for source in config.sources:
        assert source.url.startswith(("http://", "https://"))


def test_missing_config_file_raises_clear_error(tmp_path):
    with pytest.raises(ConfigError) as exc_info:
        load_config(tmp_path)
    assert "not found" in str(exc_info.value)


def test_settings_reject_empty_senders():
    from nmb.config import Settings

    with pytest.raises(Exception):
        Settings.model_validate(
            {
                "senders": [],
                "sections": [{"id": "nepal", "name": "Nepal", "count": 10}],
            }
        )


def test_npt_offset_is_used():
    from datetime import datetime

    from nmb.timeutil import NPT

    instant = datetime(2026, 10, 22, 0, 15, tzinfo=UTC)
    assert instant.astimezone(NPT).hour == 6
    assert instant.astimezone(NPT).minute == 0
