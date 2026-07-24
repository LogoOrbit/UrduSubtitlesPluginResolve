@echo off
REM Double-click this file (Windows) to install Urdu Auto Subtitles into
REM DaVinci Resolve 20+. It downloads the installer from GitHub and runs it.
setlocal
set REF=claude/urdu-auto-transcription-davinci-kwmp6a
set URL=https://raw.githubusercontent.com/LogoOrbit/UrduSubtitlesPluginResolve/%REF%/scripts/install.py

where py >nul 2>nul && (set PY=py) || (set PY=python)

echo Fetching installer...
%PY% -c "import urllib.request,sys; sys.stdout.buffer.write(urllib.request.urlopen('%URL%').read())" > "%TEMP%\urdu_install.py"
if errorlevel 1 (
  echo Failed to download installer. Is Python 3 installed and on PATH?
  echo Get it from https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% "%TEMP%\urdu_install.py"
echo.
pause
