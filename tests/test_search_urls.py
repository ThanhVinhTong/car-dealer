import unittest

from app.utils.search_urls import (
    build_facebook_marketplace_search_url,
    build_search_targets,
)


class SearchUrlTests(unittest.TestCase):
    def test_build_facebook_marketplace_search_url_encodes_quoted_phrase(self):
        url = build_facebook_marketplace_search_url(
            marketplace_location="perth",
            min_price=5000,
            make_name="BMW",
            model_name="3 Series",
        )

        self.assertEqual(
            url,
            "https://www.facebook.com/marketplace/perth/search?minPrice=5000&query=%22BMW%203%20Series%22&exact=true",
        )


    def test_build_search_targets_keeps_only_bmw_and_skips_unknown(self):
        makes = [
            {"make_id": 1, "make_name": "BMW"},
            {"make_id": 2, "make_name": "Audi"},
        ]
        models = [
            {"model_id": 49, "make_id": 1, "model_name": "unknown"},
            {"model_id": 3, "make_id": 1, "model_name": "3 Series"},
            {"model_id": 1, "make_id": 2, "model_name": "A4"},
        ]

        targets = build_search_targets(
            makes=makes,
            models=models,
            marketplace_location="perth",
            min_price=5000,
        )

        self.assertEqual([target["make_name"] for target in targets], ["BMW"])
        self.assertEqual([target["model_name"] for target in targets], ["3 Series"])
        self.assertEqual(targets[0]["make_id"], 1)
        self.assertEqual(targets[0]["model_id"], 3)
        self.assertEqual(targets[0]["source"], "facebook_marketplace")
        self.assertNotIn("unknown", {target["model_name"] for target in targets})

    def test_build_search_targets_uses_bmw_series_priority(self):
        makes = [{"make_id": 1, "make_name": "BMW"}]
        models = [
            {"model_id": 10, "make_id": 1, "model_name": "X3"},
            {"model_id": 1, "make_id": 1, "model_name": "1 Series"},
            {"model_id": 7, "make_id": 1, "model_name": "7 Series"},
            {"model_id": 6, "make_id": 1, "model_name": "6 Series"},
            {"model_id": 5, "make_id": 1, "model_name": "5 Series"},
            {"model_id": 2, "make_id": 1, "model_name": "2 Series"},
            {"model_id": 4, "make_id": 1, "model_name": "4 Series"},
            {"model_id": 3, "make_id": 1, "model_name": "3 Series"},
        ]

        targets = build_search_targets(
            makes=makes,
            models=models,
            marketplace_location="perth",
            min_price=5000,
        )

        self.assertEqual(
            [target["model_name"] for target in targets],
            [
                "3 Series",
                "4 Series",
                "2 Series",
                "5 Series",
                "6 Series",
                "7 Series",
                "1 Series",
                "X3",
            ],
        )
        self.assertEqual(
            [target["series_priority"] for target in targets],
            [1, 1, 2, 3, 3, 4, 5, 6],
        )


if __name__ == "__main__":
    unittest.main()
