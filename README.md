# BMW Marketplace Scraper

A local-first Python V1 pipeline that generates BMW Facebook Marketplace
searches from existing PostgreSQL/Supabase reference data, scrapes listing
cards, normalizes eligible cars, and exports the results to CSV.

## Features

- Reads existing make and model reference data from PostgreSQL/Supabase.
- Generates Facebook Marketplace URLs from BMW model records and `MIN_PRICE`.
- Scrapes generated targets with Playwright Chromium.
- Keeps BMW listings and removes obvious non-cars, parts, and accessories.
- Drops known manufacturing years before 2012.
- Detects explicit BMW E/F/G chassis codes and drops E-generation listings.
- Maps BMW titles to existing model-family records.
- Applies the required BMW Series processing priority.
- Preserves Marketplace listing IDs as text for Excel-safe CSV output.
- Does not write cars, reference data, or price history to the database.

## V1 Pipeline

1. Load runtime configuration.
2. Connect to the existing PostgreSQL/Supabase database.
3. Read the existing `makes` and `models` reference tables.
4. Generate BMW Marketplace search targets.
5. Scrape each generated target.
6. Collect and deduplicate raw listings.
7. Parse and normalize listing data.
8. Filter non-BMW, parts, pre-2012, and E-generation results.
9. Map BMW listings to existing model-family records.
10. Export normalized results to CSV.

## BMW Rules

| Rule | Behavior |
|---|---|
| Make | BMW is retained. MINI, Mercedes, and other makes are dropped. |
| Manufacturing year | 2012 or newer is retained. A known year before 2012 is dropped. A missing year remains unknown and is marked internally for review. |
| Chassis generation | Explicit F/G codes are retained and normalized. Explicit E codes are dropped. A missing code remains unknown. |
| Series priority | 3/4 = 1, 2 = 2, 5/6 = 3, 7 = 4, 1 = 5. Unranked families follow at priority 6. |

The priority is applied to generated search targets and normalized CSV row
order. Corresponding M models inherit their numbered family priority where
applicable.

## Requirements

- Python 3.10 or newer
- PostgreSQL or Supabase database access
- Playwright Chromium

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Configuration

Create a local `.env` file. Never commit this file.

Required variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL/Supabase connection string |
| `MARKETPLACE_LOCATION` | Facebook Marketplace location path, such as `perth` |
| `MIN_PRICE` | Minimum Marketplace search price in AUD |

Optional variables:

| Variable | Default |
|---|---|
| `SCRAPER_SOURCE` | `facebook_marketplace` |
| `EXPORT_DIR` | `exports` |
| `LOG_LEVEL` | `INFO` |
| `HEADLESS` | `true` |
| `REQUEST_DELAY_SECONDS` | `2.0` |
| `MAX_RESULTS_PER_SEARCH_URL` | `50` |

The application only reads reference data. It does not create tables, run
migrations, modify make/model rows, or write cars to the database.

## Run

Preferred:

```bash
python -m app.main
```

Direct script execution is also supported:

```bash
python app/main.py
```

CSV files are written to `exports/` unless `EXPORT_DIR` is changed.

## CSV Output

The exporter writes the existing `cars` table shape:

```text
car_id
source
listing_id
normalized_url
title
make_id
model_id
manufacture_year
current_price_aud
sell_location
status
first_seen_at
last_seen_at
created_at
updated_at
```

`listing_id` is extracted from the canonical Marketplace item URL and remains
a string internally. CSV output prefixes the value with Excel's apostrophe
text marker to prevent scientific notation and digit rounding.

Internal fields such as chassis generation, filter status, review state, and
Series priority are not added to CSV because the export must retain the exact
`cars` columns above.

## Tests

Run the complete suite:

```bash
python -m unittest discover -s tests
```

The suite covers URL generation, target generation, BMW filtering, year
eligibility, E/F/G generation handling, Series priority, price and odometer
parsing, year extraction, BMW model mapping, parts filtering, listing-ID
preservation, CSV export, and both supported entry points.

Current verification: 28 tests passing.

## Project Structure

```text
app/
  main.py
  parsers/
    car_parser.py
  scrapers/
    base.py
    fb_marketplace.py
  storage/
    csv_exporter.py
    postgres.py
  utils/
    bmw.py
    config.py
    logger.py
    normalize.py
    search_urls.py
tests/
exports/
PROJECT-STATUS.md
implementation-note.md
CODEX-HANDOFF-PROMPT.md
requirements.txt
```

## V1 Non-Goals

V1 intentionally excludes:

- database inserts or upserts for cars;
- price history;
- schema creation and migrations;
- changes to make/model reference data;
- Redis and schedulers;
- notifications and dashboards;
- Gumtree and dealer sites;
- Apify-specific code;
- cloud deployment;
- `queries.txt`.

## Handoff

Use [CODEX-HANDOFF-PROMPT.md](CODEX-HANDOFF-PROMPT.md) when moving the
project to another folder or starting a new Codex task. It contains the
current constraints, behavior, verification command, and a placeholder for
the next requested change.

More implementation history is recorded in
[implementation-note.md](implementation-note.md), with the consolidated
status in [PROJECT-STATUS.md](PROJECT-STATUS.md).
