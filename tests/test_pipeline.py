import unittest

from live_subtitle_overlay.pipeline import format_subtitle_text


class PipelineTests(unittest.TestCase):
    def test_format_subtitle_text_wraps_long_line(self):
        wrapped = format_subtitle_text(
            "This is a long subtitle line that should wrap into two visible rows.",
            line_width=20,
        )
        self.assertIn("\n", wrapped)


if __name__ == "__main__":
    unittest.main()
