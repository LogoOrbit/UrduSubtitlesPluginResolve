"""Thin wrapper around the DaVinci Resolve scripting API.

The Resolve scripting module (``DaVinciResolveScript``) is injected by Resolve
into its bundled Python or is importable when the platform environment
variables are set. This module locates it across macOS/Windows/Linux, and
exposes a small, task-focused surface for the subtitles workflow:

    * render the current timeline's audio to a temp WAV,
    * import a generated SRT as a subtitle track on the timeline.

All Resolve access is guarded so the rest of the package can be imported and
unit-tested on machines without Resolve installed.
"""

from __future__ import annotations

import os
import sys
import time
from typing import List, Optional


class ResolveNotAvailable(RuntimeError):
    """Raised when the Resolve scripting API cannot be reached."""


# Default locations of the fusionscript / DaVinciResolveScript modules.
_DEFAULT_MODULE_PATHS = {
    "darwin": [
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
        "Developer/Scripting/Modules",
    ],
    "win32": [
        os.path.join(
            os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
            "Blackmagic Design", "DaVinci Resolve", "Support",
            "Developer", "Scripting", "Modules",
        ),
    ],
    "linux": [
        "/opt/resolve/Developer/Scripting/Modules",
        "/home/resolve/Developer/Scripting/Modules",
    ],
}


def _candidate_module_dirs() -> List[str]:
    dirs: List[str] = []
    env = os.environ.get("RESOLVE_SCRIPT_API")
    if env:
        dirs.append(os.path.join(env, "Modules"))
    platform = "linux" if sys.platform.startswith("linux") else sys.platform
    dirs.extend(_DEFAULT_MODULE_PATHS.get(platform, []))
    return dirs


def get_resolve():
    """Return a live Resolve application object or raise ResolveNotAvailable."""
    try:
        import DaVinciResolveScript as dvr  # type: ignore
    except ImportError:
        dvr = None
        for d in _candidate_module_dirs():
            if os.path.isdir(d) and d not in sys.path:
                sys.path.append(d)
        try:
            import DaVinciResolveScript as dvr  # type: ignore  # noqa: F811
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ResolveNotAvailable(
                "Could not import DaVinciResolveScript. Ensure DaVinci Resolve "
                "is installed and RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB are "
                "set, or run this script from Resolve's Console."
            ) from exc
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:  # pragma: no cover - env dependent
        raise ResolveNotAvailable(
            "scriptapp('Resolve') returned None. Is DaVinci Resolve running "
            "with external scripting enabled (Preferences > System > General)?"
        )
    return resolve


class ResolveConnection:
    """Convenience façade over Resolve project / timeline objects."""

    def __init__(self, resolve=None):
        self.resolve = resolve or get_resolve()
        self.pm = self.resolve.GetProjectManager()
        self.project = self.pm.GetCurrentProject()
        if self.project is None:  # pragma: no cover - env dependent
            raise ResolveNotAvailable("No project is currently open in Resolve.")

    # -- timeline helpers --------------------------------------------------
    def current_timeline(self):
        tl = self.project.GetCurrentTimeline()
        if tl is None:  # pragma: no cover - env dependent
            raise ResolveNotAvailable("No timeline is open in the current project.")
        return tl

    def render_timeline_audio(self, out_dir: str, filename: str = "urdu_audio") -> str:
        """Render the current timeline to a WAV file and return its path.

        Uses a lightweight audio-only render so transcription only needs the
        soundtrack, not a full video export.
        """
        os.makedirs(out_dir, exist_ok=True)
        project = self.project
        project.SetRenderSettings({
            "TargetDir": out_dir,
            "CustomName": filename,
            "ExportVideo": False,
            "ExportAudio": True,
            "AudioCodec": "LinearPCM",
            "AudioSampleRate": 48000,
        })
        # Try a known audio-only preset first; fall back to whatever is active.
        for preset in ("Audio Only", "H.264"):
            try:
                if project.LoadRenderPreset(preset):
                    project.SetRenderSettings({
                        "TargetDir": out_dir,
                        "CustomName": filename,
                        "ExportVideo": False,
                        "ExportAudio": True,
                    })
                    break
            except Exception:
                continue

        job_id = project.AddRenderJob()
        if not job_id:  # pragma: no cover - env dependent
            raise ResolveNotAvailable("Failed to add a render job for audio export.")
        project.StartRendering(job_id)
        while project.IsRenderingInProgress():  # pragma: no cover
            time.sleep(1.0)

        for name in os.listdir(out_dir):
            if name.startswith(filename) and name.lower().endswith(
                (".wav", ".mov", ".mp4", ".aif", ".aiff")
            ):
                return os.path.join(out_dir, name)
        raise ResolveNotAvailable(  # pragma: no cover
            f"Rendered audio not found in {out_dir}."
        )

    def import_subtitles(self, srt_path: str) -> bool:
        """Import an SRT file as a subtitle track on the current timeline.

        Resolve 18.5+ exposes MediaPool.ImportMedia for .srt which lands the
        subtitles as a timeline subtitle track when appended.
        """
        if not os.path.isfile(srt_path):
            raise FileNotFoundError(srt_path)
        media_pool = self.project.GetMediaPool()
        timeline = self.current_timeline()
        self.project.SetCurrentTimeline(timeline)

        items = media_pool.ImportMedia([srt_path])
        if not items:  # pragma: no cover - env dependent
            raise ResolveNotAvailable(
                "Resolve rejected the subtitle import. Requires Resolve 18.5+ "
                "and a matching frame rate."
            )
        ok = media_pool.AppendToTimeline(items)
        return bool(ok)
