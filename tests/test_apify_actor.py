import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app import apify_main
from app.scrapers.fb_marketplace import FacebookMarketplaceScraper


FACEBOOK_STORAGE_STATE = {
    "cookies": [
        {
            "name": "c_user",
            "value": "test-session-only",
            "domain": ".facebook.com",
            "path": "/",
            "expires": -1,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }
    ],
    "origins": [],
}


class ActorSearchTargetTests(unittest.TestCase):
    def test_builds_bmw_targets_without_database_reference_ids(self):
        targets = apify_main.build_actor_search_targets(
            {
                "marketplaceLocation": "/perth/",
                "minPrice": 7500,
                "modelNames": ["3 Series", "X3"],
            }
        )

        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]["source"], "facebook_marketplace")
        self.assertEqual(targets[0]["make_name"], "BMW")
        self.assertIsNone(targets[0]["make_id"])
        self.assertIsNone(targets[0]["model_id"])
        self.assertEqual(targets[0]["model_name"], "3 Series")
        self.assertEqual(targets[0]["marketplace_location"], "perth")
        self.assertEqual(targets[0]["min_price"], 7500)
        self.assertIn("/marketplace/perth/search", targets[0]["search_url"])
        self.assertIn("minPrice=7500", targets[0]["search_url"])

    def test_deduplicates_model_names_case_insensitively(self):
        targets = apify_main.build_actor_search_targets(
            {
                "marketplaceLocation": "perth",
                "modelNames": ["3 Series", " 3 series ", "X3", ""],
            }
        )

        self.assertEqual(
            [target["model_name"] for target in targets],
            ["3 Series", "X3"],
        )

    def test_rejects_invalid_actor_input(self):
        invalid_inputs = (
            {"marketplaceLocation": "", "modelNames": ["3 Series"]},
            {"marketplaceLocation": "perth", "modelNames": []},
            {"marketplaceLocation": "perth", "modelNames": "3 Series"},
            {
                "marketplaceLocation": "perth",
                "modelNames": ["3 Series"],
                "minPrice": -1,
            },
        )

        for actor_input in invalid_inputs:
            with self.subTest(actor_input=actor_input):
                with self.assertRaises(ValueError):
                    apify_main.build_actor_search_targets(actor_input)


class FakeActor:
    def __init__(self, actor_input):
        self.actor_input = actor_input
        self.log = Mock()
        self.push_data = AsyncMock()
        self.set_value = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get_input(self):
        return self.actor_input


