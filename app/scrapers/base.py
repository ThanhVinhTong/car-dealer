from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.utils.logger import get_logger
from app.utils.normalize import extract_listing_id, normalize_url


class BaseScraper(ABC):
    source: str

    def __init__(
        self,
        *,
        request_delay_seconds: float = 2.0,
        max_results_per_search_url: int = 50,
    ) -> None:
        self.request_delay_seconds = request_delay_seconds
        self.max_results_per_search_url = max_results_per_search_url
        self.logger = get_logger(self.__class__.__name__)
        self._seen_keys: set[tuple[str, str]] = set()

    @abstractmethod
    def scrape_search_target(self, search_target: dict) -> list[dict]:
        raise NotImplementedError

    def scrape_all(self, search_targets: list[dict]) -> list[dict]:
        self._seen_keys.clear()
        raw_listings: list[dict] = []

        for index, search_target in enumerate(search_targets):
            try:
                search_url = search_target.get("search_url")
                self.logger.info("Processing search URL: %s", search_url)
                listings = self.scrape_search_target(search_target)
                raw_listings.extend(self._dedupe_raw_listings(listings))
                self.logger.info(
                    'Search "%s %s" returned %s raw listings',
                    search_target.get("make_name"),
                    search_target.get("model_name"),
                    len(listings),
                )
            except Exception:
                self.logger.exception(
                    "Failed search URL: %s", search_target.get("search_url")
                )

            if index < len(search_targets) - 1 and self.request_delay_seconds > 0:
                time.sleep(self.request_delay_seconds)

        return raw_listings

    def _dedupe_raw_listings(self, listings: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        duplicate_count = 0

        for listing in listings:
            key = self._dedupe_key(listing)
            if key is None:
                deduped.append(listing)
                continue

            if key in self._seen_keys:
                duplicate_count += 1
                continue

            self._seen_keys.add(key)
            deduped.append(listing)

        if duplicate_count:
            self.logger.info("Skipped %s duplicate listings", duplicate_count)

        return deduped

    def _dedupe_key(self, listing: dict) -> tuple[str, str] | None:
        source = str(listing.get("source") or self.source)
        listing_id = listing.get("listing_id")
        if listing_id:
            return source, str(listing_id)

        normalized_url = normalize_url(str(listing.get("url") or ""))
        fallback_id = extract_listing_id(normalized_url)
        if fallback_id:
            return source, fallback_id
        if normalized_url:
            return source, normalized_url

        return None
