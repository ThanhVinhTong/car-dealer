# V1 Implementation Status Report

**Report date:** 25 July 2026  
**Project:** Facebook Marketplace car scraper  
**Current status:** V1 implementation complete; unit tests pass; live end-to-end execution still depends on database and Facebook connectivity.

## Executive Summary

The local-first V1 pipeline has been implemented as a root-level Python package. It can be started with:

```bash
python -m app.main
```

Direct script execution with `python app/main.py` is also supported.

The application loads runtime configuration, reads existing make/model reference data from PostgreSQL or Supabase, generates Facebook Marketplace search URLs, scrapes listing cards, normalizes BMW vehicle listings, filters parts and non-car results, maps titles to existing BMW model-family records, and exports the final rows to CSV.

The application does not create or modify database tables and does not insert cars or price history into the database.

## Completed V1 Pipeline

| Step | Status | Implementation |
|---|---|---|
| Load configuration | Complete | Loads required `DATABASE_URL`, `MARKETPLACE_LOCATION`, and `MIN_PRICE`, plus documented optional settings. |
| Connect to PostgreSQL/Supabase | Complete | Uses `psycopg2` and closes each connection after its read operation. |
| Load reference data | Complete | Reads make and model IDs/names without modifying reference rows. |
| Generate search targets | Complete | Keeps BMW models only, skips the `unknown` model, applies Series priority, and produces deterministic Facebook Marketplace URLs using make, model, location, and minimum price. |
| Scrape generated URLs | Complete | Uses Playwright Chromium to visit only generated search targets and collect Marketplace item links. |
| Collect raw listings | Complete | Captures listing URL, URL-derived ID, card text, price text, location, images, search metadata, and scrape timestamp. |
| Parse and normalize | Complete | Normalizes URLs, titles, years, prices, odometers, locations, image URLs, timestamps, and source values. |
| Filter invalid results | Complete | Removes non-BMW results, obvious parts/accessories, known manufacture years before 2012, and detected E-generation chassis codes. Missing year/generation stays unknown. |
| Map BMW models | Complete | Maps model badges and family names to existing BMW model records, assigns chassis generation when explicit, and applies the requested Series priority. |
| Export CSV | Complete | Writes the exact requested `cars` column shape and protects long listing IDs from Excel number conversion. |

## Configuration

Required runtime variables:

- `DATABASE_URL`
- `MARKETPLACE_LOCATION`
- `MIN_PRICE`

Optional variables and defaults:

| Variable | Default |
|---|---:|
| `SCRAPER_SOURCE` | `facebook_marketplace` |
| `EXPORT_DIR` | `exports` |
| `LOG_LEVEL` | `INFO` |
| `HEADLESS` | `true` |
| `REQUEST_DELAY_SECONDS` | `2.0` |
| `MAX_RESULTS_PER_SEARCH_URL` | `50` |

Configuration is loaded at runtime. No `.env` contents were read while preparing this report.

## Database Access

Database access is read-only. The current adapter executes `SELECT` statements against the reference tables named `makes` and `models` in the implementation. It does not:

- create tables;
- run migrations;
- update make/model rows;
- insert or upsert cars;
- write price history.

The earlier Supabase failure for `db.tojwkolrbpsbifixssnq.supabase.co` was a hostname/DNS resolution failure, not a parsing or CSV problem. The database adapter now returns more useful guidance for direct-host, SSL, password-encoding, and IPv4/session-pooler connection issues. A real database connection has not yet been verified from this workspace.

## Search Target Generation

Search URLs are generated from database make/model rows and follow this shape:

```text
https://www.facebook.com/marketplace/<location>/search?minPrice=<MIN_PRICE>&query=%22<make>%20<model>%22&exact=true
```

The target builder joins each model to its make using `make_id`, keeps only the exact BMW make, ignores missing/invalid references, and skips the `unknown` model. `queries.txt` is not used.

BMW search targets use this processing priority:

| Model family | Priority |
|---|---:|
| 3 Series, 4 Series, M3, M4 | 1 |
| 2 Series, M2 | 2 |
| 5 Series, 6 Series, M5, M6 | 3 |
| 7 Series | 4 |
| 1 Series | 5 |
| X, Z, M8, and unknown/unranked families | 6 |

Priority is applied first, followed by model ID for deterministic ordering.

## Scraping Behavior

The Facebook Marketplace scraper:

- launches Playwright Chromium using the configured headless mode;
- visits each generated URL;
- locates links containing `/marketplace/item/`;
- scrolls to collect additional cards up to the configured result limit;
- deduplicates raw listings using source plus listing ID or normalized URL;
- keeps raw card text and search metadata for parsing and diagnostics;
- logs and continues when one search target fails.

It does not include login automation, CAPTCHA bypassing, proxy rotation, or Apify-specific behavior.

## Parsing and Normalization

The parser currently focuses on BMW listings as required. It recognizes BMW names and common aliases, then maps model text in this order:

1. title;
2. description;
3. generated search-target model;
4. existing BMW `unknown` model.

Supported mapping patterns include BMW 1-7 Series badges, X1-X7, X3M/X4M/X5M/X6M, M2/M3/M4/M5/M8, and Z4.

