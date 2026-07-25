from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse


POSTGRES_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CAR_MUTABLE_COLUMNS = (
    "normalized_url",
    "title",
    "make_id",
    "model_id",
    "manufacture_year",
    "current_price_aud",
    "sell_location",
    "status",
)


@dataclass(frozen=True)
class CarUpsertResult:
    car_id: Any
    source: str
    listing_id: str
    action: str
    current_price_aud: int | None
    price_changed: bool
    price_history_written: bool


class PostgresStorage:
    """PostgreSQL/Supabase reference reads and transactional car persistence."""

    def __init__(
        self,
        database_url: str,
        *,
        cars_table: str = "cars",
        price_history_table: str = "car_price_history",
        price_history_price_column: str = "price_aud",
        price_history_recorded_at_column: str = "recorded_at",
    ) -> None:
        self.database_url = database_url
        self.cars_table = _validate_identifier(cars_table)
        self.price_history_table = _validate_identifier(price_history_table)
        self.price_history_price_column = _validate_identifier(
            price_history_price_column
        )
        self.price_history_recorded_at_column = _validate_identifier(
            price_history_recorded_at_column
        )

    def load_makes(self) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT make_id, make_name, created_at
            FROM makes
            ORDER BY make_name
            """
        )

    def load_models(self) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT model_id, make_id, model_name, created_at
            FROM models
            ORDER BY make_id, model_id
            """
        )

    def load_reference_data(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return self.load_makes(), self.load_models()

    def upsert_cars(self, cars: list[dict[str, Any]]) -> list[CarUpsertResult]:
        """Persist one latest observation per source/listing ID in this batch."""
        deduplicated: dict[tuple[str, str], dict[str, Any]] = {}
        for car in cars:
            normalized_car, key = self._normalize_identity(car)
            current = deduplicated.get(key)
            if current is None:
                deduplicated[key] = normalized_car
            elif _is_same_or_newer_observation(normalized_car, current):
                deduplicated[key] = _merge_observations(
                    older=current,
                    newer=normalized_car,
                )
            else:
                deduplicated[key] = _merge_observations(
                    older=normalized_car,
                    newer=current,
                )

        return [self.upsert_car(car) for car in deduplicated.values()]

    def upsert_car(self, car: dict[str, Any]) -> CarUpsertResult:
        """
        Insert or update one car and append price history in one transaction.

        The database must enforce UNIQUE (source, listing_id). The initial
        valid price and each later valid price change receive one history row.
        Missing or invalid incoming prices preserve the stored price.
        """
        normalized_car, _ = self._normalize_identity(car)
        observed_at = _observation_time(normalized_car)
        initial_values = self._insert_values(normalized_car, observed_at)

        connection = self._connect()
        try:
            with connection:
                with self._cursor(connection) as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {self.cars_table} (
                            source,
                            listing_id,
                            normalized_url,
                            title,
                            make_id,
                            model_id,
                            manufacture_year,
                            current_price_aud,
                            sell_location,
                            status,
                            first_seen_at,
                            last_seen_at,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (source, listing_id) DO NOTHING
                        RETURNING car_id, current_price_aud
                        """,
                        initial_values,
                    )
                    inserted = cursor.fetchone()
                    if inserted:
                        car_id = inserted["car_id"]
                        price = _valid_price(inserted.get("current_price_aud"))
                        history_written = False
                        if price is not None:
                            self._insert_price_history(
                                cursor,
                                car_id=car_id,
                                price_aud=price,
                                recorded_at=observed_at,
                            )
                            history_written = True

                        return CarUpsertResult(
                            car_id=car_id,
                            source=normalized_car["source"],
                            listing_id=normalized_car["listing_id"],
                            action="inserted",
                            current_price_aud=price,
                            price_changed=False,
                            price_history_written=history_written,
                        )

                    existing = self._select_car_for_update(
                        cursor,
                        source=normalized_car["source"],
                        listing_id=normalized_car["listing_id"],
                    )
                    if existing is None:
                        raise RuntimeError(
                            "Car upsert conflict occurred but the existing car "
                            "could not be loaded"
                        )

                    return self._update_existing_car(
                        cursor,
                        existing=existing,
                        incoming=normalized_car,
                        observed_at=observed_at,
                    )
        finally:
            connection.close()

    def _normalize_identity(
        self,
        car: dict[str, Any],
    ) -> tuple[dict[str, Any], tuple[str, str]]:
        source = str(car.get("source") or "").strip()
        listing_id = str(car.get("listing_id") or "").strip()
        if not source:
            raise ValueError("Car source is required for database deduplication")
        if not listing_id:
            raise ValueError("Car listing_id is required for database deduplication")
        if listing_id.startswith("'"):
            raise ValueError(
                "Car listing_id must use the internal text value without Excel's "
                "CSV apostrophe marker"
            )

        normalized = dict(car)
        normalized["source"] = source
        normalized["listing_id"] = listing_id
        normalized["current_price_aud"] = _valid_price(
            normalized.get("current_price_aud")
        )
        return normalized, (source, listing_id)

    def _insert_values(
        self,
        car: dict[str, Any],
        observed_at: Any,
    ) -> tuple[Any, ...]:
        first_seen_at = car.get("first_seen_at") or observed_at
        last_seen_at = car.get("last_seen_at") or observed_at
        created_at = car.get("created_at") or first_seen_at
        updated_at = car.get("updated_at") or last_seen_at
        return (
            car["source"],
            car["listing_id"],
            car.get("normalized_url"),
            car.get("title"),
            car.get("make_id"),
            car.get("model_id"),
            car.get("manufacture_year"),
            car.get("current_price_aud"),
            car.get("sell_location"),
            car.get("status") or "active",
            first_seen_at,
            last_seen_at,
            created_at,
            updated_at,
        )

    def _select_car_for_update(
        self,
        cursor: Any,
        *,
        source: str,
        listing_id: str,
    ) -> dict[str, Any] | None:
        cursor.execute(
            f"""
            SELECT
                car_id,
                source,
                listing_id,
                normalized_url,
                title,
                make_id,
                model_id,
                manufacture_year,
                current_price_aud,
                sell_location,
                status,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            FROM {self.cars_table}
            WHERE source = %s AND listing_id = %s
            FOR UPDATE
            """,
            (source, listing_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _update_existing_car(
        self,
        cursor: Any,
        *,
        existing: dict[str, Any],
        incoming: dict[str, Any],
        observed_at: Any,
    ) -> CarUpsertResult:
        existing_price = _valid_price(existing.get("current_price_aud"))
        incoming_price = incoming.get("current_price_aud")

        if _is_older_observation(observed_at, existing.get("last_seen_at")):
            return CarUpsertResult(
                car_id=existing["car_id"],
                source=existing["source"],
                listing_id=str(existing["listing_id"]),
                action="unchanged",
                current_price_aud=existing_price,
                price_changed=False,
                price_history_written=False,
            )

        merged = {
            column: _prefer_incoming(incoming.get(column), existing.get(column))
            for column in CAR_MUTABLE_COLUMNS
        }
        merged["current_price_aud"] = (
            incoming_price if incoming_price is not None else existing_price
        )
        changed = any(
            not _database_values_equal(merged[column], existing.get(column))
            for column in CAR_MUTABLE_COLUMNS
        )
        price_changed = incoming_price is not None and incoming_price != existing_price

        cursor.execute(
            f"""
            UPDATE {self.cars_table}
            SET
                normalized_url = %s,
                title = %s,
                make_id = %s,
                model_id = %s,
                manufacture_year = %s,
                current_price_aud = %s,
                sell_location = %s,
                status = %s,
                last_seen_at = GREATEST(COALESCE(last_seen_at, %s), %s),
                updated_at = GREATEST(COALESCE(updated_at, %s), %s)
            WHERE car_id = %s
            """,
            (
                merged["normalized_url"],
                merged["title"],
                merged["make_id"],
                merged["model_id"],
                merged["manufacture_year"],
                merged["current_price_aud"],
                merged["sell_location"],
                merged["status"],
                observed_at,
                observed_at,
                observed_at,
                observed_at,
                existing["car_id"],
            ),
        )

        history_written = False
        if price_changed:
            self._insert_price_history(
                cursor,
                car_id=existing["car_id"],
                price_aud=incoming_price,
                recorded_at=observed_at,
            )
            history_written = True

        return CarUpsertResult(
            car_id=existing["car_id"],
            source=incoming["source"],
            listing_id=incoming["listing_id"],
            action="updated" if changed else "unchanged",
            current_price_aud=merged["current_price_aud"],
            price_changed=price_changed,
            price_history_written=history_written,
        )

    def _insert_price_history(
        self,
        cursor: Any,
        *,
        car_id: Any,
        price_aud: int,
        recorded_at: Any,
    ) -> None:
        cursor.execute(
            f"""
            INSERT INTO {self.price_history_table} (
                car_id,
                {self.price_history_price_column},
                {self.price_history_recorded_at_column}
            )
            VALUES (%s, %s, %s)
            """,
            (car_id, price_aud, recorded_at),
        )

    def _fetch_all(self, query: str) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            with connection.cursor(cursor_factory=self._real_dict_cursor()) as cursor:
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _connect(self) -> Any:
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 is required for PostgreSQL access. Install requirements.txt."
            ) from exc

        try:
            return psycopg2.connect(self.database_url)
        except psycopg2.OperationalError as exc:
            raise RuntimeError(_format_connection_error(self.database_url, exc)) from exc

    def _cursor(self, connection: Any) -> Any:
        return connection.cursor(cursor_factory=self._real_dict_cursor())

    def _real_dict_cursor(self) -> Any:
        from psycopg2.extras import RealDictCursor

        return RealDictCursor


def _validate_identifier(value: str) -> str:
    if not POSTGRES_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid PostgreSQL identifier: {value!r}")
    return value


def _valid_price(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not numeric.is_finite() or numeric <= 0 or numeric != numeric.to_integral_value():
        return None
    return int(numeric)


def _observation_time(car: dict[str, Any]) -> Any:
    return (
        car.get("last_seen_at")
        or car.get("scraped_at")
        or car.get("updated_at")
        or datetime.now(timezone.utc)
    )


def _prefer_incoming(incoming: Any, existing: Any) -> Any:
    if incoming is None:
        return existing
    if isinstance(incoming, str) and not incoming.strip():
        return existing
    return incoming


def _database_values_equal(left: Any, right: Any) -> bool:
    if left == right:
        return True
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_older_observation(incoming: Any, existing: Any) -> bool:
    incoming_time = _coerce_datetime(incoming)
    existing_time = _coerce_datetime(existing)
    return bool(
        incoming_time is not None
        and existing_time is not None
        and incoming_time < existing_time
    )


def _is_same_or_newer_observation(
    incoming: dict[str, Any],
    existing: dict[str, Any],
) -> bool:
    incoming_time = _coerce_datetime(_observation_time(incoming))
    existing_time = _coerce_datetime(_observation_time(existing))
    if incoming_time is None or existing_time is None:
        return True
    return incoming_time >= existing_time


def _merge_observations(
    *,
    older: dict[str, Any],
    newer: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(older)
    for key, value in newer.items():
        merged[key] = _prefer_incoming(value, merged.get(key))
    return merged


def _format_connection_error(database_url: str, exc: Exception) -> str:
    host = _safe_database_host(database_url)
    base_message = f"Could not connect to PostgreSQL/Supabase"
    if host:
        base_message += f" host {host!r}"

    return (
        f"{base_message}: {exc}\n"
        "Check that DATABASE_URL is copied from Supabase Dashboard > Connect, "
        "the project is active, the database password is URL-encoded if it contains "
        "special characters, and the connection string includes sslmode=require. "
        "If you are using the direct db.[project-ref].supabase.co endpoint from an "
        "IPv4-only network, use Supabase's Session pooler connection string instead "
        "or enable the IPv4 add-on."
    )


def _safe_database_host(database_url: str) -> str | None:
    try:
        parsed = urlparse(database_url)
    except Exception:
        return None
    return parsed.hostname
