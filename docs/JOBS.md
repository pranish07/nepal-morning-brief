# Weekly Nepal tech jobs

The jobs digest is separate from the daily news email. It runs on Sunday at **06:15 NPT**, with a 06:45 backup, and sends up to 10 frontend and full-stack roles in Nepal.

## Data source

- Endpoint: `https://api.merojob.com/api/v1/jobs`
- MeroJob's own frontend uses this public JSON endpoint; no login, token, or paid service is required.
- It returned 198 live listings during verification on 2026-10-22.
- Only public employer-published fields are used: title, company, level, salary, experience, location, deadline, skills, and apply URL.
- No HTML scraping is used.
- The endpoint is undocumented and can change. If it fails, the weekly email fails visibly and the daily news digest is unaffected.
- MeroJob's `job_summary` field is deliberately not used: during verification one listing had a summary for a different role. The email shows employer-provided skills instead.

LinkedIn has no public jobs API for this use case and blocks automated collection. The email contains two pre-filtered LinkedIn search links (frontend and full stack, Nepal, mid/senior, past month) instead of scraped LinkedIn listings. JobsNepal, KumariJob, and JobAxle do not expose usable feeds/APIs for this project and are not scraped.

## Selection rules

Configured in `config/jobs.yaml`:

- **Levels:** `Mid Level`, `Senior Level`, `Top Level`.
- **Included titles:** frontend / front-end / front end, full stack / full-stack / fullstack, React, Next.js, MERN, Laravel, Vue, Angular, web developer, web engineer.
- **Excluded titles:** junior, intern/internship, trainee, entry level, fresher, front desk, front office.
- **Salary:** when disclosed, the maximum must be at least **NPR 40,000/month**. Hidden salaries are included as “Not disclosed”; the API's hidden values are not displayed or used to guess.
- **Freshness:** posted within 30 days and deadline not passed.
- **Deduplication:** MeroJob job ID and URL.
- **Ordering:** newest first, then seniority, then salary ceiling.
- **Limit:** 10 listings.

Salary is a floor, not a guarantee. A listing showing `NPR 35,000–40,000/month` meets the floor at its top end and is displayed with the actual range. Non-NPR salaries are included and labeled with their own currency because they cannot be compared directly with the NPR floor.

## Schedule and state

- Primary: `30 0 * * 0` UTC = Sunday 06:15 NPT.
- Backup: `0 1 * * 0` UTC = Sunday 06:45 NPT.
- Idempotency: `state/jobs_last_sent.json`, using the Nepal calendar date.
- The workflow commits the state only after a successful send.
- If there are no matching jobs, no email is sent and the state is not updated.

## Commands

```bash
PYTHONPATH=src python -m nmb.jobs --dry-run
PYTHONPATH=src python -m nmb.jobs
```

The dry run prints the plain-text email and requires no Gmail variables. A normal run uses `GMAIL_USER`, `GMAIL_APP_PASSWORD`, and `RECIPIENT_EMAIL`.

## Workflow

`.github/workflows/weekly-jobs.yml`:

- Manual dispatch and two Sunday cron entries.
- Python 3.12 on Ubuntu 24.04.
- Gmail secrets only; no Gemini secret is needed.
- Commits `state/jobs_last_sent.json` with a rebase before push.
- Writes a failure summary if the job fails.

## Verification

Tests cover parsing, hidden salary handling, salary floor, junior/entry/expired filtering, rendering, and weekly idempotency. The checked-in `config/jobs.yaml` is loaded by the tests, so configuration drift is caught.
