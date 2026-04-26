from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


_PLACEHOLDER_SECRET_VALUES = {"replace-me", "changeme", "your-key-here", "placeholder"}


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get_env(key: str, dotenv: dict[str, str], default: str = "") -> str:
    return os.getenv(key, dotenv.get(key, default))


def _get_bool(key: str, dotenv: dict[str, str], default: bool) -> bool:
    raw = _get_env(key, dotenv, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _get_float(key: str, dotenv: dict[str, str], default: float) -> float:
    return float(_get_env(key, dotenv, str(default)))


def _get_int(key: str, dotenv: dict[str, str], default: int) -> int:
    return int(_get_env(key, dotenv, str(default)))


@dataclass(slots=True)
class AzureTranslatorConfig:
    key: str
    endpoint: str
    region: str
    target_language: str
    source_language: str

    @property
    def is_enabled(self) -> bool:
        normalized = self.key.strip().lower()
        return bool(self.endpoint.strip()) and bool(normalized) and normalized not in _PLACEHOLDER_SECRET_VALUES


@dataclass(slots=True)
class WhisperConfig:
    model_name: str
    device: str
    compute_type: str
    language: str


@dataclass(slots=True)
class AudioConfig:
    chunk_seconds: float
    frames_per_buffer: int
    sample_rate_hint: int
    loopback_device_index: int | None
    enable_vad: bool
    vad_aggressiveness: int
    silence_rms_threshold: float


@dataclass(slots=True)
class UiConfig:
    font_size: int
    opacity: float
    width: int
    height: int
    subtitle_timeout_seconds: float
    show_source_text: bool


@dataclass(slots=True)
class AppConfig:
    azure: AzureTranslatorConfig
    whisper: WhisperConfig
    audio: AudioConfig
    ui: UiConfig

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> "AppConfig":
        dotenv = _read_dotenv(Path(dotenv_path or ".env"))
        return cls(
            azure=AzureTranslatorConfig(
                key=_get_env("AZURE_TRANSLATOR_KEY", dotenv),
                endpoint=_get_env(
                    "AZURE_TRANSLATOR_ENDPOINT",
                    dotenv,
                    "https://api.cognitive.microsofttranslator.com",
                ).rstrip("/"),
                region=_get_env("AZURE_TRANSLATOR_REGION", dotenv, "global"),
                target_language=_get_env("TARGET_LANGUAGE", dotenv, "zh-Hans"),
                source_language=_get_env("SOURCE_LANGUAGE", dotenv, "en"),
            ),
            whisper=WhisperConfig(
                model_name=_get_env("WHISPER_MODEL", dotenv, "medium"),
                device=_get_env("WHISPER_DEVICE", dotenv, "cuda"),
                compute_type=_get_env("WHISPER_COMPUTE_TYPE", dotenv, "float16"),
                language=_get_env("SOURCE_LANGUAGE", dotenv, "en"),
            ),
            audio=AudioConfig(
                chunk_seconds=_get_float("CHUNK_SECONDS", dotenv, 2.0),
                frames_per_buffer=_get_int("FRAMES_PER_BUFFER", dotenv, 1024),
                sample_rate_hint=_get_int("SAMPLE_RATE_HINT", dotenv, 48000),
                loopback_device_index=(
                    int(_get_env("WASAPI_LOOPBACK_DEVICE_INDEX", dotenv))
                    if _get_env("WASAPI_LOOPBACK_DEVICE_INDEX", dotenv)
                    else None
                ),
                enable_vad=_get_bool("ENABLE_VAD", dotenv, True),
                vad_aggressiveness=_get_int("VAD_AGGRESSIVENESS", dotenv, 2),
                silence_rms_threshold=_get_float("SILENCE_RMS_THRESHOLD", dotenv, 0.009),
            ),
            ui=UiConfig(
                font_size=_get_int("OVERLAY_FONT_SIZE", dotenv, 30),
                opacity=_get_float("OVERLAY_OPACITY", dotenv, 0.86),
                width=_get_int("OVERLAY_WIDTH", dotenv, 960),
                height=_get_int("OVERLAY_HEIGHT", dotenv, 180),
                subtitle_timeout_seconds=_get_float("SUBTITLE_TIMEOUT_SECONDS", dotenv, 4.5),
                show_source_text=_get_bool("SHOW_SOURCE_TEXT", dotenv, False),
            ),
        )
