from __future__ import annotations

from abc import ABC, abstractmethod
import time
from typing import Iterable

from .config import WhisperConfig
from .models import AudioChunk, TranscriptSegment


class SpeechRecognizer(ABC):
    @abstractmethod
    def transcribe(self, chunk: AudioChunk) -> list[TranscriptSegment]:
        raise NotImplementedError


class MockRecognizer(SpeechRecognizer):
    def __init__(self, lines: Iterable[str]) -> None:
        self._lines = iter(lines)

    def transcribe(self, chunk: AudioChunk) -> list[TranscriptSegment]:
        try:
            text = next(self._lines)
        except StopIteration:
            return []
        now = time.time()
        return [
            TranscriptSegment(
                text=text,
                language="en",
                start_ts=now - 1.5,
                end_ts=now,
            )
        ]


class FasterWhisperRecognizer(SpeechRecognizer):
    def __init__(self, config: WhisperConfig) -> None:
        self._config = config
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._config.model_name,
                device=self._config.device,
                compute_type=self._config.compute_type,
            )
        return self._model

    @staticmethod
    def _pcm16_to_float32_mono(chunk: AudioChunk):
        import numpy as np

        audio = np.frombuffer(chunk.pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if chunk.channels > 1:
            audio = audio.reshape(-1, chunk.channels).mean(axis=1)

        if chunk.sample_rate == 16000:
            return audio

        src_positions = np.linspace(0, len(audio) - 1, num=len(audio), dtype=np.float32)
        dst_length = max(1, int(round(len(audio) * 16000 / chunk.sample_rate)))
        dst_positions = np.linspace(0, len(audio) - 1, num=dst_length, dtype=np.float32)
        return np.interp(dst_positions, src_positions, audio).astype(np.float32)

    def transcribe(self, chunk: AudioChunk) -> list[TranscriptSegment]:
        if not chunk.pcm:
            return []

        model = self._ensure_model()
        audio = self._pcm16_to_float32_mono(chunk)
        segments, info = model.transcribe(
            audio=audio,
            language=self._config.language,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            vad_filter=False,
            word_timestamps=False,
        )
        language = getattr(info, "language", self._config.language)
        results: list[TranscriptSegment] = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            results.append(
                TranscriptSegment(
                    text=text,
                    language=language,
                    start_ts=chunk.start_ts + float(segment.start),
                    end_ts=chunk.start_ts + float(segment.end),
                )
            )
        return results
