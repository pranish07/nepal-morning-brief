# Sources

All feeds below were checked on **2026-10-22** with a clear `NepalMorningBrief/1.0` User-Agent. A status of "200" means the endpoint returned a parseable RSS/Atom feed or the expected JSON; it does not guarantee that every item is recent.

## Nepal

| id | Publisher | URL | Type | Language | Verified |
| --- | --- | --- | --- | --- | --- |
| `kathmandu-post` | The Kathmandu Post | https://kathmandupost.com/rss | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `onlinekhabar-en` | Online Khabar English | https://english.onlinekhabar.com/feed | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `onlinekhabar-ne` | Online Khabar | https://www.onlinekhabar.com/feed | RSS 2.0 | ne | 2026-10-22, HTTP 200 |
| `ratopati` | Ratopati | https://ratopati.com/feed | RSS 2.0 | ne | 2026-10-22, HTTP 200 |
| `annapurna-post` | Annapurna Post | https://annapurnapost.com/rss | RSS 2.0 | ne | 2026-10-22, HTTP 200 |
| `republica` | Republica | https://myrepublica.nagariknetwork.com/feeds | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `khabarhub` | Khabarhub | https://english.khabarhub.com/feed | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `nepalnews` | Nepalnews | https://nepalnews.com/feed | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `nepalitimes` | Nepali Times | https://nepalitimes.com/feed | RSS 2.0 | en | 2026-10-22, HTTP 200 |

Notes:

- The Kathmandu Post feed has no per-item `pubDate`. Article URLs contain `/YYYY/MM/DD/`, so the parser uses that date as the publish date. The time is treated as 00:00 NPT.
- Annapurna Post items also have no per-item dates. The parser uses the feed channel's `lastBuildDate` for those items. This is a limitation of the feed, not a scrape. If precise times are required, disable this source until the publisher adds item dates.
- Republica's `/feeds` endpoint returns XML despite a `text/html` content type. Its `/rss` alias returned HTTP 503 during verification.
- Timestamps with an explicit offset are normalized to UTC. Timestamps with no offset, and dates recovered from URLs, are assumed to be Nepal local time (NPT). Feed-parser `*_parsed` values are already UTC and take priority.

## World

| id | Publisher | URL | Type | Language | Verified |
| --- | --- | --- | --- | --- | --- |
| `bbc-world` | BBC World | https://feeds.bbci.co.uk/news/world/rss.xml | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `aljazeera` | Al Jazeera | https://www.aljazeera.com/xml/rss/all.xml | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `guardian-world` | The Guardian | https://www.theguardian.com/world/rss | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `npr-world` | NPR | https://feeds.npr.org/1004/rss.xml | RSS 2.0 | en | 2026-10-22, HTTP 200 |

## AI

| id | Publisher | URL | Type | Language | Verified |
| --- | --- | --- | --- | --- | --- |
| `hn-ai` | Hacker News | https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI | Algolia JSON API | en | 2026-10-22, HTTP 200 |
| `verge-ai` | The Verge AI | https://www.theverge.com/rss/ai-artificial-intelligence/index.xml | Atom | en | 2026-10-22, HTTP 200 |
| `mit-tech-review-ai` | MIT Technology Review | https://www.technologyreview.com/topic/artificial-intelligence/feed | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `openai-news` | OpenAI | https://openai.com/news/rss.xml | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `deepmind-blog` | Google DeepMind | https://deepmind.google/blog/rss.xml | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `huggingface-blog` | Hugging Face | https://huggingface.co/blog/feed.xml | RSS 2.0 | en | 2026-10-22, HTTP 200 |

The Hacker News source uses the public Algolia API, filtered by the `keywords` list in `config/sources.yaml`. The request adds a `created_at_i` numeric filter so old stories are excluded server-side.

## Programming

| id | Publisher | URL | Type | Language | Verified |
| --- | --- | --- | --- | --- | --- |
| `hn-programming` | Hacker News | https://hn.algolia.com/api/v1/search_by_date?tags=story&query=programming | Algolia JSON API | en | 2026-10-22, HTTP 200 |
| `devto` | DEV Community | https://dev.to/api/articles?top=1&per_page=30 | dev.to JSON API | en | 2026-10-22, HTTP 200 |
| `lobsters` | Lobsters | https://lobste.rs/rss | RSS 2.0 | en | 2026-10-22, HTTP 200 |
| `github-blog` | GitHub Blog | https://github.blog/feed/ | RSS 2.0 | en | 2026-10-22, HTTP 200 |

## Dropped during verification

| Publisher | URL tried | Result |
| --- | --- | --- |
| Setopati (English) | https://en.setopati.com/feed | HTTP 500 on 2026-10-22. The homepage advertises this Atom feed, but it did not return usable XML. Not enabled. |
| The Himalayan Times | https://thehimalayantimes.com/feed | HTTP 404 on 2026-10-22. `/rss` returned an HTML page, not a feed. A working feed URL was not found. Not enabled. |

These are not scraped. If the publishers restore a valid feed, add them back using the runbook below.

## Replacing a dead feed

1. Check the publisher homepage source for `<link rel="alternate" type="application/rss+xml">` or an advertised RSS page.
2. Verify the URL directly, for example:
   ```bash
   curl -sS -L --max-time 20 -A "NepalMorningBrief/1.0" -D - https://example.com/feed.xml -o /tmp/feed.xml
   head -c 300 /tmp/feed.xml
   ```
   The response should begin with an RSS or Atom declaration.
3. Update `url` for the existing source id in `config/sources.yaml`. Keep the id stable so weights and docs stay meaningful.
4. Run the parser tests and a one-section local dry run:
   ```bash
   python -m pytest
   PYTHONPATH=src python -m nmb.main --section nepal --dry-run
   ```
5. Update this file with the new URL, the verification date, and any feed quirks.
6. If no valid feed exists, leave the source disabled or remove it and note the reason here. Do not add HTML scraping.

## Rate limits and etiquette

- One request per source per daily run, with a maximum of two retries after a 10-second timeout.
- A descriptive User-Agent is sent on every request.
- Hacker News and dev.to use their public APIs rather than page scraping.
- Feeds are for personal, low-volume use. Keep request volume low and follow each publisher's terms.
