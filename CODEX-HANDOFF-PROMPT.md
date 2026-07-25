# Codex Handoff Prompt

Paste the prompt below into a new Codex task after opening the copied or
cloned project folder. Replace the final placeholder with your next request.

```text
You are continuing work on the BMW Marketplace Scraper in the current folder.

Before changing code:

1. Read README.md, PROJECT-STATUS.md, and implementation-note.md carefully.
2. Inspect the current app/ and tests/ implementation.
3. Do not read any .env file or any folder named confidential.
4. Do not use queries.txt.
5. Preserve existing user changes and keep implementation-note.md updated
   with decisions, assumptions, tradeoffs, and verification results.

Current V1 pipeline:

1. Load runtime configuration.
2. Connect read-only to the existing PostgreSQL/Supabase database.
3. Read existing makes and models reference data.
4. Generate BMW Facebook Marketplace targets from database records,
   MARKETPLACE_LOCATION, and MIN_PRICE.
5. Scrape generated targets with Playwright.
6. Collect and deduplicate raw listings.
7. Parse and normalize listings.
8. Filter non-BMW, parts/accessories, known pre-2012, and detected
   E-generation listings.
9. Map BMW titles to existing model-family records.
10. Sort by BMW Series priority and export the exact cars-shaped CSV.

Required BMW behavior:

- Keep BMW only. MINI, Mercedes, and other makes are dropped.
- Keep known manufacturing years from 2012 onward.
- Drop known manufacturing years before 2012.
- Missing year stays unknown and is marked internally for review; never guess.
- Detect explicit E/F/G chassis codes from title and description.
- Drop E-generation listings.
- Keep F/G listings with the normalized chassis code.
- Missing generation stays unknown; never infer it from year or model.
- Series priority is 3/4 = 1, 2 = 2, 5/6 = 3, 7 = 4, 1 = 5.
- Unranked X/Z/unknown families follow at priority 6.

Existing constraints:

- Treat the database schema as already implemented.
- Do not create tables or run migrations.
- Do not modify make or model reference rows.
- Do not insert or upsert cars in V1.
- Do not implement price history.
- Do not implement Redis, scheduler, notifications, dashboard, Gumtree,
  dealer sites, Apify-specific code, or cloud deployment.
- Keep listing_id as text end to end.
- Extract listing_id from the canonical Marketplace item URL first.
- Prefix listing_id with Excel's apostrophe text marker in CSV only.
- Keep the CSV columns exactly as defined by app/storage/csv_exporter.py.
- Do not add internal chassis/filter/review/priority fields to the CSV.

Supported run commands:

python -m app.main
python app/main.py

Run tests without reading real runtime configuration:

python -m unittest discover -s tests

The latest verified baseline is 28 passing tests. Add or update focused tests
for any behavior you change, run the complete suite, and report anything that
could not be verified.

My next task:
[PASTE THE NEXT REQUEST HERE]
```
