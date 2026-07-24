"""Installer: register the Urdu Subtitles panel with DaVinci Resolve.

Copies ``scripts/urdu_panel.py`` into Resolve's per-user Utility scripts
directory and records the plugin location so the panel can import the package.

Run from the repository root:  python scripts/install.py
"""

from __future__ import annotations

import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_scripts_dir() -> str:
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(
            home, "Library", "Application Support", "Blackmagic Design",
            "DaVinci Resolve", "Fusion", "Scripts", "Utility",
        )
    if sys.platform.startswith("win"):
        return os.path.join(
            os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming")),
            "Blackmagic Design", "DaVinci Resolve", "Fusion", "Scripts", "Utility",
        )
    # Linux
    return os.path.join(
        home, ".local", "share", "DaVinciResolve", "Fusion", "Scripts", "Utility",
    )


def main() -> int:
    dest_dir = resolve_scripts_dir()
    os.makedirs(dest_dir, exist_ok=True)

    src = os.path.join(REPO_ROOT, "scripts", "urdu_panel.py")
    dest = os.path.join(dest_dir, "Urdu Auto Subtitles.py")

    # Inject the plugin home so the copied script can import the package.
    with open(src, "r", encoding="utf-8") as fh:
        content = fh.read()
    header = (
        "import os\n"
        f"os.environ.setdefault('URDU_SUBTITLES_HOME', {REPO_ROOT!r})\n"
    )
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(header + content)

    print(f"Installed panel -> {dest}")
    print("Open DaVinci Resolve and run:")
    print("  Workspace > Scripts > Utility > 'Urdu Auto Subtitles'")
    print("\nMake sure the Python dependencies are installed in Resolve's")
    print("Python environment (see requirements.txt / README).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
