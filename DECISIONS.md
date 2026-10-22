# Decisions

## 1. RSS and public APIs instead of HTML scraping

**Context:** Nepali and international publishers change their page markup often. Scraping is brittle, creates load, and makes robots and terms harder to respect. Most target publishers offer feeds or public APIs.

**Decision:** Collect from RSS/Atom feeds, the Hacker News Algolia API, and the dev.to API only. Do not implement an HTML scraping path.

**Consequences:** Feeds are more stable and cheap to poll. Some publishers may omit per-item timestamps or provide a limited number of stories. Sources without a usable feed are excluded rather than scraped. A future HTML fallback would need robots.txt checks, a clear User-Agent, and title/link/date extraction only.

## 2. GitHub Actions cron with a primary and backup schedule

**Context:** GitHub Actions is free for public repositories and needs no server. Scheduled runs are best-effort, can be delayed, and can be dropped.

**Decision:** Run at `45 23 * * *` UTC (05:30 NPT) as the primary and `15 00 * * *` UTC (06:00 NPT) as the backup. Use a concurrency group and a state file so the backup does not duplicate a successful primary.

**Consequences:** The digest normally arrives around 06:00 NPT. The early primary provides a buffer for delays. Occasional delays or skipped runs are possible; `workflow_dispatch` provides a manual recovery path. The two schedules are free because they use minimal Actions minutes.

## 3. Gemini free tier with a deterministic fallback

**Context:** Summaries need an LLM, but the project must remain free and the email must still be delivered when the provider is unavailable or over quota.

**Decision:** Use a configurable Gemini Flash model through the free-tier REST API, validate structured JSON with Pydantic, and fall back to the pre-ranked stories with original titles and links and no summaries on any LLM failure.

**Consequences:** Most days get original summaries without cost. A 429, timeout, malformed response, or schema violation degrades gracefully instead of dropping the newsletter. The fallback email is less useful but always deliverable. `LlmClient` keeps the provider replaceable.

## 4. Gmail SMTP with a Google App Password

**Context:** There is one recipient and no desire to run a mail service or use a paid email API.

**Decision:** Send through `smtp.gmail.com:465` over SSL using `smtplib` and a Google App Password stored as a GitHub secret.

**Consequences:** No third-party email service or credit card is required. The Google account must have 2-Step Verification and an App Password, and Google may rate-limit or flag unusual sending. The App Password can be revoked independently. Credentials are passed only through environment secrets and never logged.

## 5. Idempotency through a committed state file

**Context:** Two cron triggers exist, and GitHub may delay, retry, or overlap scheduled runs. Sending twice in one morning would be a poor experience.

**Decision:** Record the NPT date of the last successful send in `state/last_sent.json`. Check it before any fetching or sending. Update it atomically only after all active senders succeed, and commit it from the workflow.

**Consequences:** The backup cron becomes a safe retry. Manual runs are also protected. The state file is public but contains only a date, a timestamp, and the timezone name. If the commit fails, the job fails visibly; a later run could duplicate the email, which is preferable to silently losing the state record. A malformed state file fails closed.

## 6. Public repository

**Context:** GitHub Actions minutes are unlimited for public repositories, while private repositories consume the account's free quota. The workflow needs to commit its state file.

**Decision:** Keep the repository public and keep every personal or secret value out of the tree. The recipient is read only from `RECIPIENT_EMAIL`; secrets live in GitHub Actions secrets.

**Consequences:** Free scheduling and state commits. The code, source list, and last-send date are public. There is no recipient address, app password, or API key in commits, fixtures, logs, or documentation. Digest content is not published by default; the optional file sender is disabled.
