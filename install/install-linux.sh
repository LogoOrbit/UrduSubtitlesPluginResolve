#!/usr/bin/env bash
# Run this (Linux) to install Urdu Auto Subtitles into DaVinci Resolve 20+.
# It downloads the latest installer from GitHub and runs it.
set -e
REF="claude/urdu-auto-transcription-davinci-kwmp6a"
URL="https://raw.githubusercontent.com/LogoOrbit/UrduSubtitlesPluginResolve/${REF}/scripts/install.py"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python 3 is required (sudo apt install python3)."
  exit 1
fi
echo "Fetching installer…"
curl -fsSL "$URL" | "$PY" -