class ActorEntrypointTests(unittest.IsolatedAsyncioTestCase):
    async def test_actor_pushes_raw_scraper_results_to_default_dataset(self):
        actor = FakeActor(
            {
                "marketplaceLocation": "perth",
                "minPrice": 5000,
                "modelNames": ["3 Series"],
                "maxResultsPerSearchUrl": 5,
                "requestDelaySeconds": 1,
                "facebookStorageState": FACEBOOK_STORAGE_STATE,
            }
        )
        raw_listings = [
            {
                "source": "facebook_marketplace",
                "listing_id": "123",
                "url": "https://www.facebook.com/marketplace/item/123",
                "scraped_at": "2026-07-27T12:00:00+08:00",
            }
        ]
        scraper = Mock()
        scraper.last_page_diagnostics = None
        scraper.last_page_screenshot = None

        with (
            patch.dict(
                sys.modules,
                {"apify": SimpleNamespace(Actor=actor)},
            ),
            patch.object(
                apify_main,
                "FacebookMarketplaceScraper",
                return_value=scraper,
            ) as scraper_class,
            patch.object(
                apify_main.asyncio,
                "to_thread",
                new=AsyncMock(return_value=raw_listings),
            ) as to_thread,
        ):
            await apify_main.main()

        scraper_class.assert_called_once()
        config = scraper_class.call_args.args[0]
        self.assertTrue(config.headless)
        self.assertEqual(config.max_results_per_search_url, 5)
        self.assertEqual(config.request_delay_seconds, 1.0)
        self.assertEqual(
            config.facebook_storage_state,
            FACEBOOK_STORAGE_STATE,
        )
        to_thread.assert_awaited_once()
        self.assertIs(to_thread.call_args.args[0], scraper.scrape_all)
        actor.push_data.assert_awaited_once_with(raw_listings)

    async def test_actor_does_not_create_empty_dataset_items(self):
        actor = FakeActor(
            {
                "marketplaceLocation": "perth",
                "modelNames": ["3 Series"],
                "facebookStorageState": FACEBOOK_STORAGE_STATE,
            }
        )
        scraper = Mock()
        scraper.last_page_diagnostics = None
        scraper.last_page_screenshot = None

        with (
            patch.dict(
                sys.modules,
                {"apify": SimpleNamespace(Actor=actor)},
            ),
            patch.object(
                apify_main,
                "FacebookMarketplaceScraper",
                return_value=scraper,
            ),
            patch.object(
                apify_main.asyncio,
                "to_thread",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await apify_main.main()

        actor.push_data.assert_not_awaited()

    async def test_actor_rejects_missing_facebook_storage_state(self):
        actor = FakeActor(
            {
                "marketplaceLocation": "perth",
                "modelNames": ["3 Series"],
            }
        )

        with patch.dict(
            sys.modules,
            {"apify": SimpleNamespace(Actor=actor)},
        ):
            with self.assertRaises(ValueError):
                await apify_main.main()


class ActorAuthenticationTests(unittest.TestCase):
    def test_validates_facebook_storage_state(self):
        self.assertIs(
            apify_main.validate_facebook_storage_state(
                FACEBOOK_STORAGE_STATE,
            ),
            FACEBOOK_STORAGE_STATE,
        )

    def test_rejects_invalid_facebook_storage_states(self):
        invalid_states = (
            None,
            {},
            {"cookies": [], "origins": []},
            {"cookies": "not-a-list", "origins": []},
            {
                "cookies": [
                    {
                        "name": "session",
                        "value": "wrong-domain",
                        "domain": ".example.com",
                    }
                ],
                "origins": [],
            },
        )

        for state in invalid_states:
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    apify_main.validate_facebook_storage_state(state)

    def test_local_scraper_does_not_require_actor_auth_field(self):
        browser = Mock()
        scraper = FacebookMarketplaceScraper(
            SimpleNamespace(
                request_delay_seconds=0,
                max_results_per_search_url=1,
            )
        )

        scraper._new_browser_context(browser)

        browser.new_context.assert_called_once_with(
            viewport={"width": 1366, "height": 900},
        )

    def test_actor_scraper_passes_storage_state_to_browser(self):
        browser = Mock()
        scraper = FacebookMarketplaceScraper(
            SimpleNamespace(
                request_delay_seconds=0,
                max_results_per_search_url=1,
                facebook_storage_state=FACEBOOK_STORAGE_STATE,
            )
        )

        scraper._new_browser_context(browser)

        browser.new_context.assert_called_once_with(
            viewport={"width": 1366, "height": 900},
            storage_state=FACEBOOK_STORAGE_STATE,
        )

    def test_diagnostics_strip_sensitive_query_parameters(self):
        self.assertEqual(
            FacebookMarketplaceScraper._redact_url_query(
                "https://www.facebook.com/login/?next=%2Fmarketplace%2F"
            ),
            "https://www.facebook.com/login/",
        )


class ActorPackageTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.actor_dir = self.project_root / ".actor"

    def read_json(self, filename):
        return json.loads((self.actor_dir / filename).read_text(encoding="utf-8"))

    def test_actor_definition_references_valid_schema_files(self):
        actor_definition = self.read_json("actor.json")

        self.assertEqual(actor_definition["actorSpecification"], 1)
        self.assertEqual(
            actor_definition["name"],
            "bmw-facebook-marketplace-scraper",
        )
        for key in ("input", "output"):
            referenced = actor_definition[key].removeprefix("./")
            self.assertTrue((self.actor_dir / referenced).is_file())

        dataset_reference = actor_definition["storages"]["dataset"].removeprefix(
            "./"
        )
        self.assertTrue((self.actor_dir / dataset_reference).is_file())

    def test_dataset_contract_contains_raw_webhook_fields(self):
        dataset_schema = self.read_json("dataset_schema.json")
        fields = dataset_schema["fields"]
        properties = fields["properties"]

        self.assertEqual(
            fields["$schema"],
            "http://json-schema.org/draft-07/schema#",
        )
        for field in (
            "source",
            "search_make_id",
            "search_make_name",
            "search_model_id",
            "search_model_name",
            "marketplace_location",
            "min_price",
            "search_url",
            "listing_id",
            "url",
            "title",
            "price_text",
            "location_text",
            "description",
            "odometer_text",
            "image_urls",
            "seller_name",
            "seller_type",
            "raw_payload",
            "scraped_at",
        ):
            self.assertIn(field, properties)

        self.assertEqual(
            fields["required"],
            ["source", "listing_id", "url", "scraped_at"],
        )
        for normalized_field in ("price", "year", "model"):
            self.assertNotIn(normalized_field, properties)

    def test_facebook_storage_state_is_a_required_secret_input(self):
        input_schema = self.read_json("input_schema.json")
        state_field = input_schema["properties"]["facebookStorageState"]

        self.assertIn("facebookStorageState", input_schema["required"])
        self.assertEqual(state_field["type"], "object")
        self.assertTrue(state_field["isSecret"])

    def test_docker_image_runs_actor_entrypoint_without_database_configuration(self):
        dockerfile = (self.actor_dir / "Dockerfile").read_text(encoding="utf-8")
        actor_requirements = (self.actor_dir / "requirements.txt").read_text(
            encoding="utf-8"
        )

        self.assertIn("apify/actor-python-playwright:3.13", dockerfile)
        self.assertIn("pip install", dockerfile)
        self.assertIn("apify==4.0.0", actor_requirements)
        self.assertIn('"app.apify_main"', dockerfile)
        self.assertNotIn("DATABASE_URL", dockerfile)
        self.assertNotIn("app.main", dockerfile)

    def test_local_facebook_session_is_gitignored(self):
        gitignore = (self.project_root / ".gitignore").read_text(
            encoding="utf-8"
        )

        self.assertIn("playwright/.auth/", gitignore)


if __name__ == "__main__":
    unittest.main()
