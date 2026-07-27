from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.scrapers.fb_marketplace import FacebookMarketplaceScraper
from app.utils.search_urls import build_facebook_marketplace_search_url


def validate_facebook_storage_state(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError(
            "facebookStorageState must contain an authenticated "
            "Playwright storage state"
        )

    cookies = value.get("cookies")
    origins = value.get("origins")
    if not isinstance(cookies, list) or not cookies:
        raise ValueError(
            "facebookStorageState must contain at least one browser cookie"
        )
    if not isinstance(origins, list):
        raise ValueError(
            "facebookStorageState origins must be a JSON array"
        )

    has_facebook_cookie = any(
        isinstance(cookie, dict)
        and "facebook.com" in str(cookie.get("domain") or "").casefold()
        for cookie in cookies
    )
    if not has_facebook_cookie:
        raise ValueError(
            "facebookStorageState does not contain a Facebook cookie"
        )

    return value


def build_actor_search_targets(actor_input: dict) -> list[dict]:
    location = str(actor_input.get("marketplaceLocation") or "").strip().strip("/")
    if not location:
        raise ValueError("marketplaceLocation must not be empty")

    min_price = int(actor_input.get("minPrice", 5000))
    if min_price < 0:
        raise ValueError("minPrice must be zero or greater")

    model_names = actor_input.get("modelNames") or []
    if not isinstance(model_names, list) or not model_names:
        raise ValueError("modelNames must contain at least one BMW model")

    targets: list[dict] = []
    seen_model_names: set[str] = set()
    for raw_model_name in model_names:
        model_name = str(raw_model_name).strip()
        normalized_model_name = model_name.casefold()
        if not model_name or normalized_model_name in seen_model_names:
            continue

        seen_model_names.add(normalized_model_name)
        targets.append({
            "source": "facebook_marketplace",
            "make_id": None,
            "make_name": "BMW",
            "model_id": None,
            "model_name": model_name,
            "marketplace_location": location,
            "min_price": min_price,
            "search_url": build_facebook_marketplace_search_url(
                marketplace_location=location,
                min_price=min_price,
                make_name="BMW",
                model_name=model_name,
            ),
        })

    if not targets:
        raise ValueError("modelNames must contain at least one non-empty BMW model")
    return targets


async def main() -> None:
    try:
        from apify import Actor
    except ImportError as exc:
        raise RuntimeError(
            "The Apify SDK is required for the Actor entry point. "
            "Run this module in the Apify Python Playwright image."
        ) from exc

    async with Actor:
        actor_input = await Actor.get_input() or {}

        facebook_storage_state = validate_facebook_storage_state(
            actor_input.get("facebookStorageState")
        )

        search_targets = build_actor_search_targets(actor_input)

        scraper_config = SimpleNamespace(
            headless=True,
            request_delay_seconds=float(
                actor_input.get("requestDelaySeconds", 2)
            ),
            max_results_per_search_url=int(
                actor_input.get("maxResultsPerSearchUrl", 50)
            ),
            facebook_storage_state=facebook_storage_state,
        )

        Actor.log.info(
            "Scraping %s BMW Marketplace targets",
            len(search_targets),
        )

        scraper = FacebookMarketplaceScraper(scraper_config)

        # The existing scraper uses Playwright's synchronous API, so run it
        # outside the Actor's asynchronous event-loop thread.
        raw_listings = await asyncio.to_thread(
            scraper.scrape_all,
            search_targets,
        )

        if scraper.last_page_diagnostics:
            Actor.log.info(
                "Facebook page diagnostics: %s",
                scraper.last_page_diagnostics,
            )
            await Actor.set_value(
                "DEBUG_INFO",
                scraper.last_page_diagnostics,
            )

        if scraper.last_page_screenshot:
            await Actor.set_value(
                "DEBUG_SCREENSHOT",
                scraper.last_page_screenshot,
                content_type="image/png",
            )

        Actor.log.info("Collected %s raw listings", len(raw_listings))

        if raw_listings:
            await Actor.push_data(raw_listings)

        Actor.log.info("Dataset upload complete")


if __name__ == "__main__":
    asyncio.run(main())
