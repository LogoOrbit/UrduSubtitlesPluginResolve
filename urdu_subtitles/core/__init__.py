"""Core transcription and subtitle-processing package."""

from .config import TranscriptionConfig
from .transcriber import UrduTranscriber, TranscriptSegment
from .subtitles import SubtitleBuilder, write_srt
from .urdu_text import normalize_urdu, shape_for_display, is_urdu_text

__all__ = [
    "TranscriptionConfig",
    "UrduTranscriber",
    "TranscriptSegment",
    "SubtitleBuilder",
    "write_srt",
    "normalize_urdu",
    "shape_for_display",
    "is_urdu_text",
]
