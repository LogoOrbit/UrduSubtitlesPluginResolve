"""DaVinci Resolve UI panel for one-click Urdu subtitling.

Run this from inside Resolve:  Workspace > Scripts > Utility > urdu_panel
(the installer copies ``scripts/urdu_panel.py`` into Resolve's Scripts folder,
which simply imports and calls :func:`main` here).

The panel uses Resolve's bundled Fusion UI Manager (``fusionscript``) so it
needs no external GUI toolkit. If the UI Manager is unavailable it falls back
to a fully automatic run on the current timeline.
"""

from __future__ import annotations

import os
import tempfile
import traceback

from ..core.config import TranscriptionConfig, VALID_MODELS
from ..core.pipeline import transcribe_to_subtitles
from .resolve_api import ResolveConnection, get_resolve, ResolveNotAvailable


def _run_job(conn: ResolveConnection, cfg: TranscriptionConfig, log) -> str:
    work_dir = tempfile.mkdtemp(prefix="urdu_resolve_")
    log("Rendering timeline audio…")
    audio = conn.render_timeline_audio(work_dir)
    log(f"Audio ready: {os.path.basename(audio)}")

    srt_path = os.path.join(work_dir, "urdu_subtitles.srt")
    log(f"Transcribing with Whisper '{cfg.model}' (this can take a while)…")

    def prog(frac, text):
        log(f"[{int(frac * 100):3d}%] {text[:60]}")

    transcribe_to_subtitles(audio, srt_path, cfg, progress=prog)
    log("Importing subtitles into the timeline…")
    conn.import_subtitles(srt_path)
    log("Done. Urdu subtitle track added to the current timeline.")
    return srt_path


def _automatic(cfg: TranscriptionConfig) -> str:
    def log(msg):
        print(f"[UrduSubtitles] {msg}")

    conn = ResolveConnection(get_resolve())
    return _run_job(conn, cfg, log)


def main() -> None:
    try:
        resolve = get_resolve()
    except ResolveNotAvailable as exc:
        print(f"[UrduSubtitles] {exc}")
        return

    fusion = None
    try:
        fusion = resolve.Fusion()
    except Exception:
        fusion = None

    ui = getattr(fusion, "UIManager", None) if fusion else None
    disp = None
    try:
        import BlackmagicFusion as bmd  # type: ignore
        disp = bmd.UIDispatcher(ui) if ui else None
    except Exception:
        disp = None

    if ui is None or disp is None:
        print("[UrduSubtitles] UI Manager unavailable; running automatically.")
        _automatic(TranscriptionConfig())
        return

    # -- Build a small dialog ---------------------------------------------
    win = disp.AddWindow(
        {"ID": "UrduWin", "WindowTitle": "Urdu Auto Subtitles",
         "Geometry": [200, 200, 460, 320]},
        [
            ui.VGroup([
                ui.Label({"Text": "Whisper model", "Weight": 0}),
                ui.ComboBox({"ID": "Model", "Weight": 0}),
                ui.CheckBox({"ID": "Translate", "Text": "Translate to English",
                             "Weight": 0}),
                ui.CheckBox({"ID": "RTL", "Text": "Add RTL marks (recommended)",
                             "Checked": True, "Weight": 0}),
                ui.Label({"ID": "Status", "Text": "Ready.", "Weight": 1,
                          "WordWrap": True}),
                ui.HGroup([
                    ui.Button({"ID": "Run", "Text": "Generate Subtitles"}),
                    ui.Button({"ID": "Close", "Text": "Close"}),
                ]),
            ])
        ],
    )
    itm = win.GetItems()
    for m in VALID_MODELS:
        itm["Model"].AddItem(m)
    itm["Model"].CurrentText = "large-v3"

    def set_status(msg):
        itm["Status"].Text = msg
        print(f"[UrduSubtitles] {msg}")

    def on_close(ev):
        disp.ExitLoop()

    def on_run(ev):
        cfg = TranscriptionConfig(
            model=itm["Model"].CurrentText,
            task="translate" if itm["Translate"].Checked else "transcribe",
            add_rtl_marks=bool(itm["RTL"].Checked),
        )
        try:
            conn = ResolveConnection(resolve)
            _run_job(conn, cfg, set_status)
        except Exception as exc:  # surface any failure in the panel
            set_status(f"Error: {exc}")
            traceback.print_exc()

    win.On.UrduWin.Close = on_close
    win.On.Close.Clicked = on_close
    win.On.Run.Clicked = on_run

    win.Show()
    disp.RunLoop()
    win.Hide()


if __name__ == "__main__":
    main()