Obvious parts and accessory listings are filtered using title/description patterns such as wheels, rims, tyres, bumpers, lights, floor mats, roof racks, wrecking, and parting out. Non-BMW results are also removed.

Known manufacture years before 2012 are removed. A listing with no detected year is retained with an internal `year_filter_status` of `unknown` and `requires_review=true`; the application does not invent a year.

Explicit E/F/G chassis codes are detected from title and description text, including forms such as `F30`, `f-30`, and `G 20`. Detected E-generation listings are removed. F/G listings are retained with the normalized code, while no detected code is retained as `unknown`.

The same Series priority used for search targets is also applied to normalized result order before CSV export. Internal filter status, chassis, review, and priority fields are deliberately omitted from the fixed `cars` CSV schema.

Price parsing first uses the scraper's price field. If that field is absent, it scans the title, description, and raw card text for currency-marked values. Values such as `free`, `contact seller`, `negotiable`, and odometer text are not treated as prices.

## CSV Output

The current exporter writes these columns in this exact order:

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

All fields are quoted. Extra parser/debug fields are deliberately excluded.

### Listing ID Handling

`listing_id` is extracted from the canonical Marketplace item URL before any source-provided ID is considered. It remains a Python string throughout parsing and normalization.

For CSV output only, the value receives Excel's leading apostrophe text marker. For example:

```text
'1676856430099137
```

This prevents Excel from displaying the ID in scientific notation or rounding it to a different value. The apostrophe is not added to the internal normalized value and would not be used for a future database write.

### Existing Export Files

The `exports/` directory currently contains outputs from several implementation stages:

| File | Rows | Rows with price | Notes |
|---|---:|---:|---|
| `facebook_marketplace_20260707_232548.csv` | 249 | 2 | Historical export using the earlier analysis/debug column set. |
| `facebook_marketplace_20260707_234811.csv` | 242 | 242 | Uses the requested `cars` columns; predates final Excel ID protection. |
| `facebook_marketplace_20260708_000231.csv` | 240 | 240 | Uses quoted requested columns; predates the apostrophe text marker. |
| `facebook_marketplace_20260708_001000.csv` | 243 | 243 | Reflects the current Excel-safe listing ID behavior. |

Existing historical files are not rewritten automatically. New runs use the current exporter behavior.

## Project Structure

| Path | Purpose |
|---|---|
| `app/main.py` | V1 orchestration and `python -m app.main` entry point. |
| `app/utils/config.py` | Runtime configuration loading and validation. |
| `app/utils/search_urls.py` | Marketplace URL and search-target generation. |
| `app/utils/normalize.py` | URL, ID, text, year, price, odometer, location, and image normalization. |
| `app/storage/postgres.py` | Read-only PostgreSQL/Supabase reference-data access. |
| `app/scrapers/base.py` | Scraper contract and raw-listing deduplication. |
| `app/scrapers/fb_marketplace.py` | Playwright Facebook Marketplace scraper. |
| `app/parsers/car_parser.py` | BMW filtering, model mapping, normalization, and parsed-listing deduplication. |
| `app/storage/csv_exporter.py` | Exact `cars`-shaped CSV export and Excel-safe listing IDs. |
| `tests/` | Unit tests for configuration, URLs, normalization, parsing, filtering, mapping, and export. |
| `implementation-note.md` | Running implementation decisions, tradeoffs, and verification notes. |

## Dependencies

The V1 runtime dependencies are:

- `playwright>=1.45,<2`
- `psycopg2>=2.9,<3`
- `python-dotenv>=1.0,<2`

Setup commands:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Tests and Verification

The test suite covers the requested V1 behavior:

- configuration loading and safe database error messages;
- Facebook search URL generation;
- make/model search-target generation;
- price parsing and card-text fallback;
- odometer parsing;
- year extraction;
- URL and listing ID normalization;
- BMW model-family mapping;
- BMW-only search target and listing filtering;
- manufacture-year eligibility and missing-year review handling;
- F/G chassis detection and E-generation rejection;
- BMW Series priority for search targets and normalized output;
- parts/accessory and non-BMW filtering;
- parsed-listing deduplication;
- exact CSV columns and Excel-safe long listing IDs.

Latest verification performed on 25 July 2026:

```text
Ran 28 tests
OK
```

Test command:

```bash
python -m unittest discover -s tests
```

The Python modules were also previously compiled successfully, and `app.main` was imported successfully.

## Explicitly Excluded from V1

The following were intentionally not implemented:

- database writes for cars;
- price history;
- database schema creation or migrations;
- changes to make/model reference data;
- Redis;
- schedulers;
- notifications;
- dashboards;
- Gumtree;
- dealer sites;
- Apify-specific code;
- cloud deployment.

## Remaining Operational Work

The code-level V1 work is complete, but a production-like live run still needs:

- a reachable PostgreSQL/Supabase connection string;
- confirmation that deployed reference table names match the adapter's `makes` and `models` queries;
- installed Playwright Chromium binaries;
- live Facebook Marketplace access from the machine running the scraper.

Because Facebook Marketplace markup can change, the scraper's card extraction should be rechecked whenever live results become empty or fields begin missing. This is the main external maintenance risk in the current V1.
