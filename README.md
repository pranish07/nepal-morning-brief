# Nepal Morning Brief

A free, serverless daily news digest that runs on GitHub Actions and emails one newsletter every morning at about 06:00 Nepal Time (NPT, UTC+05:45).

Each day it sends:

- 10 Nepal news items
- 5 world news items
- 5 AI news items
- 5 programming news items

Normally every item contains an original 1-2 sentence summary, the source name, a link to the publisher, and the publish time in NPT. If Gemini is unavailable, the fallback digest keeps the headline, source, link, and time without summaries. Summaries are generated only from feed titles and short feed descriptions. Article text is never reproduced.

## Assumptions

- "Nepali news" means news from Nepal, from both Nepali-language and English-language publishers. `output_language` can be `en`, `ne`, or `both`; the default is `en`.
- There is one recipient. Email is sent from the owner's Gmail account via SMTP.
- The repository is public, so Actions minutes are free. No personal data or secrets are committed.
- Changeable behavior belongs in `config/settings.yaml` and `config/sources.yaml`.

## How it works

1. Enabled sources are fetched in parallel from RSS feeds and public JSON APIs.
2. Items older than the lookback window (36 hours by default) are discarded.
3. Duplicate stories are removed by canonical URL and fuzzy title matching.
4. Remaining stories are pre-ranked by recency, source weight, cross-source mentions, and Hacker News points.
5. The top candidates in each section go to Gemini Flash, which selects the final stories and writes JSON summaries.
6. If Gemini fails, returns bad JSON, or hits a quota limit, the pre-ranked stories are used with their original headlines and links and no summary.
7. A responsive HTML email and a plain-text email are rendered and sent through Gmail SMTP.
8. The NPT send date is stored in `state/last_sent.json` so a second scheduled run does not send a duplicate.

No server, database, paid API, or credit card is required. There is no HTML scraping: all sources are RSS or documented public APIs.

## Project layout

```text
nepal-morning-brief/
  .github/workflows/daily.yml
  config/sources.yaml
  config/settings.yaml
  docs/SOURCES.md
  src/nmb/
    config.py
    models.py
    main.py
    sources/
    pipeline/
    llm/
    senders/
    render/
  state/last_sent.json
  tests/
  README.md
  ARCHITECTURE.md
  DECISIONS.md
```

## Setup checklist

1. Create a **public** GitHub repository and push this project to it.
2. Enable 2-Step Verification on the Google account that will send the email.
3. Create a Google **App Password** for Mail. Do not use the normal account password.
4. Get a free Gemini API key from Google AI Studio.
5. In the repository, open **Settings > Secrets and variables > Actions** and add these four repository secrets:
   - `GEMINI_API_KEY`
   - `GMAIL_USER` (the full Gmail address)
   - `GMAIL_APP_PASSWORD` (the 16-character App Password; remove spaces when pasting)
   - `RECIPIENT_EMAIL` (the destination address)
6. Open the **Actions** tab and enable workflows if GitHub asks.
7. Run **Daily Nepal Morning Brief > Run workflow** once (`workflow_dispatch`) to verify the setup.
8. If the first email lands in spam, open it and choose **Not spam**. Add the sender to contacts if needed.

Never put the recipient address, Gmail password, or Gemini key in a file in the repository.

## Local setup and use

Python 3.12 or newer is required.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"
$env:GEMINI_API_KEY = "your-gemini-key"
$env:GMAIL_USER = "you@example.com"
$env:GMAIL_APP_PASSWORD = "your-app-password"
$env:RECIPIENT_EMAIL = "you@example.com"

python -m nmb.main --dry-run
python -m nmb.main --send-test
```

Bash:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=src
export GEMINI_API_KEY="your-gemini-key"
export GMAIL_USER="you@example.com"
export GMAIL_APP_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="you@example.com"

python -m nmb.main --dry-run
python -m nmb.main --send-test
```

CLI behavior:

- `--dry-run` fetches, ranks, summarizes, prints the plain-text digest, and sends nothing. It requires `GEMINI_API_KEY` but does not require Gmail variables and does not update the state file.
- `--send-test` sends a short test email through Gmail and exits. It requires the three Gmail variables but does not call Gemini.
- `--section ID` runs only one configured section, for example `--section nepal`.
- A normal run sends the email once per NPT calendar day. A second run on the same day exits successfully without sending.

