from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import os

from .asr import FasterWhisperRecognizer
from .audio import PyAudioLoopbackSource
from .config import AppConfig


_PLACEHOLDER_KEYS = {"replace-me", "changeme", "your-key-here", "placeholder"}


@dataclass(slots=True)
class DiagnosticIssue:
    severity: str
    summary: str
    detail: str = ""


@dataclass(slots=True)
class DiagnosticReport:
    issues: list[DiagnosticIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def add(self, severity: str, summary: str, detail: str = "") -> None:
        self.issues.append(DiagnosticIssue(severity=severity, summary=summary, detail=detail))

    def render_lines(self) -> list[str]:
        lines: list[str] = []
        for issue in self.issues:
            lines.append(f"[{issue.severity.upper()}] {issue.summary}")
            if issue.detail:
                lines.append(f"  {issue.detail}")
        if not lines:
            lines.append("[OK] No startup issues detected.")
        return lines


def azure_looks_configured(config: AppConfig) -> bool:
    key = config.azure.key.strip()
    return bool(key) and key.lower() not in _PLACEHOLDER_KEYS and bool(config.azure.endpoint.strip())


def collect_preflight_diagnostics(
    config: AppConfig,
    demo_mode: bool,
    *,
    platform_name: str | None = None,
    import_module=importlib.import_module,
) -> DiagnosticReport:
    report = DiagnosticReport()
    current_platform = platform_name or os.name

    try:
        import_module("PySide6")
    except Exception as exc:
        report.add("error", "PySide6 is not available.", str(exc))

    if demo_mode:
        report.add("info", "Demo mode skips Windows audio capture, Whisper, and Azure translation.")
        return report

    if current_platform != "nt":
        report.add(
            "error",
            "Real capture mode requires Windows.",
            f"Detected platform {current_platform!r}; WASAPI loopback is only available on Windows.",
        )

    try:
        import_module("faster_whisper")
    except Exception as exc:
        report.add("error", "faster-whisper is not available.", str(exc))

    try:
        import_module("pyaudiowpatch")
    except Exception as exc:
        report.add("error", "PyAudioWPatch is not available.", str(exc))

    if azure_looks_configured(config):
        report.add("info", "Azure Translator credentials detected.")
    else:
        report.add(
            "warning",
            "Azure Translator is not configured.",
            "The app will fall back to showing the source transcript only.",
        )

    return report


def run_runtime_diagnostics(
    config: AppConfig,
    demo_mode: bool,
    *,
    platform_name: str | None = None,
    import_module=importlib.import_module,
    audio_source_factory=PyAudioLoopbackSource,
    recognizer_factory=FasterWhisperRecognizer,
) -> DiagnosticReport:
    report = collect_preflight_diagnostics(
        config,
        demo_mode,
        platform_name=platform_name,
        import_module=import_module,
    )
    if demo_mode:
        return report

    try:
        audio_source = audio_source_factory(config.audio)
        device = audio_source.resolve_device()
        device_name = str(device.get("name", "unknown device"))
        report.add("info", "Resolved loopback capture device.", device_name)
    except Exception as exc:
        report.add("error", "Audio device resolution failed.", str(exc))

    try:
        recognizer = recognizer_factory(config.whisper)
        recognizer.ensure_ready()
        report.add(
            "info",
            "Whisper model loaded successfully.",
            f"model={config.whisper.model_name} device={config.whisper.device}",
        )
    except Exception as exc:
        report.add("error", "Whisper model initialization failed.", str(exc))

    return report
