from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from .audio import AudioSourceInitializationError, DemoAudioSource, PyAudioLoopbackSource, list_loopback_devices
from .asr import FasterWhisperRecognizer, MockRecognizer, RecognizerInitializationError
from .config import AppConfig
from .diagnostics import collect_preflight_diagnostics, run_runtime_diagnostics
from .pipeline import SubtitlePipeline
from .settings import SettingsStore
from .translation import AzureTranslator, PassthroughTranslator
from .ui import SubtitleWindow, choose_loopback_device


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
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available WASAPI loopback devices and exit",
    )
    parser.add_argument(
        "--settings",
        default="",
        help="Path to persisted settings JSON file",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        default=None,
        help="Override WASAPI loopback device index without editing .env",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Run startup diagnostics and exit",
    )
    parser.add_argument(
        "--choose-device",
        action="store_true",
        help="Open a GUI chooser for the loopback capture device and save the selection",
    )
    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _print_diagnostic_report(report) -> None:
    for line in report.render_lines():
        print(line)


def _build_runtime(config: AppConfig, overlay: SubtitleWindow, demo_mode: bool):
    if demo_mode:
        return (
            DemoAudioSource(interval_seconds=config.audio.chunk_seconds),
            MockRecognizer(DEMO_LINES),
            PassthroughTranslator(),
        )

    overlay.set_status("Checking audio")
    audio_source = PyAudioLoopbackSource(config.audio)
    device = audio_source.resolve_device()
    logging.info("Using loopback device: %s", device.get("name", "unknown"))

    overlay.set_status("Loading Whisper")
    recognizer = FasterWhisperRecognizer(config.whisper)
    recognizer.ensure_ready()

    translator = AzureTranslator(config.azure)
    if config.azure.is_enabled:
        overlay.set_status("Ready")
    else:
        overlay.set_status("Source only")
        overlay.show_message(
            "Azure Translator not configured",
            "The overlay will show the source transcript until Azure credentials are added.",
        )

    return audio_source, recognizer, translator


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_env(args.dotenv)
    if args.show_source:
        config.ui.show_source_text = True
    settings_store = SettingsStore(args.settings or None)
    overlay_state = settings_store.load()

    if args.device_index is not None:
        config.audio.loopback_device_index = args.device_index
    elif config.audio.loopback_device_index is None and overlay_state.loopback_device_index is not None:
        config.audio.loopback_device_index = overlay_state.loopback_device_index

    if args.list_devices:
        try:
            for device in list_loopback_devices():
                default_marker = " (default output)" if device["is_default_output"] else ""
                print(
                    f'[{device["index"]}] {device["name"]} | channels={device["channels"]} | '
                    f'sample_rate={device["sample_rate"]}{default_marker}'
                )
        except Exception as exc:
            logging.exception("Unable to list loopback devices")
            print(f"[ERROR] Unable to list loopback devices: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.config_check:
        print(config)
        return 0

    if args.choose_device:
        try:
            devices = list_loopback_devices()
        except Exception as exc:
            logging.exception("Unable to load loopback devices for chooser")
            print(f"[ERROR] Unable to load loopback devices: {exc}", file=sys.stderr)
            return 1

        from PySide6.QtWidgets import QApplication

        qt_app = QApplication(sys.argv)
        selected = choose_loopback_device(devices, selected_index=config.audio.loopback_device_index)
        if selected is None:
            return 0
        overlay_state.loopback_device_index = selected
        settings_store.save(overlay_state)
        print(f"Saved loopback device index {selected} to {settings_store.path}")
        qt_app.quit()
        return 0

    if args.diagnostics:
        report = run_runtime_diagnostics(
            config,
            args.demo,
            platform_name=os.name,
        )
        _print_diagnostic_report(report)
        return 1 if report.has_errors else 0

    preflight = collect_preflight_diagnostics(
        config,
        args.demo,
        platform_name=os.name,
    )
    if preflight.has_errors:
        _print_diagnostic_report(preflight)
        return 1

    overlay_state.width = overlay_state.width or config.ui.width
    overlay_state.height = overlay_state.height or config.ui.height
    if not overlay_state.show_source_text and config.ui.show_source_text:
        overlay_state.show_source_text = True

    from PySide6.QtWidgets import QApplication

    qt_app = QApplication(sys.argv)
    overlay = SubtitleWindow(
        config.ui,
        initial_state=overlay_state,
        on_state_changed=settings_store.save,
    )
    overlay.show()

    if args.demo:
        overlay.set_status("Starting demo")

    try:
        audio_source, recognizer, translator = _build_runtime(config, overlay, args.demo)
    except (AudioSourceInitializationError, RecognizerInitializationError, RuntimeError) as exc:
        logging.exception("Startup validation failed")
        overlay.set_status("Startup error")
        overlay.show_message(
            "Unable to start subtitle capture",
            f"{exc}\nRun `live-subtitle-overlay --diagnostics` or `--list-devices` for more details.",
        )
        return qt_app.exec()

    pipeline = SubtitlePipeline(
        audio_source=audio_source,
        recognizer=recognizer,
        translator=translator,
        on_subtitle=overlay.post_subtitle,
        audio_config=config.audio,
        on_status=overlay.set_status,
    )
    overlay.set_pause_handler(pipeline.toggle_paused)
    overlay.set_paused(False)

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
