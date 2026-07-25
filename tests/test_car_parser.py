import unittest

from app.parsers.car_parser import CarParser


MAKES = [{"make_id": 1, "make_name": "BMW"}]
MODELS = [
    {"model_id": 1, "make_id": 1, "model_name": "1 Series"},
    {"model_id": 2, "make_id": 1, "model_name": "2 Series"},
    {"model_id": 3, "make_id": 1, "model_name": "3 Series"},
    {"model_id": 4, "make_id": 1, "model_name": "4 Series"},
    {"model_id": 5, "make_id": 1, "model_name": "5 Series"},
    {"model_id": 6, "make_id": 1, "model_name": "6 Series"},
    {"model_id": 7, "make_id": 1, "model_name": "7 Series"},
    {"model_id": 10, "make_id": 1, "model_name": "X3"},
    {"model_id": 17, "make_id": 1, "model_name": "M3"},
    {"model_id": 21, "make_id": 1, "model_name": "X3M"},
    {"model_id": 49, "make_id": 1, "model_name": "unknown"},
]


def make_raw(**overrides):
    raw = {
        "source": "facebook_marketplace",
        "search_make_id": 1,
        "search_make_name": "BMW",
        "search_model_id": 3,
        "search_model_name": "3 Series",
        "search_url": "https://www.facebook.com/marketplace/perth/search?minPrice=5000&query=%22BMW%203%20Series%22&exact=true",
        "listing_id": "123",
        "url": "https://www.facebook.com/marketplace/item/123?ref=search",
        "title": "2015 BMW 320i",
        "price_text": "$12,500",
        "location_text": "Perth Western Australia",
        "description": "Clean 145,000 km car",
        "odometer_text": "145,000 km",
        "image_urls": ["https://img/1.jpg", "", "https://img/1.jpg"],
        "seller_name": "Seller",
        "seller_type": None,
        "scraped_at": "2026-07-07T21:00:00+08:00",
    }
    raw.update(overrides)
    return raw


def parse_title(title: str):
    return CarParser(MAKES, MODELS).parse(make_raw(title=title))


