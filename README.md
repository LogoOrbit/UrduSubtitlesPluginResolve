# Urdu Auto Subtitles for DaVinci Resolve

Advanced **automatic Urdu transcription** that generates *proper*, broadcast-quality
Urdu subtitles for DaVinci Resolve — right‑to‑left, correctly shaped, cleanly
segmented, and imported straight onto your timeline with one click.

Powered by OpenAI **Whisper** (via `faster-whisper`), tuned for Urdu, with a
dedicated Urdu text‑normalization and RTL layout layer that most generic
Whisper wrappers skip.

---

## Why this is different

Generic "Whisper → SRT" tools produce Urdu that looks wrong: Arabic‑preferred
letterforms, Western digits, punctuation on the wrong side, run‑on cues. This
plugin fixes all of that:

| Concern | What the plugin does |
|---|---|
| **ASR accuracy** | Whisper `large-v3`, Urdu‑primed prompt, VAD filtering to cut hallucinations |
| **Proper Urdu script** | Maps Arabic `ك/ي` → Urdu `ک/ی`, strips kashida & stray tashkeel, NFC‑normalizes |
| **Digits** | Converts to Urdu digits `۰۱۲۳` (configurable) |
| **Punctuation** | `?`→`؟`, `.`→`۔`, correct spacing |
| **RTL rendering** | Wraps each cue in bidi embedding marks so players/Resolve render right‑to‑left |
| **Subtitle craft** | Balanced line wrapping, reading‑speed‑aware splitting, min/max duration, gap merging |
| **Resolve integration** | Renders timeline audio, transcribes, imports SRT as a subtitle track |

## Architecture

```
urdu_subtitles/
├── core/
│   ├── config.py        # TranscriptionConfig — every tunable, validated
│   ├── urdu_text.py     # Urdu normalization, digits, RTL shaping
│   ├── transcriber.py   # Whisper backends + ffmpeg audio extraction
│   ├── subtitles.py     # cue building, wrapping, SRT/VTT writers
│   └── pipeline.py      # media file -> subtitle file
└── resolve/
    ├── resolve_api.py   # DaVinci Resolve scripting wrapper
    └── panel.py         # in‑Resolve UI panel (Fusion UIManager)
scripts/
└── install.py           # self-bootstrapping installer (copies plugin,
                         #   installs deps into Resolve's Python, adds menu item)
install/
├── install-macos.command  # double-click installers that download & run
├── install-windows.bat    #   scripts/install.py from GitHub
└── install-linux.sh
```

The `core` package has **no hard ML dependency at import time** — the Whisper
backend is loaded lazily, so formatting logic and tests run anywhere.

## Install (one step)

Supports **DaVinci Resolve 20 and later** (Free & Studio) on macOS, Windows and
Linux. The installer copies the plugin into Resolve's Scripts folder, installs
the Whisper dependency into Resolve's own Python, and adds the menu item — no
manual file copying.

### Easiest — download & double‑click

| OS | Download this file, then double‑click it |
|----|------------------------------------------|
| **macOS** | [`install/install-macos.command`](https://github.com/LogoOrbit/UrduSubtitlesPluginResolve/raw/claude/urdu-auto-transcription-davinci-kwmp6a/install/install-macos.command) |
| **Windows** | [`install/install-windows.bat`](https://github.com/LogoOrbit/UrduSubtitlesPluginResolve/raw/claude/urdu-auto-transcription-davinci-kwmp6a/install/install-windows.bat) |
| **Linux** | [`install/install-linux.sh`](https://github.com/LogoOrbit/UrduSubtitlesPluginResolve/raw/claude/urdu-auto-transcription-davinci-kwmp6a/install/install-linux.sh) |

> On macOS, if double‑click is blocked: right‑click → **Open**, or run
> `chmod +x install-macos.command` first.

### One‑liner (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/LogoOrbit/UrduSubtitlesPluginResolve/claude/urdu-auto-transcription-davinci-kwmp6a/scripts/install.py | python3 -
```

### One‑liner (Windows PowerShell)

```powershell
python -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/LogoOrbit/UrduSubtitlesPluginResolve/claude/urdu-auto-transcription-davinci-kwmp6a/scripts/install.py').read())"
```

### From a clone

```bash
git clone https://github.com/LogoOrbit/UrduSubtitlesPluginResolve
python UrduSubtitlesPluginResolve/scripts/install.py
```

After installing, open Resolve and run
**Workspace → Scripts → Utility → “Urdu Auto Subtitles”**.

> **ffmpeg** must also be on PATH (`brew install ffmpeg` / `sudo apt install
> ffmpeg` / `choco install ffmpeg`). The installer reminds you if it's missing.
> If it can't find Resolve's Python, it prints the exact `pip install
> faster-whisper` command to run. Details in [`docs/USAGE.md`](docs/USAGE.md).

## Usage

### Inside DaVinci Resolve (one click)

1. Open your project and a timeline.
2. Run the panel, pick a Whisper model, click **Generate Subtitles**.
3. Audio is rendered, transcribed to Urdu, and imported as a subtitle track.

### Standalone CLI

```bash
# Urdu subtitles next to the input file
python -m urdu_subtitles.cli interview.mp4

# Choose model / output / format
python -m urdu_subtitles.cli interview.mp4 -o out.srt --model large-v3

# Translate Urdu speech to English subtitles
python -m urdu_subtitles.cli interview.mp4 --translate --format vtt

# Keep Latin digits, wider lines
python -m urdu_subtitles.cli interview.mp4 --digits latin --max-chars 50
```

### As a library

```python
from urdu_subtitles.core.config import TranscriptionConfig
from urdu_subtitles.core.pipeline import transcribe_to_subtitles

cfg = TranscriptionConfig(model="large-v3", add_rtl_marks=True)
path = transcribe_to_subtitles("clip.wav", "clip.ur.srt", cfg)
print("wrote", path)
```

## Configuration highlights

All options live in `TranscriptionConfig` (`urdu_subtitles/core/config.py`):

- `model`, `engine`, `device`, `beam_size`, `temperature`
- `vad_filter`, `no_speech_threshold`, `log_prob_threshold` — hallucination control
- `max_chars_per_line`, `max_lines_per_cue`, `min/max_cue_duration`, `reading_speed_cps`
- `normalize_text`, `add_rtl_marks`, `convert_digits`

## Development

```bash
pip install pytest
python -m pytest -q
```

The test suite covers Urdu normalization, digit conversion, RTL shaping, line
wrapping, cue splitting/merging, timestamp formatting, and SRT/VTT output — all
without needing the Whisper model or a GPU.

## Requirements

- Python 3.8+
- ffmpeg
- DaVinci Resolve 18.5+ (for subtitle‑track import) — Studio recommended for
  the scripting API
- ~3 GB disk / GPU recommended for the `large-v3` model

## License

MIT
