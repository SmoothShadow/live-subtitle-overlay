from __future__ import annotations

from collections.abc import Callable
import logging
import threading

from .audio import AudioSource
from .asr import SpeechRecognizer
from .models import SubtitleLine, TranscriptSegment
from .translation import TranslationError, Translator

logger = logging.getLogger(__name__)


def format_subtitle_text(text: str, line_width: int = 22) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= line_width:
        return clean

    words = clean.split(" ")
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        projected = current_len + len(word) + (1 if current else 0)
        if projected > line_width and current:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
            continue
        current.append(word)
        current_len = projected
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines[:2])


class SubtitlePipeline:
    def __init__(
        self,
        audio_source: AudioSource,
        recognizer: SpeechRecognizer,
        translator: Translator,
        on_subtitle: Callable[[SubtitleLine], None],
    ) -> None:
        self._audio_source = audio_source
        self._recognizer = recognizer
        self._translator = translator
        self._on_subtitle = on_subtitle
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._audio_source.start()
        self._thread = threading.Thread(target=self._run, name="subtitle-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._audio_source.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _publish(self, segment: TranscriptSegment) -> None:
        source_text = segment.text.strip()
        if not source_text:
            return

        try:
            translated = self._translator.translate_text(source_text)
        except TranslationError as exc:
            logger.warning("Translator failed, using source text: %s", exc)
            translated = source_text

        self._on_subtitle(
            SubtitleLine(
                text=format_subtitle_text(translated),
                source_text=format_subtitle_text(source_text),
                start_ts=segment.start_ts,
                end_ts=segment.end_ts,
                is_partial=segment.is_partial,
            )
        )

    def _run(self) -> None:
        for chunk in self._audio_source.read_chunks(self._stop_event):
            if self._stop_event.is_set():
                break
            try:
                segments = self._recognizer.transcribe(chunk)
            except Exception:
                logger.exception("ASR failed for chunk %.2f -> %.2f", chunk.start_ts, chunk.end_ts)
                continue
            for segment in segments:
                self._publish(segment)
