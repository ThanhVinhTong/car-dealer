from __future__ import annotations

import re
import time
from datetime import datetime

from app.scrapers.base import BaseScraper
from app.utils.normalize import extract_listing_id, normalize_url


class FacebookMarketplaceScraper(BaseScraper):
    source = "facebook_marketplace"

    def __init__(self, config) -> None:
        super().__init__(
            request_delay_seconds=config.request_delay_seconds,
            max_results_per_search_url=config.max_results_per_search_url,
        )
        self.config = config

    def scrape_all(self, search_targets: list[dict]) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for scraping. Install requirements.txt and browser binaries."
            ) from exc

        self._seen_keys.clear()
        raw_listings: list[dict] = []
        self.logger.info("Starting facebook_marketplace scraper")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.set_default_timeout(30_000)

            try:
                for index, search_target in enumerate(search_targets):
                    try:
                        listings = self._scrape_search_target_with_page(
                            page, search_target
                        )
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
            finally:
                browser.close()

        return raw_listings

    def scrape_search_target(self, search_target: dict) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for scraping. Install requirements.txt and browser binaries."
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.set_default_timeout(30_000)
            try:
                return self._scrape_search_target_with_page(page, search_target)
            finally:
                browser.close()

    def _scrape_search_target_with_page(self, page, search_target: dict) -> list[dict]:
        search_url = search_target["search_url"]
        self.logger.info("Processing search URL: %s", search_url)
        page.goto(search_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        listings = self._collect_listing_cards(page, search_target)
        return listings[: self.max_results_per_search_url]

    def _collect_listing_cards(self, page, search_target: dict) -> list[dict]:
        anchors = page.locator('a[href*="/marketplace/item/"]')
        collected: list[dict] = []
        seen_urls: set[str] = set()
        stable_rounds = 0

        for _ in range(4):
            before_count = len(collected)
            anchor_count = anchors.count()

            for index in range(anchor_count):
                if len(collected) >= self.max_results_per_search_url:
                    return collected

                anchor = anchors.nth(index)
                try:
                    href = anchor.get_attribute("href") or ""
                    text = anchor.inner_text(timeout=1500)
                    image_urls = self._extract_image_urls(anchor)
                except Exception:
                    continue

                normalized_url = normalize_url(href)
                if not normalized_url or normalized_url in seen_urls:
                    continue

                seen_urls.add(normalized_url)
                collected.append(
                    self._build_raw_listing(
                        normalized_url=normalized_url,
                        card_text=text,
                        image_urls=image_urls,
                        search_target=search_target,
                    )
                )

            stable_rounds = stable_rounds + 1 if len(collected) == before_count else 0
            if stable_rounds >= 2 or len(collected) >= self.max_results_per_search_url:
                break

            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(int(self.request_delay_seconds * 1000))

        return collected

    def _extract_image_urls(self, anchor) -> list[str]:
        urls: list[str] = []
        try:
            images = anchor.locator("img")
            for index in range(images.count()):
                src = images.nth(index).get_attribute("src")
                if src:
                    urls.append(src)
        except Exception:
            return []
        return urls

    def _build_raw_listing(
        self,
        *,
        normalized_url: str,
        card_text: str,
        image_urls: list[str],
        search_target: dict,
    ) -> dict:
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in card_text.splitlines()
            if line.strip()
        ]
        price_text = next((line for line in lines if "$" in line or "AUD" in line), None)
        title = next((line for line in lines if line != price_text), None)
        location_text = lines[-1] if len(lines) > 2 else None
        listing_id = extract_listing_id(normalized_url)
        scraped_at = datetime.now().astimezone().isoformat(timespec="seconds")

        return {
            "source": self.source,
            "search_make_id": search_target.get("make_id"),
            "search_make_name": search_target.get("make_name"),
            "search_model_id": search_target.get("model_id"),
            "search_model_name": search_target.get("model_name"),
            "marketplace_location": search_target.get("marketplace_location"),
            "min_price": search_target.get("min_price"),
            "search_url": search_target.get("search_url"),
            "listing_id": listing_id,
            "url": normalized_url,
            "title": title,
            "price_text": price_text,
            "location_text": location_text,
            "description": card_text,
            "odometer_text": None,
            "image_urls": image_urls,
            "seller_name": None,
            "seller_type": None,
            "raw_payload": {"card_text": card_text, "lines": lines},
            "scraped_at": scraped_at,
        }