class CarParserTests(unittest.TestCase):
    def test_parser_normalizes_complete_listing_and_preserves_raw_payload(self):
        raw = make_raw()
        car = CarParser(MAKES, MODELS).parse(raw)

        self.assertEqual(car["listing_id"], "123")
        self.assertEqual(
            car["normalized_url"], "https://www.facebook.com/marketplace/item/123"
        )
        self.assertEqual(car["make_name"], "BMW")
        self.assertEqual(car["model_name"], "3 Series")
        self.assertEqual(car["make_id"], 1)
        self.assertEqual(car["model_id"], 3)
        self.assertEqual(car["manufacture_year"], 2015)
        self.assertEqual(car["current_price_aud"], 12500)
        self.assertEqual(car["sell_location"], "Perth, WA")
        self.assertEqual(car["first_seen_at"], "2026-07-07T21:00:00+08:00")
        self.assertEqual(car["odometer_km"], 145000)
        self.assertEqual(car["image_urls"], ["https://img/1.jpg"])
        self.assertEqual(car["year_filter_status"], "eligible")
        self.assertEqual(car["generation_filter_status"], "unknown")
        self.assertEqual(car["series_priority"], 1)
        self.assertFalse(car["requires_review"])
        self.assertIs(car["raw_payload"], raw)

    def test_parser_handles_missing_price_odometer_and_listing_id(self):
        raw = make_raw(
            listing_id=None,
            url="https://www.facebook.com/marketplace/item/999",
            price_text="Contact seller",
            odometer_text=None,
            description="No odometer listed",
        )

        car = CarParser(MAKES, MODELS).parse(raw)

        self.assertEqual(car["listing_id"], "999")
        self.assertIsNone(car["current_price_aud"])
        self.assertIsNone(car["odometer_km"])

    def test_parser_prefers_listing_id_extracted_from_url(self):
        listing_id = "1000639938499289123"
        raw = make_raw(
            listing_id="wrong-id",
            url=f"https://www.facebook.com/marketplace/item/{listing_id}?ref=search",
        )

        car = CarParser(MAKES, MODELS).parse(raw)

        self.assertEqual(car["listing_id"], listing_id)
        self.assertIsInstance(car["listing_id"], str)

    def test_parser_falls_back_to_price_from_raw_card_text(self):
        raw = make_raw(
            price_text=None,
            description="2015 BMW 320i\n$12,500\nPerth, WA",
            raw_payload={
                "card_text": "2015 BMW 320i\n$12,500\nPerth, WA",
                "lines": ["2015 BMW 320i", "$12,500", "Perth, WA"],
            },
        )

        car = CarParser(MAKES, MODELS).parse(raw)

        self.assertEqual(car["current_price_aud"], 12500)

    def test_parser_skips_parts_and_accessories(self):
        car = CarParser(MAKES, MODELS).parse(make_raw(title="BMW 3 Series wheels"))

        self.assertIsNone(car)

    def test_parser_skips_non_bmw_listings(self):
        parser = CarParser(MAKES, MODELS)

        for title in ("2018 Mercedes C200", "2017 MINI Cooper S"):
            with self.subTest(title=title):
                car = parser.parse(
                    make_raw(
                        search_make_name="BMW",
                        title=title,
                        description="Clean car",
                    )
                )

                self.assertIsNone(car)

    def test_parser_filters_known_years_before_2012_and_reviews_missing_year(self):
        parser = CarParser(MAKES, MODELS)

        self.assertIsNone(parser.parse(make_raw(title="2011 BMW 320i")))

        eligible = parser.parse(make_raw(title="2012 BMW 320i"))
        self.assertEqual(eligible["manufacture_year"], 2012)
        self.assertEqual(eligible["year_filter_status"], "eligible")
        self.assertFalse(eligible["requires_review"])

        unknown = parser.parse(
            make_raw(
                title="BMW 320i",
                description="Clean car with full service history",
            )
        )
        self.assertIsNone(unknown["manufacture_year"])
        self.assertEqual(unknown["year_filter_status"], "unknown")
        self.assertTrue(unknown["requires_review"])

    def test_parser_detects_f_g_generation_and_drops_e_generation(self):
        parser = CarParser(MAKES, MODELS)

        f_generation = parser.parse(make_raw(title="2015 BMW F30 320i"))
        self.assertEqual(f_generation["chassis_generation"], "F30")
        self.assertEqual(f_generation["generation_filter_status"], "eligible")

        g_generation = parser.parse(make_raw(title="2020 BMW G20 320i"))
        self.assertEqual(g_generation["chassis_generation"], "G20")
        self.assertEqual(g_generation["generation_filter_status"], "eligible")

        self.assertIsNone(parser.parse(make_raw(title="2012 BMW E90 320i")))

        unknown = parser.parse(make_raw(title="2015 BMW 320i"))
        self.assertIsNone(unknown["chassis_generation"])
        self.assertEqual(unknown["generation_filter_status"], "unknown")

    def test_bmw_model_mapping_examples(self):
        self.assertEqual(parse_title("2015 BMW 320i")["model_name"], "3 Series")
        self.assertEqual(parse_title("2017 BMW M340i")["model_name"], "3 Series")
        self.assertEqual(parse_title("2016 BMW M3 Competition")["model_name"], "M3")
        self.assertEqual(parse_title("2019 BMW X3 M40i")["model_name"], "X3")
        self.assertEqual(parse_title("2020 BMW X3M Competition")["model_name"], "X3M")

    def test_parse_many_deduplicates_by_listing_id(self):
        parser = CarParser(MAKES, MODELS)
        cars = parser.parse_many([make_raw(), make_raw(price_text="$13,000")])

        self.assertEqual(len(cars), 1)

    def test_parse_many_orders_cars_by_bmw_series_priority(self):
        parser = CarParser(MAKES, MODELS)
        titles = [
            "2015 BMW 120i",
            "2015 BMW 520i",
            "2015 BMW 220i",
            "2015 BMW X3",
            "2015 BMW 320i",
        ]
        raw_listings = [
            make_raw(
                listing_id=str(index),
                url=f"https://www.facebook.com/marketplace/item/{index}",
                title=title,
            )
            for index, title in enumerate(titles, start=1)
        ]

        cars = parser.parse_many(raw_listings)

        self.assertEqual(
            [car["model_name"] for car in cars],
            ["3 Series", "2 Series", "5 Series", "1 Series", "X3"],
        )
        self.assertEqual(
            [car["series_priority"] for car in cars],
            [1, 2, 3, 5, 6],
        )


if __name__ == "__main__":
    unittest.main()
