from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
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


def export_cars_to_csv(
    cars: list[dict],
    export_dir: str | Path,
    source: str,
    *,
    timestamp: datetime | None = None,
) -> Path:
    output_dir = Path(export_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    export_time = timestamp or datetime.now()
    output_path = output_dir / f"{source}_{export_time:%Y%m%d_%H%M%S}.csv"

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_COLUMNS,
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for car in cars:
            writer.writerow(
                {
                    column: _serialize_value(column, car.get(column))
                    for column in CSV_COLUMNS
                }
            )

    return output_path


def _serialize_value(column: str, value: Any) -> Any:
    if value is None:
        return ""
    if column == "listing_id":
        return _excel_text(str(value))
    return value


def _excel_text(value: str) -> str:
    return f"'{value}"
