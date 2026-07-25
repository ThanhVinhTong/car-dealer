from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.parsers.car_parser import CarParser
from app.scrapers.fb_marketplace import FacebookMarketplaceScraper
from app.storage.csv_exporter import export_cars_to_csv
from app.storage.postgres import PostgresStorage
from app.utils.config import load_config
from app.utils.logger import configure_logging, get_logger
from app.utils.search_urls import build_search_targets


def main() -> int:
    config = load_config()
    configure_logging(config.log_level)
    logger = get_logger("app.main")

    if config.scraper_source != "facebook_marketplace":
        raise ValueError("V1 only supports SCRAPER_SOURCE=facebook_marketplace")

    logger.info("Scraper start")
    storage = PostgresStorage(config.database_url)
    makes, models = storage.load_reference_data()
    logger.info("Loaded %s makes from database", len(makes))
    logger.info("Loaded %s models from database", len(models))

    search_targets = build_search_targets(
        makes=makes,
        models=models,
        marketplace_location=config.marketplace_location,
        min_price=config.min_price,
    )
    logger.info(
        "Generated %s Facebook Marketplace search URLs", len(search_targets)
    )

    scraper = FacebookMarketplaceScraper(config=config)
    raw_listings = scraper.scrape_all(search_targets)
    logger.info("Collected %s raw listings", len(raw_listings))

    parser = CarParser(makes=makes, models=models)
    normalized_cars = parser.parse_many(raw_listings)
    logger.info("Parsed %s listings", len(normalized_cars))

    export_path = export_cars_to_csv(
        cars=normalized_cars,
        export_dir=config.export_dir,
        source=config.scraper_source,
    )
    logger.info("Exported CSV to %s", export_path)
    logger.info("Scraper complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
