import unittest

from app.utils.normalize import (
    extract_listing_id,
    extract_price_aud,
    extract_year,
    normalize_location,
    normalize_text,
    normalize_url,
    parse_odometer_km,
    parse_price_aud,
)


class NormalizeTests(unittest.TestCase):
    def test_normalize_text_removes_safe_punctuation(self):
        self.assertEqual(normalize_text("BMW 320i M-Sport"), "bmw 320i m sport")
        self.assertEqual(normalize_text("BMW X3M Competition"), "bmw x3m competition")


    def test_parse_price_aud(self):
        self.assertEqual(parse_price_aud("$12,500"), 12500)
        self.assertEqual(parse_price_aud("A$8,000"), 8000)
        self.assertEqual(parse_price_aud("AUD 8,000"), 8000)
        self.assertEqual(parse_price_aud("8,000"), 8000)
        self.assertIsNone(parse_price_aud("Contact seller"))
        self.assertIsNone(parse_price_aud("145,000 km"))

    def test_extract_price_aud_from_card_text(self):
        self.assertEqual(extract_price_aud("2015 BMW 320i\n$12,500\nPerth"), 12500)
        self.assertEqual(extract_price_aud("BMW X5 AUD 18,000 145,000 km"), 18000)
        self.assertIsNone(extract_price_aud("BMW X5 145,000 km"))


    def test_parse_odometer_km(self):
        self.assertEqual(parse_odometer_km("145,000 km"), 145000)
        self.assertEqual(parse_odometer_km("145000kms"), 145000)
        self.assertEqual(parse_odometer_km("145k km"), 145000)
        self.assertEqual(parse_odometer_km("145 k"), 145000)
        self.assertIsNone(parse_odometer_km("unknown"))
        self.assertIsNone(parse_odometer_km("3.0L engine"))
        self.assertIsNone(parse_odometer_km("320i"))


    def test_extract_year_prefers_title_then_description(self):
        self.assertEqual(
            extract_year("2015 BMW 320i", "2018 service history", current_year=2026),
            2015,
        )
        self.assertEqual(extract_year("BMW 320i", "2015 model", current_year=2026), 2015)
        self.assertIsNone(extract_year("BMW 320i", current_year=2026))


    def test_url_and_listing_id_normalization(self):
        url = "https://facebook.com/marketplace/item/123/?ref=search&tracking=abc"

        self.assertEqual(normalize_url(url), "https://facebook.com/marketplace/item/123")
        self.assertEqual(extract_listing_id(url), "123")
        self.assertEqual(
            normalize_url(None, listing_id="456"),
            "https://www.facebook.com/marketplace/item/456",
        )


    def test_normalize_location(self):
        self.assertEqual(normalize_location("Perth Western Australia"), "Perth, WA")
        self.assertEqual(normalize_location(" Cannington,   WA "), "Cannington, WA")
        self.assertEqual(normalize_location("Morley"), "Morley")


if __name__ == "__main__":
    unittest.main()
