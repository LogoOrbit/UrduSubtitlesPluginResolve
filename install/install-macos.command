#!/bin/bash
# Double-click this file (macOS) to install Urdu Auto Subtitles into DaVinci
# Resolve 20+. It downloads the latest installer from GitHub and runs it.
set -e
REF="claude/urdu-auto-transcription-davinci-kwmp6a"
URL="https://raw.githubusercontent.com/LogoOrbit/UrduSubtitlesPluginResolve/${REF}/scripts/install.py"
echo "Fetching installer…"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python 3 is required. Install it from https://www.python.org/downloads/"
  read -n1 -r -p "Press any key to close…"; exit 1
fi
curl -fsSL "$URL" | "$PY" -
echo
read -n1 -r -p "Done. Press any key to close…"
