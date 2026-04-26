from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path


@dataclass(slots=True)
class OverlayState:
    x: int = 120
    y: int = 780
    width: int = 960
    height: int = 180
    locked: bool = False
    show_source_text: bool = False
    loopback_device_index: int | None = None


def default_settings_path() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "LiveSubtitleOverlay" / "settings.json"
    return Path.home() / ".live-subtitle-overlay" / "settings.json"


class SettingsStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else default_settings_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> OverlayState:
        if not self._path.exists():
            return OverlayState()
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return OverlayState(
            x=int(payload.get("x", 120)),
            y=int(payload.get("y", 780)),
            width=int(payload.get("width", 960)),
            height=int(payload.get("height", 180)),
            locked=bool(payload.get("locked", False)),
            show_source_text=bool(payload.get("show_source_text", False)),
            loopback_device_index=(
                int(payload["loopback_device_index"])
                if payload.get("loopback_device_index") is not None
                else None
            ),
        )

    def save(self, state: OverlayState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(asdict(state), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
