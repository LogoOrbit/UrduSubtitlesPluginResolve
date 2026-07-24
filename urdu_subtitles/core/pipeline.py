"""End-to-end pipeline: media file -> Urdu subtitle file."""

from __future__ import annotations

import os
from typing import Optional

from .config import TranscriptionConfig
from .subtitles import SubtitleBuilder, save_subtitles
from .transcriber import UrduTranscriber, ProgressCB


def transcribe_to_subtitles(
    media_path: str,
    output_path: Optional[str] = None,
    config: Optional[TranscriptionConfig] = None,
    progress: Optional[ProgressCB] = None,
) -> str:
    """Transcribe ``media_path`` and write an SRT/VTT next to it.

    Returns the path to the written subtitle file.
    """
    cfg = config or TranscriptionConfig()
    cfg.validate()

    if output_path is None:
        base, _ = os.path.splitext(media_path)
        ext = ".vtt" if cfg.output_format == "vtt" else ".srt"
        output_path = base + ".ur" + ext

    transcriber = UrduTranscriber(cfg)
    segments = transcriber.transcribe(media_path, progress=progress)

    builder = SubtitleBuilder(cfg)
    cues = builder.build(segments)

    save_subtitles(cues, output_path, cfg)
    return output_path
