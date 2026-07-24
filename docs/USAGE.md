# Usage & Setup Guide

## 1. Installing dependencies into DaVinci Resolve's Python

DaVinci Resolve runs scripts with its **own** bundled Python interpreter, which
does not see packages you `pip install` system‑wide. You have three options:

### Option A — install into Resolve's interpreter
Find Resolve's Python (Resolve **Studio** ships one) and install there:

```bash
# example paths
"/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/.../python" -m pip install faster-whisper
```

### Option B — point Resolve at a virtualenv
Create a venv with the deps and export it before launching Resolve:

```bash
python -m venv ~/.urdu-venv
~/.urdu-venv/bin/pip install -r requirements.txt
export PYTHONPATH="$HOME/.urdu-venv/lib/python3.x/site-packages:$PYTHONPATH"
```

### Option C — run the CLI outside Resolve
Generate the `.srt` with the CLI, then **File → Import → Subtitle** in Resolve.
This needs no changes to Resolve's Python at all.

## 2. Enabling external scripting in Resolve

`Preferences → System → General → External scripting using` → set to **Local**.

Set the scripting env vars (usually auto‑set by the installer, but for a
terminal session):

```bash
# macOS
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"

# Linux
export RESOLVE_SCRIPT_API="/opt/resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/opt/resolve/libs/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```

## 3. Choosing a model

| Model | VRAM | Speed | Urdu quality |
|---|---|---|---|
| `small` | ~2 GB | fast | ok for clean audio |
| `medium` | ~5 GB | medium | good |
| `large-v3` | ~10 GB | slow | **best** (default) |

On CPU‑only machines use `--device cpu` and `medium`; expect roughly real‑time
to a few× slower.

## 4. Workflow inside Resolve

1. Cut your timeline as usual.
2. Run **Workspace → Scripts → Utility → Urdu Auto Subtitles**.
3. Pick the model; optionally tick *Translate to English*.
4. Click **Generate Subtitles**. The panel:
   - renders an audio‑only export of the current timeline,
   - transcribes it to Urdu with Whisper,
   - normalizes the text and formats cues,
   - imports the `.srt` as a subtitle track on the current timeline.
5. Style the subtitle track in the **Edit/Cut** page inspector. Pick an Urdu
   font (e.g. *Noto Nastaliq Urdu*, *Jameel Noori Nastaleeq*) and set alignment
   to right.

## 5. Troubleshooting

- **"Could not import DaVinciResolveScript"** — env vars not set / running from
  outside Resolve. Use the Console inside Resolve or set the vars above.
- **"ffmpeg not found"** — install ffmpeg and ensure it is on PATH.
- **Subtitles render left‑to‑right** — keep `add_rtl_marks` on and choose an
  RTL‑aware Urdu font in the inspector.
- **Import rejected** — subtitle import requires Resolve 18.5+ and a project
  frame rate matching the media.
- **Odd words / hallucinated text in silence** — keep `vad_filter` on and raise
  `no_speech_threshold`.
