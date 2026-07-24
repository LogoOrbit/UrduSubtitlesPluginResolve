#!/usr/bin/env python3
"""One-step installer for the Urdu Auto Subtitles panel in DaVinci Resolve.

Supports DaVinci Resolve 20 and later on macOS, Windows and Linux
(Free and Studio).

What it does:
  1. Locates DaVinci Resolve's per-user Fusion scripts folder.
  2. Copies the whole ``urdu_subtitles`` package into a support folder next to
     it (so nothing extra shows up in the Scripts menu).
  3. Drops a launcher, "Urdu Auto Subtitles.py", into Scripts/Utility so it
     appears under  Workspace > Scripts > Utility.
  4. Installs the Python dependencies (faster-whisper) into Resolve's own
     Python interpreter when it can find it — otherwise prints exact commands.

It works two ways:
  * From a clone:      python scripts/install.py
  * Standalone link:   the script downloads the plugin from GitHub itself, so
                       `curl ... | python3 -` (see README) is enough.
"""

from __future__ import annotations

import glob
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

# --- where to fetch from when run standalone (no local package present) ------
GITHUB_OWNER = "LogoOrbit"
GITHUB_REPO = "UrduSubtitlesPluginResolve"
GITHUB_REF = "claude/urdu-auto-transcription-davinci-kwmp6a"
TARBALL_URL = (
    f"https://codeload.github.com/{GITHUB_OWNER}/{GITHUB_REPO}/tar.gz/{GITHUB_REF}"
)

PACKAGE_NAME = "urdu_subtitles"
SUPPORT_FOLDER = "UrduSubtitles"          # holds the package, off-menu
MENU_SCRIPT_NAME = "Urdu Auto Subtitles.py"


# --------------------------------------------------------------------------- #
# Locating Resolve's folders (Resolve 20+; folder layout is stable across it). #
# --------------------------------------------------------------------------- #
def fusion_base_dir() -> str:
    """Per-user Fusion directory that Resolve reads scripts from."""
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(
            home, "Library", "Application Support", "Blackmagic Design",
            "DaVinci Resolve", "Fusion",
        )
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        # On Windows the per-user scripts live under a "Support" subfolder.
        return os.path.join(
            appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion",
        )
    # Linux
    return os.path.join(home, ".local", "share", "DaVinciResolve", "Fusion")


def scripts_utility_dir() -> str:
    return os.path.join(fusion_base_dir(), "Scripts", "Utility")


def find_resolve_python() -> str | None:
    """Best-effort path to the Python interpreter Resolve ships/uses.

    Resolve embeds/uses CPython; installing deps there means they are visible
    to the in-app panel. Falls back to None (we then print manual commands).
    """
    candidates: list[str] = []
    if sys.platform == "darwin":
        candidates += glob.glob(
            "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/"
            "Resources/*/bin/python3"
        )
        candidates += glob.glob(
            "/Library/Frameworks/Python.framework/Versions/3.*/bin/python3"
        )
    elif sys.platform.startswith("win"):
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        candidates += glob.glob(
            os.path.join(pf, "Blackmagic Design", "DaVinci Resolve", "*", "python.exe")
        )
        localapp = os.environ.get("LOCALAPPDATA", "")
        candidates += glob.glob(
            os.path.join(localapp, "Programs", "Python", "Python3*", "python.exe")
        )
    else:
        candidates += ["/opt/resolve/bin/python3", "/opt/resolve/libs/python3"]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Last resort: whatever python is running the installer.
    return sys.executable


# --------------------------------------------------------------------------- #
# Obtaining the package source (local clone or GitHub download).              #
# --------------------------------------------------------------------------- #
def local_repo_root() -> str | None:
    # __file__ is undefined when this installer is run via exec() of a
    # downloaded string (the curl/PowerShell one-liner); in that case there is
    # no local clone and we fall back to downloading from GitHub.
    script = globals().get("__file__")
    if not script:
        return None
    here = os.path.dirname(os.path.abspath(script))
    root = os.path.dirname(here)
    if os.path.isdir(os.path.join(root, PACKAGE_NAME)):
        return root
    return None


