import json
from datetime import datetime, timedelta

import pytest

from nmb.state import StateError, StateStore
from nmb.timeutil import UTC


def test_second_run_on_same_npt_date_is_blocked(tmp_path):
    store = StateStore(tmp_path / "last_sent.json")
    first_run = datetime(2026, 10, 22, 0, 20, tzinfo=UTC)

    assert store.already_sent_today(first_run) is False
    store.mark_sent(first_run)
    assert store.already_sent_today(first_run) is True
    assert store.already_sent_today(first_run + timedelta(hours=4)) is True


def test_next_npt_day_is_not_blocked(tmp_path):
    store = StateStore(tmp_path / "last_sent.json")
    first_run = datetime(2026, 10, 22, 0, 20, tzinfo=UTC)
    store.mark_sent(first_run)

    next_day = first_run + timedelta(days=1)
    assert store.already_sent_today(next_day) is False


def test_state_file_contains_public_date_only(tmp_path):
    path = tmp_path / "last_sent.json"
    store = StateStore(path)
    store.mark_sent(datetime(2026, 10, 22, 0, 20, tzinfo=UTC))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["last_sent_date"] == "2026-10-22"
    assert payload["timezone"] == "Asia/Kathmandu"
    assert "recipient" not in json.dumps(payload).lower()


def test_malformed_state_fails_closed(tmp_path):
    path = tmp_path / "last_sent.json"
    path.write_text("not json", encoding="utf-8")
    store = StateStore(path)
    with pytest.raises(StateError):
        store.already_sent_today(datetime(2026, 10, 22, tzinfo=UTC))
