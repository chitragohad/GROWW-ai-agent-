# Phase 1 Run Notes

Live ingestion against Groww (`com.nextbillion.groww`) on 2026-06-10.

## Observed ratios (10-week window)

| Metric | Count |
|--------|-------|
| Raw reviews scraped | 5,000 (config `max_reviews` cap) |
| Normalized reviews kept | 890 |
| Keep rate | ~17.8% |

## Filter breakdown

| Filter | Dropped |
|--------|---------|
| &lt; 8 words | 3,909 |
| Emoji | 107 |
| Non-English / language | 94 |
| Duplicates | 0 |

Architecture expected ~5,000 raw → ~800–900 normalized (~17%); observed **890 normalized** aligns with that range.

## Cache

- First run: `from_cache: false` — live scrape ~31s
- Second run (same day, same `window_weeks`): `from_cache: true` — instant

Cache path: `data/cache/groww/{YYYY-MM-DD}/`
