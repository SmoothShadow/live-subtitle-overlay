import unittest

from live_subtitle_overlay.models import SubtitleLine
from live_subtitle_overlay.models import AudioChunk
from live_subtitle_overlay.models import TranscriptSegment
from live_subtitle_overlay.pipeline import SegmentAssembler, SubtitlePipeline, SubtitleStabilizer, format_subtitle_text


class _AudioSourceStub:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def read_chunks(self, _stop_event):
        return iter(
            [
                AudioChunk(
                    pcm=b"",
                    sample_rate=16000,
                    channels=1,
                    start_ts=0.0,
                    end_ts=1.0,
                )
            ]
        )


class _RecognizerStub:
    def transcribe(self, _chunk):
        return []


class _TranslatorStub:
    def translate_text(self, text: str) -> str:
        return text


class _AudioConfigStub:
    enable_vad = False
    vad_aggressiveness = 2
    silence_rms_threshold = 0.0


class PipelineTests(unittest.TestCase):
    def test_format_subtitle_text_wraps_long_line(self):
        wrapped = format_subtitle_text(
            "This is a long subtitle line that should wrap into two visible rows.",
            line_width=20,
        )
        self.assertIn("\n", wrapped)

    def test_stabilizer_skips_duplicate_subtitles(self):
        stabilizer = SubtitleStabilizer()
        first = SubtitleLine(text="你好", source_text="hello there", start_ts=1.0, end_ts=2.0)
        duplicate = SubtitleLine(text="你好", source_text="hello there", start_ts=2.2, end_ts=3.0)
        self.assertIsNotNone(stabilizer.filter(first))
        self.assertIsNone(stabilizer.filter(duplicate))

    def test_stabilizer_keeps_longer_revision(self):
        stabilizer = SubtitleStabilizer()
        first = SubtitleLine(text="你好", source_text="hello", start_ts=1.0, end_ts=2.0)
        revised = SubtitleLine(text="你好啊", source_text="hello there", start_ts=2.1, end_ts=3.0)
        self.assertIsNotNone(stabilizer.filter(first))
        self.assertIsNotNone(stabilizer.filter(revised))

    def test_segment_assembler_merges_close_segments(self):
        assembler = SegmentAssembler()
        merged = assembler.merge(
            [
                TranscriptSegment(text="hello", language="en", start_ts=0.0, end_ts=0.8),
                TranscriptSegment(text="there", language="en", start_ts=1.0, end_ts=1.5),
            ]
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].text, "hello there")

    def test_pipeline_pause_toggle_updates_status(self):
        statuses: list[str] = []
        pipeline = SubtitlePipeline(
            audio_source=_AudioSourceStub(),
            recognizer=_RecognizerStub(),
            translator=_TranslatorStub(),
            on_subtitle=lambda _subtitle: None,
            audio_config=_AudioConfigStub(),
            on_status=statuses.append,
        )

        self.assertTrue(pipeline.set_paused(True))
        self.assertFalse(pipeline.set_paused(False))
        self.assertEqual(statuses, ["Paused", "Listening"])


if __name__ == "__main__":
    unittest.main()
