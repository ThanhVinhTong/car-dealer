# Implementation Notes

## M2 Data Insertion — 25 July 2026

### Decisions

- Implemented database listing identity as the exact pair
  `(source, listing_id)`. Similar title/model/price values are never used to
  merge different listing IDs.
- Kept `listing_id` as plain text internally and reject the leading apostrophe
  used only by the Excel-safe CSV representation.
- Implemented `PostgresStorage.upsert_car()` as the stable persistence boundary
  for the future Apify dataset processor. It returns the car ID, insert/update
  action, resulting price, and whether price history was written.
- Implemented `PostgresStorage.upsert_cars()` to reduce repeated occurrences of
  one source/listing ID to the newest observation before database writes, while
  filling its missing optional values from the older observation.
- Used PostgreSQL `INSERT ... ON CONFLICT (source, listing_id) DO NOTHING` as
  the insert claim, followed by `SELECT ... FOR UPDATE` for an existing row.
  This serializes concurrent updates once the required unique constraint is
  present and prevents duplicate cars and price-history rows.
- Kept car upsert and its corresponding price-history write in one database
  transaction.
- A valid initial price receives a history row. Later history is written only
  when a valid incoming price differs from the stored price.
- Missing, non-numeric, zero, negative, Boolean, or fractional prices are
  treated as invalid at the storage boundary. They neither overwrite a known
  price nor create history.
- Preserved stored values when an incoming optional value is missing or blank,
  and ignored observations older than the stored `last_seen_at` so delayed
  webhook processing cannot roll a car or price backward.
- Wired `app.main` to persist parsed cars before CSV export and to copy returned
  database `car_id` values into exported rows.
- Did not create or modify database tables or reference rows.

### Schema assumptions

- The existing `cars` table has the columns documented by
  `app/storage/csv_exporter.py`.
- `cars` has a database-enforced unique constraint on `(source, listing_id)`.
- Price history defaults to
  `car_price_history(car_id, price_aud, recorded_at)`.
- Table and price-history column identifiers can be changed through
  `CARS_TABLE`, `PRICE_HISTORY_TABLE`, `PRICE_HISTORY_PRICE_COLUMN`, and
  `PRICE_HISTORY_RECORDED_AT_COLUMN`. Identifiers are validated before use.
- The known `cars` shape has no `description` column. The upsert therefore
  updates normalized URL, title, make/model IDs, manufacture year, valid price,
  sell location, status, and observation timestamps. Description persistence
  requires confirmation of a deployed column name or a separate listing-detail
  table; inventing one would violate the no-migration/schema-as-implemented
  constraint.

### Tradeoffs

- Each car uses its own transaction. This gives Huy's future Apify processor a
  precise per-item outcome and prevents one malformed item from requiring a
  large batch transaction design, at the cost of more database round trips.
- Existing rows are still touched to advance `last_seen_at` even when their
  business fields and price are unchanged. The returned action remains
  `unchanged`, which is more useful for processing counters.
- The implementation relies on the database unique constraint as the final
  concurrency guarantee rather than an in-memory deduplication set.

### Verification

- Added focused storage tests for initial insertion, changed and unchanged
  prices, invalid-price preservation, mutable-field updates, stale observations,
  batch deduplication, different listing identities, plain-text IDs, and safe
  SQL identifiers.
- Focused verification initially ran 9 tests successfully with the bundled
  Python runtime.
- Added a pipeline orchestration test proving persistence runs before CSV export
  and returned database IDs are included in exported rows.
- Final verification ran the complete suite: 40 tests passed. `compileall`
  completed successfully for `app` and `tests`, and `git diff --check` reported
  no whitespace errors.
- A live PostgreSQL/Supabase write was not attempted because no runtime
  credentials or confirmed deployed price-history schema were provided, and
  `.env` files must not be read.