def download_repo(dest: str) -> str:
    print(f"Downloading plugin from GitHub ({GITHUB_REF})…")
    with urllib.request.urlopen(TARBALL_URL) as resp:  # nosec - trusted URL
        data = resp.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest)  # nosec - trusted archive
    for name in os.listdir(dest):
        root = os.path.join(dest, name)
        if os.path.isdir(root) and os.path.isdir(os.path.join(root, PACKAGE_NAME)):
            return root
    raise RuntimeError("Downloaded archive did not contain the plugin package.")


# --------------------------------------------------------------------------- #
# Install steps.                                                              #
# --------------------------------------------------------------------------- #
def copy_package(repo_root: str) -> tuple[str, str]:
    fusion = fusion_base_dir()
    support = os.path.join(fusion, SUPPORT_FOLDER)
    util = scripts_utility_dir()
    os.makedirs(support, exist_ok=True)
    os.makedirs(util, exist_ok=True)

    # Copy the package into the support folder (replace any old copy).
    pkg_src = os.path.join(repo_root, PACKAGE_NAME)
    pkg_dst = os.path.join(support, PACKAGE_NAME)
    if os.path.isdir(pkg_dst):
        shutil.rmtree(pkg_dst)
    shutil.copytree(
        pkg_src, pkg_dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # Write the menu launcher that adds the support folder to sys.path.
    launcher = os.path.join(util, MENU_SCRIPT_NAME)
    launcher_code = (
        "# Auto-generated by the Urdu Auto Subtitles installer.\n"
        "import os, sys\n"
        f"_support = {support!r}\n"
        "if _support not in sys.path:\n"
        "    sys.path.insert(0, _support)\n"
        "from urdu_subtitles.resolve.panel import main\n"
        "main()\n"
    )
    with open(launcher, "w", encoding="utf-8") as fh:
        fh.write(launcher_code)
    return pkg_dst, launcher


def install_dependencies(py: str | None) -> bool:
    if not py:
        return False
    print(f"Installing dependencies into: {py}")
    try:
        subprocess.run(
            [py, "-m", "pip", "install", "--upgrade", "pip"],
            check=False, capture_output=True,
        )
        proc = subprocess.run(
            [py, "-m", "pip", "install", "faster-whisper>=1.0.0"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            print("  (pip reported an issue)")
            print(proc.stderr[-800:])
            return False
        return True
    except Exception as exc:  # pragma: no cover
        print(f"  Could not run pip automatically: {exc}")
        return False


def ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None


def main() -> int:
    print("=" * 60)
    print(" Urdu Auto Subtitles — DaVinci Resolve installer")
    print("=" * 60)

    tmp = None
    root = local_repo_root()
    if root is None:
        tmp = tempfile.mkdtemp(prefix="urdu_install_")
        root = download_repo(tmp)

    try:
        pkg_dst, launcher = copy_package(root)
        print(f"\n[1/3] Plugin files installed:\n      {pkg_dst}")
        print(f"[2/3] Menu launcher installed:\n      {launcher}")

        py = find_resolve_python()
        ok = install_dependencies(py)
        print(f"[3/3] Python dependencies: {'installed' if ok else 'action needed'}")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "-" * 60)
    print("DONE. In DaVinci Resolve (20 or later):")
    print("  Workspace > Scripts > Utility > 'Urdu Auto Subtitles'")
    print("-" * 60)

    if not ok:
        py = find_resolve_python() or "python3"
        print("\nInstall the ASR dependency into Resolve's Python manually:")
        print(f'  "{py}" -m pip install faster-whisper')
    if not ffmpeg_present():
        print("\nAlso install ffmpeg (required for audio extraction):")
        print("  macOS:  brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        print("  Windows: choco install ffmpeg   (or add ffmpeg.exe to PATH)")
    print("\nTip: enable Preferences > System > General >")
    print("     'External scripting using' = Local  (if prompted).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
