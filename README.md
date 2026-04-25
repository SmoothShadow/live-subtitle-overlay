# Live Subtitle Overlay

Windows-only MVP for watching foreign-language video with a transparent, always-on-top Chinese subtitle window.

## Scope

- Captures system playback audio with `WASAPI loopback`
- Runs local ASR with `faster-whisper`
- Translates subtitles with `Azure AI Translator`
- Shows subtitles in a movable desktop overlay instead of injecting into the browser

This repository is structured to keep the moving parts isolated:

- `audio.py`: Windows loopback capture
- `asr.py`: local speech recognition adapters
- `translation.py`: Azure Translator client
- `pipeline.py`: background coordination
- `ui.py`: transparent subtitle window

## Current Status

This is a first-pass MVP skeleton with:

- a working overlay window
- Azure translation integration
- a real `PyAudioWPatch` loopback capture adapter for Windows
- a real `faster-whisper` adapter
- a `--demo` mode so the UI can be verified before Azure and audio devices are configured

You will still need to tune chunking, VAD, buffering, and subtitle smoothing on a real Windows machine.

## Recommended Environment

Use Python `3.11` to `3.13` on Windows. `PyAudioWPatch` officially ships Windows wheels for Python 3.7-3.13.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env
```

Set the Azure Translator values in `.env`.

## Run

UI smoke test:

```bash
live-subtitle-overlay --demo
```

Real pipeline:

```bash
live-subtitle-overlay
```

Useful flags:

```bash
live-subtitle-overlay --demo --show-source
live-subtitle-overlay --config-check
```

## Notes

- Use windowed mode or borderless fullscreen for the player. Exclusive fullscreen can hide the overlay window.
- If Azure is not configured, translation falls back to the original transcript.
- If the default output device changes while the app is running, restart the app.
