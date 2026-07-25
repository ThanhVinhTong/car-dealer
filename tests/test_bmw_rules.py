import unittest

from app.utils.bmw import (
    bmw_series_priority,
    detect_bmw_chassis_generation,
    is_bmw_make_name,
)


class BmwRuleTests(unittest.TestCase):
    def test_is_bmw_make_name_requires_exact_make(self):
        self.assertTrue(is_bmw_make_name(" BMW "))
        self.assertFalse(is_bmw_make_name("MINI"))
        self.assertFalse(is_bmw_make_name("Mercedes-Benz"))

    def test_detect_bmw_chassis_generation_normalizes_common_formats(self):
        self.assertEqual(detect_bmw_chassis_generation("BMW F30 320i"), "F30")
        self.assertEqual(detect_bmw_chassis_generation("BMW f-30 320i"), "F30")
        self.assertEqual(detect_bmw_chassis_generation(None, "BMW G 20"), "G20")
        self.assertEqual(detect_bmw_chassis_generation("BMW E90 320i"), "E90")
        self.assertIsNone(detect_bmw_chassis_generation("BMW 320i"))

    def test_bmw_series_priority_matches_requested_ranking(self):
        priorities = {
            "3 Series": 1,
            "4 Series": 1,
            "2 Series": 2,
            "5 Series": 3,
            "6 Series": 3,
            "7 Series": 4,
            "1 Series": 5,
            "X3": 6,
            "unknown": 6,
        }

        for model_name, expected_priority in priorities.items():
            with self.subTest(model_name=model_name):
                self.assertEqual(
                    bmw_series_priority(model_name),
                    expected_priority,
                )


if __name__ == "__main__":
    unittest.main()
