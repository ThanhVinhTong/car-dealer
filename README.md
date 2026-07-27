# BMW Marketplace Scraper

A local-first Python pipeline that generates BMW Facebook Marketplace
searches from existing PostgreSQL/Supabase reference data, scrapes listing
cards, normalizes eligible cars, persists them, and exports the results to CSV.

## Features

- Reads existing make and model reference data from PostgreSQL/Supabase.
- Generates Facebook Marketplace URLs from BMW model records and `MIN_PRICE`.
- Scrapes generated targets with Playwright Chromium.
- Keeps BMW listings and removes obvious non-cars, parts, and accessories.
- Drops known manufacturing years before 2012.
- Detects explicit BMW E/F/G chassis codes and drops E-generation listings.
- Maps BMW titles to existing model-family records.
- Applies the required BMW Series processing priority.
- Upserts one car per source/listing ID and records real price changes.
- Preserves Marketplace listing IDs as text for Excel-safe CSV output.
- Never modifies make/model reference data.

## Pipeline

1. Load runtime configuration.
2. Connect to the existing PostgreSQL/Supabase database.
3. Read the existing `makes` and `models` reference tables.
4. Generate BMW Marketplace search targets.
5. Scrape each generated target.
6. Collect and deduplicate raw listings.
7. Parse and normalize listing data.
8. Filter non-BMW, parts, pre-2012, and E-generation results.
9. Map BMW listings to existing model-family records.
10. Upsert cars and append initial/changed valid prices to price history.
11. Export normalized results to CSV.

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
| `CARS_TABLE` | `cars` |
| `PRICE_HISTORY_TABLE` | `car_price_history` |
| `PRICE_HISTORY_PRICE_COLUMN` | `price_aud` |
| `PRICE_HISTORY_RECORDED_AT_COLUMN` | `recorded_at` |
| `SCRAPER_SOURCE` | `facebook_marketplace` |
| `EXPORT_DIR` | `exports` |
| `LOG_LEVEL` | `INFO` |
| `HEADLESS` | `true` |
| `REQUEST_DELAY_SECONDS` | `2.0` |
| `MAX_RESULTS_PER_SEARCH_URL` | `50` |

The application does not create tables, run migrations, or modify make/model
rows. Car and price-history writes use the already deployed schema.

## Database Persistence

The persistence boundary is `PostgresStorage.upsert_car()` or the batch helper
`PostgresStorage.upsert_cars()`.

- Listing identity is exactly `(source, listing_id)`.
- The database must enforce `UNIQUE (source, listing_id)` on `cars`.
- A first observation inserts one car.
- Later observations update mutable car fields while preserving the original
  `first_seen_at` and `created_at`.
- Missing values do not erase known values.
- An older observation cannot roll back a newer car or price.
- A valid initial price creates one history row.
- A later valid price change creates one history row.
- An unchanged, missing, zero, negative, fractional, or otherwise invalid price
  creates no history row.
- Multiple copies of one listing in a batch are reduced to the newest
  observation. Different listing IDs are never merged based on similar details.

The documented `cars` schema does not contain a `description` column, so the
current upsert updates only the known `cars` columns below. If the deployed
schema includes description under another name, that mapping must be confirmed
before it can be persisted safely.

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

## Apify Actor

The repository includes a separate Apify Actor entry point that collects raw
Marketplace cards into the Actor run's default dataset:

```text
Apify input
  -> generated BMW search targets
  -> FacebookMarketplaceScraper
  -> raw listing dataset
```

The Actor deliberately does not load `DATABASE_URL`, parse cars, write
Supabase rows, create price history, or export CSV. Khanh's webhook backend
owns dataset parsing and persistence after the Actor run completes.

Actor input example:

```json
{
  "marketplaceLocation": "perth",
  "minPrice": 5000,
  "modelNames": ["3 Series"],
  "maxResultsPerSearchUrl": 5,
  "requestDelaySeconds": 2
}
```

The input form also requires `facebookStorageState`, an encrypted secret
Playwright storage-state object captured from an authenticated Facebook
session. It is intentionally omitted from examples and must never be committed
or copied into logs, documentation, or dataset output. The local capture path
`playwright/.auth/facebook.json` is gitignored.

Package files are under `.actor/`; the runtime entry point is
`app/apify_main.py`. After installing and authenticating the Apify CLI, deploy
from the repository root:

```bash
apify validate-schema .actor/input_schema.json
apify push
```

The Actor `dukich/bmw-facebook-marketplace-scraper` version `1.0` completed an
authenticated five-item cloud smoke test on 27 July 2026. The hardened package
was subsequently published successfully as build `1.0.7`. Its output contract
is raw: `price_text`, listing text, and search metadata are passed to the
existing backend parser. A pre-2012 or E-generation listing in this dataset is
expected and must be rejected by `CarParser` before database insertion.

The complete configuration, output contract, operating procedure,
troubleshooting notes, and Khanh checklist are in
[APIFY-HANDOFF.md](APIFY-HANDOFF.md).

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
preservation, transactional car upserts, price-history rules, database
deduplication, CSV export, and both supported entry points.

Current verification is recorded in [implementation-note.md](implementation-note.md).

## Project Structure

```text
app/
  apify_main.py
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
    capture_facebook_session.py
    config.py
    logger.py
    normalize.py
    search_urls.py
tests/
.actor/
  actor.json
  input_schema.json
  dataset_schema.json
  output_schema.json
  Dockerfile
  requirements.txt
APIFY-HANDOFF.md
exports/
requirements.txt
```

## Non-Goals

The current implementation still excludes:

- schema creation and migrations;
- changes to make/model reference data;
- Redis and schedulers;
- notifications and dashboards;
- Gumtree and dealer sites;
- Apify webhook and run-status APIs;
- non-Apify cloud deployment;
- `queries.txt`.

## Handoff

Use [APIFY-HANDOFF.md](APIFY-HANDOFF.md) for the Actor-to-backend handoff.
Implementation history and verification evidence are recorded in
[implementation-note.md](implementation-note.md).
