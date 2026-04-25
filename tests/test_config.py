import unittest

from live_subtitle_overlay.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_defaults_when_env_file_missing(self):
        config = AppConfig.from_env("/tmp/does-not-exist.env")
        self.assertEqual(config.azure.endpoint, "https://api.cognitive.microsofttranslator.com")
        self.assertEqual(config.whisper.model_name, "medium")
        self.assertEqual(config.audio.chunk_seconds, 2.0)


if __name__ == "__main__":
    unittest.main()
