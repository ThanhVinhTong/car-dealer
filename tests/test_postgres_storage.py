import unittest
from unittest.mock import Mock, patch

from app.storage.postgres import CarUpsertResult, PostgresStorage


OBSERVED_AT = "2026-07-25T12:00:00+08:00"


def make_car(**overrides):
    car = {
        "source": "facebook_marketplace",
        "listing_id": "123",
        "normalized_url": "https://www.facebook.com/marketplace/item/123",
        "title": "2015 BMW F30 320i",
        "make_id": 1,
        "model_id": 3,
        "manufacture_year": 2015,
        "current_price_aud": 15000,
        "sell_location": "Perth, WA",
        "status": "active",
        "first_seen_at": OBSERVED_AT,
        "last_seen_at": OBSERVED_AT,
        "created_at": OBSERVED_AT,
        "updated_at": OBSERVED_AT,
    }
    car.update(overrides)
    return car


def existing_car(**overrides):
    row = make_car(car_id="car-1")
    row.update(overrides)
    return row


class FakeCursor:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, parameters=None):
        self.executions.append((" ".join(query.split()), parameters))

    def fetchone(self):
        return self.fetchone_results.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self.test_cursor = cursor
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self, **kwargs):
        return self.test_cursor

    def close(self):
        self.closed = True


