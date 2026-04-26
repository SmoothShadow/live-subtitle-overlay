from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
import queue
import threading
import time
from typing import Any

from .config import AudioConfig
from .models import AudioChunk


class AudioSourceInitializationError(RuntimeError):
    """Raised when the loopback audio source cannot be initialized."""


class AudioSource(ABC):
    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_chunks(self, stop_event: threading.Event) -> Iterator[AudioChunk]:
        raise NotImplementedError


class DemoAudioSource(AudioSource):
    def __init__(self, interval_seconds: float = 2.0) -> None:
        self._interval_seconds = interval_seconds

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def read_chunks(self, stop_event: threading.Event) -> Iterator[AudioChunk]:
        while not stop_event.is_set():
            now = time.time()
            yield AudioChunk(
                pcm=b"",
                sample_rate=16000,
                channels=1,
                start_ts=now - self._interval_seconds,
                end_ts=now,
            )
            time.sleep(self._interval_seconds)


class PyAudioLoopbackSource(AudioSource):
    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=32)
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._pyaudio = None
        self._stream = None
        self._device_info = None
        self._bytes_per_second = 0
        self._current_chunk_start = 0.0

    @staticmethod
    def _load_pyaudio():
        try:
            import pyaudiowpatch as pyaudio
        except ModuleNotFoundError as exc:
            raise AudioSourceInitializationError(
                "PyAudioWPatch is not installed. Install dependencies on Windows to enable WASAPI loopback capture."
            ) from exc
        return pyaudio

    def _resolve_loopback_device(self, pyaudio_module, manager):
        if self._config.loopback_device_index is not None:
            selected = manager.get_device_info_by_index(self._config.loopback_device_index)
            if selected.get("isLoopbackDevice"):
                return selected
            for loopback in manager.get_loopback_device_info_generator():
                if int(loopback["index"]) == int(selected["index"]):
                    return loopback
            raise RuntimeError(
                f"Configured device index {self._config.loopback_device_index} is not a WASAPI loopback device."
            )

        wasapi_info = manager.get_host_api_info_by_type(pyaudio_module.paWASAPI)
        default_speakers = manager.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        if default_speakers.get("isLoopbackDevice"):
            return default_speakers

        for loopback in manager.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                return loopback
        raise RuntimeError(
            "Default WASAPI loopback device not found. Run `python -m pyaudiowpatch` on Windows to inspect devices."
        )

    def resolve_device(self):
        pyaudio = self._load_pyaudio()
        manager = pyaudio.PyAudio()
        try:
            return self._resolve_loopback_device(pyaudio, manager)
        finally:
            manager.terminate()

    def start(self) -> None:
        pyaudio = self._load_pyaudio()
        self._pyaudio = pyaudio
        manager = pyaudio.PyAudio()
        try:
            self._device_info = self._resolve_loopback_device(pyaudio, manager)
        except Exception:
            manager.terminate()
            raise
        self._current_chunk_start = time.time()
        channels = int(self._device_info["maxInputChannels"])
        sample_rate = int(self._device_info["defaultSampleRate"])
        bytes_per_sample = pyaudio.get_sample_size(pyaudio.paInt16)
        self._bytes_per_second = sample_rate * channels * bytes_per_sample
        chunk_bytes = max(1, int(self._bytes_per_second * self._config.chunk_seconds))

        def callback(in_data, frame_count, time_info, status):
            del frame_count, time_info, status
            with self._lock:
                if not self._buffer:
                    self._current_chunk_start = time.time()
                self._buffer.extend(in_data)
                while len(self._buffer) >= chunk_bytes:
                    chunk_start = self._current_chunk_start
                    chunk_end = chunk_start + self._config.chunk_seconds
                    pcm = bytes(self._buffer[:chunk_bytes])
                    del self._buffer[:chunk_bytes]
                    self._current_chunk_start = chunk_end
                    try:
                        self._queue.put_nowait(
                            AudioChunk(
                                pcm=pcm,
                                sample_rate=sample_rate,
                                channels=channels,
                                start_ts=chunk_start,
                                end_ts=chunk_end,
                            )
                        )
                    except queue.Full:
                        pass
            return (in_data, pyaudio.paContinue)

        self._stream = manager.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            frames_per_buffer=self._config.frames_per_buffer,
            input=True,
            input_device_index=self._device_info["index"],
            stream_callback=callback,
        )
        self._stream.start_stream()
        self._manager = manager

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if getattr(self, "_manager", None) is not None:
            self._manager.terminate()
            self._manager = None

    def read_chunks(self, stop_event: threading.Event) -> Iterator[AudioChunk]:
        while not stop_event.is_set():
            try:
                yield self._queue.get(timeout=0.2)
            except queue.Empty:
                continue


def list_loopback_devices() -> list[dict[str, Any]]:
    pyaudio = PyAudioLoopbackSource._load_pyaudio()
    manager = pyaudio.PyAudio()
    devices: list[dict[str, Any]] = []
    try:
        wasapi_info = manager.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_output_index = int(wasapi_info["defaultOutputDevice"])
        default_output = manager.get_device_info_by_index(default_output_index)
        for loopback in manager.get_loopback_device_info_generator():
            devices.append(
                {
                    "index": int(loopback["index"]),
                    "name": str(loopback["name"]),
                    "channels": int(loopback["maxInputChannels"]),
                    "sample_rate": int(loopback["defaultSampleRate"]),
                    "is_default_output": default_output["name"] in loopback["name"],
                }
            )
    finally:
        manager.terminate()
    return devices
