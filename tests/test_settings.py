import tempfile
import unittest
from pathlib import Path

from live_subtitle_overlay.settings import OverlayState, SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_load_returns_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "settings.json"
            store = SettingsStore(path)
            state = store.load()
            self.assertEqual(state.x, 120)
            self.assertFalse(state.locked)
            self.assertIsNone(state.loopback_device_index)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "settings.json"
            store = SettingsStore(path)
            expected = OverlayState(
                x=1,
                y=2,
                width=3,
                height=4,
                locked=True,
                show_source_text=True,
                loopback_device_index=9,
            )
            store.save(expected)
            loaded = store.load()
            self.assertEqual(loaded, expected)


if __name__ == "__main__":
    unittest.main()
