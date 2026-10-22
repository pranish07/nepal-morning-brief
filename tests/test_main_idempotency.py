from datetime import datetime

from nmb.config import AppConfig, Settings
from nmb.main import main
from nmb.models import Digest, Section
from nmb.pipeline.fetch import FetchResult
from nmb.pipeline.summarize import SummarizeStats
from nmb.timeutil import UTC

FIXED_NOW = datetime(2026, 10, 22, 0, 20, tzinfo=UTC)


class FakeSender:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def send(self, subject, text_body, html_body, digest):
        self.calls += 1


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "senders": ["gmail_smtp"],
            "sections": [{"id": "nepal", "name": "Nepal", "count": 10}],
        }
    )


def test_second_run_on_same_npt_date_does_not_send(monkeypatch, tmp_path):
    settings = _settings()
    app = AppConfig(
        settings=settings,
        sources=[],
        config_dir=tmp_path,
        project_root=tmp_path,
    )
    sender = FakeSender()
    digest = Digest(
        generated_at=FIXED_NOW,
        sections=[Section(id="nepal", name="Nepal", count=10, articles=[])],
    )

    monkeypatch.setattr("nmb.main.load_config", lambda: app)
    monkeypatch.setattr("nmb.main.now_utc", lambda: FIXED_NOW)
    monkeypatch.setattr("nmb.main.validate_run_env", lambda *args, **kwargs: "key")
    monkeypatch.setattr("nmb.main.build_sources", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "nmb.main.fetch_all",
        lambda *args, **kwargs: FetchResult(),
    )
    monkeypatch.setattr("nmb.main.build_llm_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "nmb.main.summarize_sections",
        lambda *args, **kwargs: (digest, SummarizeStats()),
    )
    monkeypatch.setattr(
        "nmb.main.render_digest",
        lambda *args, **kwargs: ("Subject", "Plain", "<p>HTML</p>"),
    )
    monkeypatch.setattr("nmb.main.build_senders", lambda *args, **kwargs: [sender])

    assert main([]) == 0
    assert sender.calls == 1
    assert main([]) == 0
    assert sender.calls == 1
