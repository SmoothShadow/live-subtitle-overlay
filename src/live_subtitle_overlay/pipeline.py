from __future__ import annotations

from collections.abc import Callable
from difflib import SequenceMatcher
import logging
import threading

from .audio import AudioSource
from .config import AudioConfig
from .asr import SpeechRecognizer
from .models import AudioChunk, SubtitleLine, TranscriptSegment
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


class SpeechGate:
    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._vad = None
        self._vad_error_logged = False
        if config.enable_vad:
            try:
                import webrtcvad

                self._vad = webrtcvad.Vad(max(0, min(3, config.vad_aggressiveness)))
            except Exception:
                self._vad = None

    def should_process(self, chunk: AudioChunk) -> bool:
        if not chunk.pcm:
            return True

        mono_pcm = self._to_mono_pcm(chunk)
        if self._rms_level(mono_pcm) < self._config.silence_rms_threshold:
            return False

        if self._vad is None:
            return True

        if chunk.sample_rate not in {8000, 16000, 32000, 48000}:
            if not self._vad_error_logged:
                logger.info("VAD disabled for unsupported sample rate %s", chunk.sample_rate)
                self._vad_error_logged = True
            return True

        frame_ms = 20
        frame_bytes = int(chunk.sample_rate * frame_ms / 1000) * 2
        if frame_bytes <= 0 or len(mono_pcm) < frame_bytes:
            return True

        speech_frames = 0
        total_frames = 0
        for offset in range(0, len(mono_pcm) - frame_bytes + 1, frame_bytes):
            frame = mono_pcm[offset : offset + frame_bytes]
            total_frames += 1
            if self._vad.is_speech(frame, chunk.sample_rate):
                speech_frames += 1
        if total_frames == 0:
            return True
        return speech_frames > 0

    @staticmethod
    def _to_mono_pcm(chunk: AudioChunk) -> bytes:
        import numpy as np

        if chunk.channels == 1:
            return chunk.pcm
        audio = np.frombuffer(chunk.pcm, dtype=np.int16)
        if len(audio) == 0:
            return b""
        mono = audio.reshape(-1, chunk.channels).mean(axis=1).astype(np.int16)
        return mono.tobytes()

    @staticmethod
    def _rms_level(mono_pcm: bytes) -> float:
        import numpy as np

        audio = np.frombuffer(mono_pcm, dtype=np.int16).astype(np.float32)
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio / 32768.0))))


class SubtitleStabilizer:
    def __init__(self, similarity_threshold: float = 0.9, dedupe_seconds: float = 4.0) -> None:
        self._similarity_threshold = similarity_threshold
        self._dedupe_seconds = dedupe_seconds
        self._last_line: SubtitleLine | None = None

    def filter(self, subtitle: SubtitleLine) -> SubtitleLine | None:
        current_norm = self._normalize(subtitle.source_text or subtitle.text)
        if not current_norm:
            return None
        if self._last_line is None:
            self._last_line = subtitle
            return subtitle

        previous = self._last_line
        previous_norm = self._normalize(previous.source_text or previous.text)
        close_in_time = subtitle.start_ts - previous.end_ts <= self._dedupe_seconds
        similarity = SequenceMatcher(None, previous_norm, current_norm).ratio()

        if close_in_time and current_norm == previous_norm:
            return None
        if close_in_time and previous_norm.startswith(current_norm):
            return None
        if close_in_time and similarity >= self._similarity_threshold and len(current_norm) <= len(previous_norm):
            return None

        self._last_line = subtitle
        return subtitle

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower().strip()
        return "".join(ch for ch in lowered if ch.isalnum() or ch.isspace())


class SegmentAssembler:
    def __init__(self, max_gap_seconds: float = 0.45, max_chars: int = 84, max_span_seconds: float = 6.0) -> None:
        self._max_gap_seconds = max_gap_seconds
        self._max_chars = max_chars
        self._max_span_seconds = max_span_seconds

    def merge(self, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        if not segments:
            return []

        merged: list[TranscriptSegment] = []
        current = segments[0]
        for segment in segments[1:]:
            current_text = current.text.strip()
            next_text = segment.text.strip()
            close_gap = segment.start_ts - current.end_ts <= self._max_gap_seconds
            combined_text = f"{current_text} {next_text}".strip()
            combined_span = segment.end_ts - current.start_ts
            same_language = current.language == segment.language

            if close_gap and same_language and len(combined_text) <= self._max_chars and combined_span <= self._max_span_seconds:
                current = TranscriptSegment(
                    text=combined_text,
                    language=current.language,
                    start_ts=current.start_ts,
                    end_ts=segment.end_ts,
                    is_partial=current.is_partial or segment.is_partial,
                )
                continue

            merged.append(current)
            current = segment

        merged.append(current)
        return merged


class SubtitlePipeline:
    def __init__(
        self,
        audio_source: AudioSource,
        recognizer: SpeechRecognizer,
        translator: Translator,
        on_subtitle: Callable[[SubtitleLine], None],
        audio_config: AudioConfig,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self._audio_source = audio_source
        self._recognizer = recognizer
        self._translator = translator
        self._on_subtitle = on_subtitle
        self._on_status = on_status or (lambda _message: None)
        self._speech_gate = SpeechGate(audio_config)
        self._stabilizer = SubtitleStabilizer()
        self._assembler = SegmentAssembler()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_status: str | None = None

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def _set_status(self, message: str) -> None:
        if message == self._last_status:
            return
        self._last_status = message
        self._on_status(message)

    def start(self) -> None:
        self._set_status("Listening")
        self._audio_source.start()
        self._thread = threading.Thread(target=self._run, name="subtitle-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._set_status("Stopped")
        self._audio_source.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def set_paused(self, paused: bool) -> bool:
        if paused:
            self._pause_event.set()
            self._set_status("Paused")
        else:
            self._pause_event.clear()
            self._set_status("Listening")
        return self._pause_event.is_set()

    def toggle_paused(self) -> bool:
        return self.set_paused(not self._pause_event.is_set())

    def _publish(self, segment: TranscriptSegment) -> None:
        source_text = segment.text.strip()
        if not source_text:
            return

        try:
            translated = self._translator.translate_text(source_text)
        except TranslationError as exc:
            logger.warning("Translator failed, using source text: %s", exc)
            translated = source_text

        filtered = self._stabilizer.filter(
            SubtitleLine(
                text=format_subtitle_text(translated),
                source_text=format_subtitle_text(source_text),
                start_ts=segment.start_ts,
                end_ts=segment.end_ts,
                is_partial=segment.is_partial,
            )
        )
        if filtered is None:
            return
        self._set_status("Translating" if translated != source_text else "Showing source")
        self._on_subtitle(filtered)

    def _run(self) -> None:
        for chunk in self._audio_source.read_chunks(self._stop_event):
            if self._stop_event.is_set():
                break
            if self._pause_event.is_set():
                self._set_status("Paused")
                continue
            if not self._speech_gate.should_process(chunk):
                self._set_status("Listening")
                continue
            try:
                segments = self._recognizer.transcribe(chunk)
            except Exception:
                logger.exception("ASR failed for chunk %.2f -> %.2f", chunk.start_ts, chunk.end_ts)
                self._set_status("ASR error")
                continue
            segments = self._assembler.merge(segments)
            if not segments:
                self._set_status("Listening")
            for segment in segments:
                self._publish(segment)
