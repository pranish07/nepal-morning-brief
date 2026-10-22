import json

import pytest

from nmb.config import LlmConfig, SectionConfig
from nmb.llm.base import CurationValidationError, LlmQuotaError, parse_curation_json
from nmb.llm.gemini import GeminiClient


def _section() -> SectionConfig:
    return SectionConfig(id="nepal", name="Nepal", count=2)


def test_valid_llm_json_is_mapped_to_selected_ids(make_article):
    first = make_article(title="First headline", url="https://example.com/first")
    second = make_article(title="Second headline", url="https://example.com/second")
    raw = json.dumps(
        {
            "items": [
                {
                    "id": 1,
                    "headline": "A deliberately different headline",
                    "summary": "The first event happened and matters for residents.",
                },
                {
                    "id": 2,
                    "summary": "The second event changed a local policy this week.",
                },
            ]
        }
    )

    result = parse_curation_json(raw, [first, second], 2)

    assert [item.url for item in result] == ["https://example.com/first", "https://example.com/second"]
    assert result[0].title == "First headline"
    assert result[0].summary.startswith("The first event")


def test_fenced_json_is_accepted(make_article):
    candidate = make_article(url="https://example.com/one")
    payload = {
        "items": [
            {
                "id": 1,
                "summary": "A valid original summary of the event.",
            }
        ]
    }
    raw = f"```json\n{json.dumps(payload)}\n```"
    result = parse_curation_json(raw, [candidate], 1)
    assert len(result) == 1


def test_json_is_extracted_from_surrounding_text(make_article):
    candidate = make_article(url="https://example.com/one")
    raw = (
        "Here is the result:\n"
        '{"items":[{"id":1,"summary":"A valid original summary of the event."}]}\n'
        "Done."
    )
    result = parse_curation_json(raw, [candidate], 1)
    assert len(result) == 1


def test_invalid_json_is_rejected(make_article):
    candidate = make_article(url="https://example.com/one")
    with pytest.raises(CurationValidationError):
        parse_curation_json("{not valid json", [candidate], 1)


def test_bad_schema_is_rejected(make_article):
    candidate = make_article(url="https://example.com/one")
    raw = json.dumps({"items": [{"id": 1}]})
    with pytest.raises(CurationValidationError):
        parse_curation_json(raw, [candidate], 1)


def test_unknown_id_is_rejected(make_article):
    candidate = make_article(url="https://example.com/one")
    raw = json.dumps(
        {
            "items": [
                {
                    "id": 99,
                    "summary": "A summary that should never be accepted by the parser.",
                }
            ]
        }
    )
    with pytest.raises(CurationValidationError):
        parse_curation_json(raw, [candidate], 1)


def test_too_few_items_is_rejected(make_article):
    candidates = [
        make_article(url="https://example.com/one"),
        make_article(url="https://example.com/two"),
    ]
    raw = json.dumps(
        {
            "items": [
                {
                    "id": 1,
                    "summary": "A summary long enough to pass schema validation checks.",
                }
            ]
        }
    )
    with pytest.raises(CurationValidationError):
        parse_curation_json(raw, candidates, 2)


def test_duplicate_selection_is_rejected(make_article):
    candidate = make_article(url="https://example.com/one")
    item = {
        "id": 1,
        "summary": "A summary long enough to pass schema validation checks.",
    }
    raw = json.dumps({"items": [item, item]})
    with pytest.raises(CurationValidationError):
        parse_curation_json(raw, [candidate], 2)


class _QuotaResponse:
    status_code = 429


class _QuotaSession:
    def post(self, *args, **kwargs):
        return _QuotaResponse()


def test_gemini_429_raises_quota_error(make_article):
    candidate = make_article(url="https://example.com/one")
    client = GeminiClient("test-key", LlmConfig(), session=_QuotaSession())
    section = SectionConfig(id="nepal", name="Nepal", count=1)
    with pytest.raises(LlmQuotaError):
        client.curate(section, [candidate], "en")
