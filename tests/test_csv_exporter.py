import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.storage.csv_exporter import CSV_COLUMNS, export_cars_to_csv


EXPECTED_CARS_TABLE_COLUMNS = [
    "car_id",
    "source",
    "listing_id",
    "normalized_url",
    "title",
    "make_id",
    "model_id",
    "manufacture_year",
    "current_price_aud",
    "sell_location",
    "status",
    "first_seen_at",
    "last_seen_at",
    "created_at",
    "updated_at",
]


class CsvExporterTests(unittest.TestCase):
    def test_export_cars_to_csv_writes_expected_columns_and_serializes_complex_values(self):
        listing_id = "1000639938499289123"
        car = {
            "car_id": None,
            "source": "facebook_marketplace",
            "listing_id": listing_id,
            "normalized_url": f"https://www.facebook.com/marketplace/item/{listing_id}",
            "title": "2015 BMW 320i",
            "make_id": 1,
            "model_id": 3,
            "manufacture_year": 2015,
            "current_price_aud": 12500,
            "sell_location": "Perth, WA",
            "status": "active",
            "first_seen_at": "2026-07-07T21:00:00+08:00",
            "last_seen_at": "2026-07-07T21:00:00+08:00",
            "created_at": "2026-07-07T21:00:00+08:00",
            "updated_at": "2026-07-07T21:00:00+08:00",
            "odometer_km": 145000,
            "description": "Clean car",
            "image_urls": ["https://img/1.jpg"],
            "seller_name": "Seller",
            "seller_type": None,
            "search_make_name": "BMW",
            "search_model_name": "3 Series",
            "search_url": "https://www.facebook.com/marketplace/perth/search",
            "scraped_at": "2026-07-07T21:00:00+08:00",
            "raw_payload": {"title": "2015 BMW 320i"},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = export_cars_to_csv(
                cars=[car],
                export_dir=Path(temp_dir),
                source="facebook_marketplace",
                timestamp=datetime(2026, 7, 7, 21, 0, 0),
            )

            self.assertEqual(path.name, "facebook_marketplace_20260707_210000.csv")

            with path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)

            raw_csv = path.read_text(encoding="utf-8")

        self.assertEqual(CSV_COLUMNS, EXPECTED_CARS_TABLE_COLUMNS)
        self.assertEqual(reader.fieldnames, EXPECTED_CARS_TABLE_COLUMNS)
        self.assertEqual(rows[0]["listing_id"], f"'{listing_id}")
        self.assertIn(f'"\'{listing_id}"', raw_csv)
        self.assertEqual(rows[0]["make_id"], "1")
        self.assertEqual(rows[0]["model_id"], "3")
        self.assertNotIn("make_name", rows[0])
        self.assertNotIn("model_name", rows[0])
        self.assertNotIn("raw_payload", rows[0])


if __name__ == "__main__":
    unittest.main()
