# Architecture

Nepal Morning Brief is a single-process Python 3.12 application started by GitHub Actions. It has no database and no web server. All changing behavior is read from two YAML files.

## Layers

| Layer | Modules | Responsibility |
| --- | --- | --- |
| Configuration | `nmb.config`, `config/*.yaml` | Load, validate, and cross-check settings and sources. |
| Domain | `nmb.models` | `Article`, `Section`, and `Digest` dataclasses. |
| Sources | `nmb.sources` | Fetch RSS, Hacker News, and dev.to data and normalize it to `Article`. |
| Pipeline | `nmb.pipeline` | Parallel fetch, dedupe, rank, summarize, and fallback. |
| LLM | `nmb.llm` | Provider-neutral curation interface and Gemini JSON client. |
| Render | `nmb.render` | Jinja HTML and plain-text email bodies. |
| Delivery | `nmb.senders` | Gmail SMTP and optional static-file output. |
| Orchestration | `nmb.main` | CLI, environment checks, idempotency, run summary, exit codes. |

## Interfaces

```python
class Source(ABC):
    def fetch_articles(self, since: datetime) -> list[Article]: ...

class LlmClient(ABC):
    def curate(
        self,
        section: SectionConfig,
        candidates: list[Article],
        output_language: str,
    ) -> CurationResult: ...

class Sender(ABC):
    def send(
        self,
        subject: str,
        text_body: str,
        html_body: str,
        digest: Digest,
    ) -> None: ...
```

`Source` implementations are `RssSource`, `HackerNewsSource`, and `DevToSource`, selected by `nmb.sources.registry.build_source`. `LlmClient` is implemented by `GeminiClient`; `build_llm_client` is the single provider factory. `Sender` is implemented by `GmailSmtpSender` and `FileSender`; active senders come from `settings.senders`.

## Data flow

```text
config/settings.yaml + config/sources.yaml
                |
                v
        build_sources()
                |
                v
 fetch_all() -- parallel, per-source timeout and retries
                |
                v
 dedupe_articles() -- canonical URL + fuzzy title, per section
                |
                v
 rank_all() -- recency + weight + cross-source + HN points
                |
                v
 summarize_sections() -- one Gemini JSON call per section
                |
                v
 render_digest() -- subject, text/plain, text/html
                |
                v
 senders --> Gmail SMTP / optional public files
                |
                v
 state/last_sent.json
```

`Article.published_at` is stored as timezone-aware UTC. NPT is applied only for display and for the "one digest per NPT day" check.

## Failure handling

- **Source failure:** each source runs in its own worker. A source is retried up to `fetch_retries` times (default 2) with exponential backoff. After the final failure it is recorded in `failed_sources`, logged, and skipped. The run continues.
- **No items:** sections can be empty. Rendering still succeeds and reports 0 in that section.
- **LLM failure:** any exception from `LlmClient.curate`, including HTTP 429, timeout, invalid JSON, schema failure, unknown URL, duplicates, or too few selected items, triggers the fallback for that section. The fallback is the top-ranked candidates with original titles and links and no summaries.
- **Rendering failure:** treated as a hard failure because there is nothing safe to send.
- **Send failure:** Gmail transient errors are retried up to 3 attempts with backoff. Authentication and recipient rejection are not retried. The workflow fails visibly and the state file is not updated.
- **Idempotency failure:** an unreadable or malformed state file fails closed rather than risking a duplicate email.
- **Missing environment:** configuration errors exit with code 2 and a message naming the missing variable. Values and secrets are never printed.

The GitHub workflow itself is the final safety net: a non-zero exit fails the job, produces a failing Actions notification, and appends an error summary to the job summary.

## LLM safety and validation

Feed content is untrusted data. The Gemini system prompt states that titles, descriptions, URLs, and source names are data only and must never be treated as instructions. Candidate data is JSON-encoded inside a delimited block. The model must return JSON only.

The response is validated in two stages:

1. Pydantic validates the exact object shape and field lengths.
2. Application validation requires at least the configured count of items, known candidate URLs only, no duplicate stories, and a non-empty summary for each item.

If any validation step fails, the section is replaced by the ranked fallback. The digest is always renderable.

## Logging

Logging is newline-delimited JSON to stderr. Events include source-level fetch results, retries, failures, LLM token counts, sender results, and one final `run.complete` event with:

- run duration
- items fetched and deduped
- per-source counts
- failed sources
- LLM tokens used
- fallback sections and errors
- sender names, subject, and per-section item counts

Recipient, sender address, app password, and API key are redacted from sender errors and are never included in normal events.

## Idempotency

`StateStore` stores only the last NPT send date, the send timestamp, and the timezone name in `state/last_sent.json`. Before fetching, a normal run compares the stored date with the current NPT date. If they match, it exits 0 without sending. After every active sender succeeds, it atomically writes the new state. The workflow commits that file back with `contents: write` and skips the commit when the file is unchanged.

## Configuration boundaries

Adding a source requires only `config/sources.yaml`. Adding a section requires a section entry in `config/settings.yaml` plus at least one enabled source with that section id. Item counts, output language, lookback, model, sender selection, source weights, and ranking weights are YAML values. The only schedule change is the cron expression in the workflow.
