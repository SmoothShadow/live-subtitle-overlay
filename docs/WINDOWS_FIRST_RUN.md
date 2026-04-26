# Windows First Run

This runbook is for the first real validation on the target Windows machine.

## Preconditions

- Windows 10 or 11
- Python `3.11` to `3.13`
- NVIDIA driver installed and CUDA-capable GPU available if you want `WHISPER_DEVICE=cuda`
- `.env` created from `.env.example`
- `AZURE_TRANSLATOR_KEY` replaced with the real key

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
```

If PowerShell blocks script execution:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## First Validation Flow

1. Run startup diagnostics.

```powershell
live-subtitle-overlay --diagnostics
```

Expected result:

- no `[ERROR]` lines
- Azure may show only a warning if the key is still missing
- loopback device resolution succeeds
- Whisper model loads successfully

2. Choose the loopback device.

```powershell
live-subtitle-overlay --choose-device
```

Pick the playback device that corresponds to the player output you actually use.

3. Launch the overlay.

```powershell
live-subtitle-overlay
```

4. Start video playback and verify:

- overlay stays on top
- Japanese speech is recognized
- Chinese subtitle line updates
- `Ctrl+Shift+S` pauses and resumes listening
- `Ctrl+Shift+H` hides and shows the overlay globally

## If Something Fails

### Diagnostics says `PyAudioWPatch is not available`

- Confirm you are on Windows
- Reinstall dependencies inside the virtual environment

```powershell
pip install -e .[dev]
```

### Diagnostics says `Whisper model initialization failed`

- If CUDA fails, temporarily switch to CPU in `.env`

```dotenv
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

- Re-run:

```powershell
live-subtitle-overlay --diagnostics
```

### Overlay starts but only shows source transcript

- Check `AZURE_TRANSLATOR_KEY`
- Confirm `AZURE_TRANSLATOR_REGION=eastasia`
- Keep `AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com` unless your Azure portal gave you a different endpoint explicitly

### No subtitles while video is playing

- Verify the selected loopback device matches the actual playback output
- Try `--choose-device` again
- Lower `SILENCE_RMS_THRESHOLD` slightly, for example `0.006`
- Temporarily disable VAD:

```dotenv
ENABLE_VAD=false
```

## Fast Retry Flow

After the first successful device selection, the saved device index is reused automatically. Normal retry loop:

```powershell
live-subtitle-overlay --diagnostics
live-subtitle-overlay
```