Run the tests without network access:

```bash
python -m pytest
```

### Test in GitHub Actions

After the four secrets are configured, open **Actions > Daily Nepal Morning Brief > Run workflow**. A manual run performs the real pipeline and sends a real email. Check the job log for the structured JSON events and the final `run.complete` summary. If the state file says today's digest was already sent, the run exits successfully without sending. Use local `--dry-run` for a non-sending pipeline test.

## Add or change sources

Edit `config/sources.yaml`. A source has these fields:

```yaml
- id: example-feed
  name: Example News
  section: nepal
  url: https://example.com/feed.xml
  type: rss
  language: en
  weight: 1.0
  enabled: true
```

- `type` is `rss`, `hn_api`, or `devto_api`.
- `section` must match an `id` in `config/settings.yaml`.
- `weight` is a ranking multiplier. Keep it between roughly 0.8 and 1.3.
- `enabled: false` temporarily disables a source without deleting it.
- Optional `keywords` filters Hacker News titles. Optional `max_items` limits items kept per source.

Before adding a feed, verify that it responds and returns RSS/Atom or the expected JSON. Follow the replacement runbook in [docs/SOURCES.md](docs/SOURCES.md) and update the verification date there.

## Change sections, counts, language, or schedule

- Section names and counts (10/5/5/5) are in `config/settings.yaml` under `sections`.
- `output_language` is `en`, `ne`, or `both`.
- `lookback_hours` defaults to 36.
- `llm.model` selects the Gemini Flash model.
- `senders` defaults to `[gmail_smtp]`. The optional `file` sender writes `public/index.html` and `public/rss.xml`; it is disabled by default.
- `ranking` controls recency, source weight, cross-source, and Hacker News point contributions.

The schedule is in `.github/workflows/daily.yml`:

- `45 23 * * *` UTC = 05:30 NPT the next day (primary).
- `15 00 * * *` UTC = 06:00 NPT (backup).

Nepal is UTC+05:45, so subtract 5 hours 45 minutes to convert NPT to UTC. The primary runs 30 minutes early because GitHub scheduled jobs can be delayed. Scheduled runs are best-effort and may occasionally be delayed or dropped.

## Optional file output

To write static files instead of, or in addition to, email, add `file` to `senders` in `config/settings.yaml` and optionally set `file_sender.site_url`. Running the bot writes `public/index.html` and `public/rss.xml`. GitHub Pages hosting and deployment are intentionally not wired into the daily workflow.

## Troubleshooting

**Gmail authentication error (`535`, `SMTPAuthenticationError`, or "Username and Password not accepted")**

- Confirm `GMAIL_USER` is the full address, not an alias.
- Confirm the App Password was created for Mail and copied without spaces.
- Confirm 2-Step Verification is enabled; App Passwords are unavailable without it.
- Recreate the App Password if it was revoked.
- Make sure the recipient is set in `RECIPIENT_EMAIL` and is not hardcoded anywhere.

**Gemini quota error (`429`)**

The bot treats this as a normal LLM failure and sends the pre-ranked fallback digest without summaries. To recover summaries, wait for the free-tier quota to reset or change `llm.model` in `config/settings.yaml` to another Flash model available in your Gemini project. The email still goes out.

**Scheduled workflow did not run**

- Check the **Actions** tab and the repository's Actions permissions.
- Confirm the repository has not been inactive for 60 days; GitHub disables scheduled workflows in inactive public repositories.
- Remember that scheduled runs are best-effort and may be delayed or skipped.
- Run `workflow_dispatch` manually; idempotency prevents a duplicate email if the daily digest was already sent.
- If the state commit is blocked by a branch protection rule, allow the Actions bot to push to the branch or commit the state change manually.

**The workflow failed**

The job fails visibly and GitHub sends a failure notification. Open the job log for the redacted error and the job summary. State is recorded only after a successful send. If the run failed before sending, retrying is safe. If the email was sent but the final state commit failed, fix the push/permission problem and update the state file before rerunning to avoid a duplicate.

**Wrong publish times**

Feeds occasionally omit per-item timestamps. The parser then uses a date from the article URL when present, otherwise the feed's build time. Timestamps without an offset and URL-only dates are assumed to be Nepal local time. See [docs/SOURCES.md](docs/SOURCES.md) for the affected sources.
