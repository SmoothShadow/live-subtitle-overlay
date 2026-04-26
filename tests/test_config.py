import unittest
from unittest.mock import patch

from live_subtitle_overlay.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_defaults_when_env_file_missing(self):
        config = AppConfig.from_env("/tmp/does-not-exist.env")
        self.assertEqual(config.azure.endpoint, "https://api.cognitive.microsofttranslator.com")
        self.assertEqual(config.whisper.model_name, "medium")
        self.assertEqual(config.audio.chunk_seconds, 2.0)
        self.assertTrue(config.audio.enable_vad)

    def test_placeholder_azure_key_is_not_treated_as_enabled(self):
        with patch.dict("os.environ", {"AZURE_TRANSLATOR_KEY": "replace-me"}, clear=False):
            config = AppConfig.from_env("/tmp/does-not-exist.env")
        self.assertFalse(config.azure.is_enabled)


if __name__ == "__main__":
    unittest.main()
