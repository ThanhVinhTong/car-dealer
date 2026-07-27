import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app.main as app_main
from app.storage.postgres import CarUpsertResult

class MainEntrypointTests(unittest.TestCase):
    def test_direct_script_resolves_app_package_imports(self):
        project_root = Path(__file__).resolve().parents[1]
        main_script = project_root / "app" / "main.py"
        import_only_code = (
            "import runpy; "
            f"runpy.run_path({str(main_script)!r}, run_name='entrypoint_import_test')"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c", import_only_code],
                cwd=temporary_directory,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pipeline_persists_parsed_cars_before_csv_export(self):
        config = SimpleNamespace(
            database_url="postgresql://unused",
            cars_table="cars",
            price_history_table="car_price_history",
            price_history_price_column="price_aud",
            price_history_recorded_at_column="recorded_at",
            scraper_source="facebook_marketplace",
            marketplace_location="perth",
            min_price=5000,
            export_dir="exports",
            log_level="INFO",
        )
        car = {
            "car_id": None,
            "source": "facebook_marketplace",
            "listing_id": "123",
        }
        storage = Mock()
        storage.load_reference_data.return_value = ([], [])
        storage.upsert_cars.return_value = [
            CarUpsertResult(
                car_id="car-1",
                source="facebook_marketplace",
                listing_id="123",
                action="inserted",
                current_price_aud=15000,
                price_changed=False,
                price_history_written=True,
            )
        ]
        scraper = Mock()
        scraper.scrape_all.return_value = [{"listing_id": "123"}]
        parser = Mock()
        parser.parse_many.return_value = [car]

        with (
            patch.object(app_main, "load_config", return_value=config),
            patch.object(app_main, "configure_logging"),
            patch.object(app_main, "PostgresStorage", return_value=storage),
            patch.object(app_main, "build_search_targets", return_value=[]),
            patch.object(
                app_main,
                "FacebookMarketplaceScraper",
                return_value=scraper,
            ),
            patch.object(app_main, "CarParser", return_value=parser),
            patch.object(
                app_main,
                "export_cars_to_csv",
                return_value=Path("exports/result.csv"),
            ) as export,
        ):
            exit_code = app_main.main()

        self.assertEqual(exit_code, 0)
        storage.upsert_cars.assert_called_once_with([car])
        self.assertEqual(car["car_id"], "car-1")
        export.assert_called_once()
        self.assertEqual(export.call_args.kwargs["cars"][0]["car_id"], "car-1")


if __name__ == "__main__":
    unittest.main()
