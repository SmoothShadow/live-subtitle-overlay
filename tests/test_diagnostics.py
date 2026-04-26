import unittest

from live_subtitle_overlay.config import AppConfig
from live_subtitle_overlay.diagnostics import collect_preflight_diagnostics, run_runtime_diagnostics


class _ImportStub:
    def __init__(self, available: set[str]) -> None:
        self._available = available

    def __call__(self, name: str):
        if name not in self._available:
            raise ModuleNotFoundError(name)
        return object()


class _AudioSourceOk:
    def __init__(self, _config) -> None:
        pass

    def resolve_device(self):
        return {"name": "Speakers (Loopback)"}


class _AudioSourceFail:
    def __init__(self, _config) -> None:
        pass

    def resolve_device(self):
        raise RuntimeError("no loopback device")


class _RecognizerOk:
    def __init__(self, _config) -> None:
        pass

    def ensure_ready(self) -> None:
        return None


class _RecognizerFail:
    def __init__(self, _config) -> None:
        pass

    def ensure_ready(self) -> None:
        raise RuntimeError("cuda unavailable")


class DiagnosticsTests(unittest.TestCase):
    def test_preflight_warns_when_azure_missing(self):
        config = AppConfig.from_env("/tmp/does-not-exist.env")
        import_stub = _ImportStub({"PySide6", "faster_whisper", "pyaudiowpatch"})

        report = collect_preflight_diagnostics(
            config,
            demo_mode=False,
            platform_name="nt",
            import_module=import_stub,
        )

        severities = [issue.severity for issue in report.issues]
        self.assertIn("warning", severities)
        self.assertFalse(report.has_errors)

    def test_preflight_reports_platform_and_dependency_errors(self):
        config = AppConfig.from_env("/tmp/does-not-exist.env")
        import_stub = _ImportStub(set())

        report = collect_preflight_diagnostics(
            config,
            demo_mode=False,
            platform_name="posix",
            import_module=import_stub,
        )

        self.assertTrue(report.has_errors)
        self.assertGreaterEqual(len([issue for issue in report.issues if issue.severity == "error"]), 3)

    def test_runtime_diagnostics_reports_audio_and_model_failures(self):
        config = AppConfig.from_env("/tmp/does-not-exist.env")
        import_stub = _ImportStub({"PySide6", "faster_whisper", "pyaudiowpatch"})

        report = run_runtime_diagnostics(
            config,
            demo_mode=False,
            platform_name="nt",
            import_module=import_stub,
            audio_source_factory=_AudioSourceFail,
            recognizer_factory=_RecognizerFail,
        )

        summaries = [issue.summary for issue in report.issues]
        self.assertIn("Audio device resolution failed.", summaries)
        self.assertIn("Whisper model initialization failed.", summaries)

    def test_runtime_diagnostics_reports_successful_probes(self):
        config = AppConfig.from_env("/tmp/does-not-exist.env")
        import_stub = _ImportStub({"PySide6", "faster_whisper", "pyaudiowpatch"})

        report = run_runtime_diagnostics(
            config,
            demo_mode=False,
            platform_name="nt",
            import_module=import_stub,
            audio_source_factory=_AudioSourceOk,
            recognizer_factory=_RecognizerOk,
        )

        summaries = [issue.summary for issue in report.issues]
        self.assertIn("Resolved loopback capture device.", summaries)
        self.assertIn("Whisper model loaded successfully.", summaries)


if __name__ == "__main__":
    unittest.main()