class PostgresStorageInsertionTests(unittest.TestCase):
    def make_storage(self, fetchone_results):
        cursor = FakeCursor(fetchone_results)
        connection = FakeConnection(cursor)
        storage = PostgresStorage("postgresql://unused")
        storage._connect = Mock(return_value=connection)
        storage._real_dict_cursor = Mock(return_value=None)
        return storage, connection, cursor

    def test_first_observation_inserts_car_and_initial_price_history(self):
        storage, connection, cursor = self.make_storage(
            [{"car_id": "car-1", "current_price_aud": 15000}]
        )

        result = storage.upsert_car(make_car())

        self.assertEqual(result.action, "inserted")
        self.assertEqual(result.car_id, "car-1")
        self.assertEqual(result.current_price_aud, 15000)
        self.assertFalse(result.price_changed)
        self.assertTrue(result.price_history_written)
        self.assertEqual(len(cursor.executions), 2)
        self.assertIn("INSERT INTO cars", cursor.executions[0][0])
        self.assertIn("ON CONFLICT (source, listing_id) DO NOTHING", cursor.executions[0][0])
        self.assertIn("INSERT INTO car_price_history", cursor.executions[1][0])
        self.assertEqual(cursor.executions[1][1], ("car-1", 15000, OBSERVED_AT))
        self.assertTrue(connection.closed)

    def test_changed_price_updates_car_and_writes_one_history_row(self):
        storage, _, cursor = self.make_storage(
            [None, existing_car(current_price_aud=15000)]
        )

        result = storage.upsert_car(
            make_car(
                current_price_aud=13500,
                last_seen_at="2026-07-25T13:00:00+08:00",
            )
        )

        self.assertEqual(result.action, "updated")
        self.assertTrue(result.price_changed)
        self.assertTrue(result.price_history_written)
        self.assertEqual(result.current_price_aud, 13500)
        self.assertEqual(len(cursor.executions), 4)
        self.assertIn("SELECT car_id", cursor.executions[1][0])
        self.assertIn("FOR UPDATE", cursor.executions[1][0])
        self.assertIn("UPDATE cars", cursor.executions[2][0])
        self.assertEqual(cursor.executions[2][1][5], 13500)
        self.assertEqual(
            cursor.executions[3][1],
            ("car-1", 13500, "2026-07-25T13:00:00+08:00"),
        )

    def test_new_car_with_invalid_price_has_no_price_history(self):
        storage, _, cursor = self.make_storage(
            [{"car_id": "car-1", "current_price_aud": None}]
        )

        result = storage.upsert_car(make_car(current_price_aud="contact seller"))

        self.assertEqual(result.action, "inserted")
        self.assertIsNone(result.current_price_aud)
        self.assertFalse(result.price_history_written)
        self.assertEqual(len(cursor.executions), 1)

    def test_same_price_does_not_write_duplicate_history(self):
        storage, _, cursor = self.make_storage(
            [None, existing_car(current_price_aud=15000)]
        )

        result = storage.upsert_car(
            make_car(last_seen_at="2026-07-25T13:00:00+08:00")
        )

        self.assertEqual(result.action, "unchanged")
        self.assertFalse(result.price_changed)
        self.assertFalse(result.price_history_written)
        self.assertEqual(len(cursor.executions), 3)
        self.assertFalse(
            any("INSERT INTO car_price_history" in query for query, _ in cursor.executions)
        )

    def test_first_valid_price_after_missing_price_writes_initial_history(self):
        storage, _, cursor = self.make_storage(
            [None, existing_car(current_price_aud=None)]
        )

        result = storage.upsert_car(
            make_car(
                current_price_aud=15000,
                last_seen_at="2026-07-25T13:00:00+08:00",
            )
        )

        self.assertEqual(result.action, "updated")
        self.assertTrue(result.price_changed)
        self.assertTrue(result.price_history_written)
        self.assertEqual(
            cursor.executions[3][1],
            ("car-1", 15000, "2026-07-25T13:00:00+08:00"),
        )

    def test_missing_or_invalid_price_preserves_existing_price(self):
        for value in (None, "", "contact seller", 0, -1, 12.5, True):
            with self.subTest(value=value):
                storage, _, cursor = self.make_storage(
                    [None, existing_car(current_price_aud=15000)]
                )

                result = storage.upsert_car(
                    make_car(
                        current_price_aud=value,
                        last_seen_at="2026-07-25T13:00:00+08:00",
                    )
                )

                self.assertEqual(result.current_price_aud, 15000)
                self.assertFalse(result.price_changed)
                self.assertFalse(result.price_history_written)
                self.assertEqual(cursor.executions[2][1][5], 15000)
                self.assertEqual(len(cursor.executions), 3)

    def test_changed_location_updates_existing_car_without_price_history(self):
        storage, _, cursor = self.make_storage(
            [None, existing_car(sell_location="Perth, WA")]
        )

        result = storage.upsert_car(
            make_car(
                sell_location="Fremantle, WA",
                last_seen_at="2026-07-25T13:00:00+08:00",
            )
        )

        self.assertEqual(result.action, "updated")
        self.assertFalse(result.price_changed)
        self.assertEqual(cursor.executions[2][1][6], "Fremantle, WA")
        self.assertEqual(len(cursor.executions), 3)

    def test_older_observation_cannot_roll_back_current_car_or_price(self):
        storage, _, cursor = self.make_storage(
            [
                None,
                existing_car(
                    current_price_aud=13500,
                    last_seen_at="2026-07-25T14:00:00+08:00",
                ),
            ]
        )

        result = storage.upsert_car(
            make_car(
                current_price_aud=15000,
                sell_location="Old location",
                last_seen_at="2026-07-25T13:00:00+08:00",
            )
        )

        self.assertEqual(result.action, "unchanged")
        self.assertEqual(result.current_price_aud, 13500)
        self.assertFalse(result.price_history_written)
        self.assertEqual(len(cursor.executions), 2)

    def test_batch_deduplicates_by_source_and_listing_id_but_not_car_details(self):
        storage = PostgresStorage("postgresql://unused")

        def result_for(car):
            return CarUpsertResult(
                car_id=f"car-{car['listing_id']}",
                source=car["source"],
                listing_id=car["listing_id"],
                action="inserted",
                current_price_aud=car["current_price_aud"],
                price_changed=False,
                price_history_written=True,
            )

        first = make_car(title="First result", current_price_aud=15000)
        duplicate = make_car(
            title="Later result",
            current_price_aud=14000,
            sell_location=None,
            last_seen_at="2026-07-25T13:00:00+08:00",
        )
        different_listing = make_car(
            listing_id="456",
            normalized_url="https://www.facebook.com/marketplace/item/456",
            title=duplicate["title"],
            current_price_aud=duplicate["current_price_aud"],
        )

        with patch.object(storage, "upsert_car", side_effect=result_for) as upsert:
            results = storage.upsert_cars([first, duplicate, different_listing])

        self.assertEqual(len(results), 2)
        self.assertEqual(upsert.call_count, 2)
        self.assertEqual(upsert.call_args_list[0].args[0]["title"], "Later result")
        self.assertEqual(upsert.call_args_list[0].args[0]["sell_location"], "Perth, WA")
        self.assertEqual(
            [result.listing_id for result in results],
            ["123", "456"],
        )

    def test_database_identity_requires_plain_source_and_listing_id(self):
        storage = PostgresStorage("postgresql://unused")

        for car in (
            make_car(source=""),
            make_car(listing_id=None),
            make_car(listing_id="'123"),
        ):
            with self.subTest(car=car):
                with self.assertRaises(ValueError):
                    storage.upsert_car(car)

    def test_table_and_column_identifiers_are_validated(self):
        with self.assertRaises(ValueError):
            PostgresStorage(
                "postgresql://unused",
                price_history_table="car_price_history; DROP TABLE cars",
            )


if __name__ == "__main__":
    unittest.main()
