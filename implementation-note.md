# Implementation Notes

## Decisions

- Implemented the requested V1 pipeline in a new root-level `app/` package so it runs with `python -m app.main`.
- Kept the old `marketplace_scraper/` folder untouched except for not using it; the new V1 path does not read `queries.txt`.
- Config loading supports `.env` at runtime, but tests load from environment variables so no real `.env` file is read during implementation.
- PostgreSQL access is read-only and only selects from existing `make` and `model` tables.
- Switched the database adapter to `psycopg2` after installing `python-dotenv` and `psycopg2` for direct Supabase/PostgreSQL connections.
- Added safer Supabase connection error messaging for DNS/host resolution failures, including guidance to verify `DATABASE_URL`, URL-encode special characters in the password, use `sslmode=require`, and consider the Supabase Session pooler on IPv4-only networks.
- Search targets are generated from `make` and `model` rows, skip the `unknown` model, and include search metadata for every raw listing.
- The Facebook scraper uses generated URLs and Playwright only when scraping is executed. It does not bypass login, CAPTCHA, or platform protections.
- The parser keeps both IDs and names internally, but CSV export writes the `cars` table columns only.
- Updated CSV export to match the existing `cars` table columns exactly, using `make_id` and `model_id` instead of analysis/debug fields.
- Made the parser extract `listing_id` from the normalized Marketplace item URL first because source-provided IDs can disagree with the canonical URL.
- Kept `listing_id` as text end to end and made CSV export quote fields while explicitly serializing `listing_id` as `str`, so large Marketplace IDs are not intentionally converted to integers by the pipeline.
- Added Excel-specific CSV protection for `listing_id` by prefixing the exported cell with Excel's text marker, while keeping the parser/internal value as the plain listing ID string for future database writes.
- Added a conservative price fallback that scans title, description, and raw card text for currency-marked prices when `price_text` is missing.
- Set `first_seen_at`, `last_seen_at`, `created_at`, and `updated_at` to the scrape timestamp for exported rows so the CSV better matches the non-null timestamp columns in `cars`.
- Added `PROJECT-STATUS.md` on 14 July 2026 to consolidate the completed V1 scope, implementation behavior, generated export history, test evidence, exclusions, and remaining live-run requirements.
- On 25 July 2026, restricted generated search targets to the exact BMW make so non-BMW reference rows are no longer scraped.
- Added a minimum manufacture-year rule: known years before 2012 are dropped, while a missing year is retained as `unknown` with an internal review flag instead of being inferred.
- Added explicit E/F/G chassis-code detection from title and description. E-generation listings are dropped, F/G codes are normalized, and missing generation stays `unknown`.
- Added BMW Series priority to both generated search-target order and normalized output order: 3/4 = 1, 2 = 2, 5/6 = 3, 7 = 4, and 1 = 5.
- Assigned corresponding M models to their numbered family priority (M3/M4 = 1, M2 = 2, M5/M6 = 3) and placed X, Z, M8, and unknown/unranked models at priority 6.
- Kept year/generation filter status, review state, chassis code, and priority as internal parser fields because the CSV must retain the previously requested exact `cars` table columns.
- Added a project-root import bootstrap to `app/main.py` so both `python -m app.main` and `python app/main.py` resolve package imports correctly.
- Reworked the root `README.md` for GitHub with setup, configuration names, V1 pipeline behavior, BMW rules, CSV contract, tests, structure, and non-goals.
- Added a root `.gitignore` that excludes secrets, confidential folders, Python caches, Playwright/test artifacts, logs, generated CSV exports, and the unused `queries.txt`.
- Added `CODEX-HANDOFF-PROMPT.md` as a reusable prompt for continuing the project from a new folder or Codex task without exposing local secrets.
- Excluded all `.env*` files from Git because the no-`.env` instruction prevents verifying that `.env.example` contains placeholders only.
- Excluded the unrelated `datadome_clone/` prototype from this scraper repository so the GitHub project contains only the documented V1 implementation.

## Tradeoffs

- Facebook Marketplace HTML changes often, so the scraper extracts listing cards from Marketplace item links and keeps raw card text for debugging.
- The parser is conservative: obvious BMW parts/accessory listings are skipped, and unclear BMW model matches fall back to the existing `unknown` model.
- Search-target model fallback is intentionally weak and only used after title and description matching fail.
- The parser still keeps analysis fields internally, but the CSV exporter now drops anything outside the `cars` table shape.
- Chassis detection intentionally recognizes only explicit E/F/G codes in listing text; V1 does not infer chassis from VINs, year, or model badge.
- Listings with missing year or generation are retained rather than guessed. A missing year is marked for review, while an unranked Series family is processed after the five specified groups.

## Verification

- Ran `python -m unittest discover -s tests` with the bundled Python runtime. Result: 16 tests passed before connection diagnostics; rerun after diagnostics added 17 tests passed. Rerun after CSV/listing ID/price fixes added 20 tests passed.
- Ran `python -m compileall app tests`. Result: all new app and test modules compiled successfully.
- Imported `app.main` successfully to verify the `python -m app.main` entry point module is importable.
- Did not run a full live scrape because that requires real `.env` database credentials, a reachable PostgreSQL/Supabase database, Playwright browser binaries, and live Facebook Marketplace access.
- Re-ran the complete suite while preparing the status report on 14 July 2026. Result: 20 tests passed.
- Audited existing CSV artifacts for the report: the newest export contains 243 rows, all 243 have parsed prices, and its first long Marketplace ID is preserved with Excel's text marker.
- Re-ran the complete suite after BMW-only, year, chassis-generation, and Series-priority implementation on 25 July 2026. Result: 27 tests passed.
- Added an isolated direct-entrypoint import regression test and re-ran the complete suite. Result: 28 tests passed.
- Confirmed the folder was not yet a Git repository while preparing the GitHub handoff files; no remote repository was available to push.
- Initialized a local Git repository on the `main` branch; a GitHub remote still needs to be supplied before pushing.
- Created the initial local Git commit containing the documented V1 scraper source, tests, and GitHub handoff files.
