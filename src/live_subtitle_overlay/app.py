from __future__ import annotations

import argparse
import logging
import signal
import sys

from .audio import DemoAudioSource, PyAudioLoopbackSource
from .asr import FasterWhisperRecognizer, MockRecognizer
from .config import AppConfig
from .pipeline import SubtitlePipeline
from .translation import AzureTranslator, PassthroughTranslator
from .ui import SubtitleWindow


DEMO_LINES = [
    "I know you are trying to follow the dialogue without subtitles.",
    "This overlay is the simplest MVP shape for Windows playback.",
    "Local ASR runs on your GPU, while translation can stay on Azure free tier.",
    "Once the real pipeline is stable, the next step is subtitle smoothing and hotkeys.",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows live subtitle overlay")
    parser.add_argument("--demo", action="store_true", help="Run UI and pipeline with demo subtitles")
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Print the parsed configuration and exit",
    )
    parser.add_argument(
        "--show-source",
        action="store_true",
        help="Force source transcript line visible",
    )
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Path to the .env file",
    )
    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_env(args.dotenv)
    if args.show_source:
        config.ui.show_source_text = True

    if args.config_check:
        print(config)
        return 0

    from PySide6.QtWidgets import QApplication

    qt_app = QApplication(sys.argv)
    overlay = SubtitleWindow(config.ui)
    overlay.show()

    if args.demo:
        audio_source = DemoAudioSource(interval_seconds=config.audio.chunk_seconds)
        recognizer = MockRecognizer(DEMO_LINES)
        translator = PassthroughTranslator()
    else:
        audio_source = PyAudioLoopbackSource(config.audio)
        recognizer = FasterWhisperRecognizer(config.whisper)
        translator = AzureTranslator(config.azure)

    pipeline = SubtitlePipeline(
        audio_source=audio_source,
        recognizer=recognizer,
        translator=translator,
        on_subtitle=overlay.post_subtitle,
    )

    def shutdown(*_args):
        pipeline.stop()
        overlay.close()
        qt_app.quit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    pipeline.start()
    exit_code = qt_app.exec()
    pipeline.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
