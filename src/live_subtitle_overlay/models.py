from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class AudioChunk:
    pcm: bytes
    sample_rate: int
    channels: int
    start_ts: float
    end_ts: float


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    language: Optional[str]
    start_ts: float
    end_ts: float
    is_partial: bool = False


@dataclass(slots=True)
class SubtitleLine:
    text: str
    source_text: str = ""
    start_ts: float = 0.0
    end_ts: float = 0.0
    is_partial: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
