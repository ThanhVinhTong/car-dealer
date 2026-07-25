import unittest
from unittest.mock import patch


from app.storage.postgres import _format_connection_error
from app.utils.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_from_environment(self):
        env = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "SCRAPER_SOURCE": "facebook_marketplace",
            "MARKETPLACE_LOCATION": "perth",
            "MIN_PRICE": "5000",
            "EXPORT_DIR": "exports",
            "LOG_LEVEL": "DEBUG",
            "HEADLESS": "false",
            "REQUEST_DELAY_SECONDS": "1.5",
            "MAX_RESULTS_PER_SEARCH_URL": "25",
        }

        with patch.dict("os.environ", env, clear=True):
            config = load_config(env_file=None)

        self.assertEqual(config.database_url, "postgresql://user:pass@localhost/db")
        self.assertEqual(config.scraper_source, "facebook_marketplace")
        self.assertEqual(config.marketplace_location, "perth")
        self.assertEqual(config.min_price, 5000)
        self.assertEqual(config.export_dir, "exports")
        self.assertEqual(config.log_level, "DEBUG")
        self.assertFalse(config.headless)
        self.assertEqual(config.request_delay_seconds, 1.5)
        self.assertEqual(config.max_results_per_search_url, 25)

    def test_database_connection_error_includes_safe_supabase_guidance(self):
        message = _format_connection_error(
            "postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
            Exception("could not translate host name"),
        )

        self.assertIn("db.example.supabase.co", message)
        self.assertIn("Session pooler", message)
        self.assertIn("sslmode=require", message)
        self.assertNotIn("secret", message)


if __name__ == "__main__":
    unittest.main()
