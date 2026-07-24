"""Configuration for the Urdu transcription pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


# Whisper models ordered by size/accuracy. "large-v3" gives the best Urdu
# accuracy; "medium" is a good speed/quality compromise on modest hardware.
VALID_MODELS = (
    "tiny", "base", "small", "medium",
    "large", "large-v2", "large-v3",
)

VALID_ENGINES = ("faster-whisper", "openai-whisper")


@dataclass
class TranscriptionConfig:
    """All tunable parameters for a transcription run.

    Defaults are chosen for high-quality Urdu subtitles rather than raw speed.
    """

    # --- Model / engine -------------------------------------------------
    engine: str = "faster-whisper"
    model: str = "large-v3"
    language: str = "ur"                 # ISO-639-1 code for Urdu
    device: str = "auto"                 # "auto" | "cpu" | "cuda"
    compute_type: str = "auto"           # faster-whisper quantization
    beam_size: int = 5
    temperature: float = 0.0
    # Force translation to English instead of transcription in-language.
    task: str = "transcribe"             # "transcribe" | "translate"

    # --- Voice activity / quality --------------------------------------
    vad_filter: bool = True              # drop silence -> fewer hallucinations
    vad_min_silence_ms: int = 500
    condition_on_previous_text: bool = True
    # Below this avg log-prob a segment is treated as unreliable.
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    initial_prompt: Optional[str] = (
        "یہ اردو زبان میں ایک تقریر ہے۔"  # nudges Whisper toward Urdu script
    )

    # --- Subtitle formatting -------------------------------------------
    max_chars_per_line: int = 42
    max_lines_per_cue: int = 2
    min_cue_duration: float = 0.8        # seconds
    max_cue_duration: float = 6.0        # seconds
    max_cue_gap_merge: float = 0.25      # merge cues closer than this
    reading_speed_cps: float = 17.0      # chars/sec target for splitting

    # --- Urdu text handling --------------------------------------------
    normalize_text: bool = True          # unify Arabic/Urdu code points
    add_rtl_marks: bool = True           # wrap cues with RLE/PDF for players
    convert_digits: str = "urdu"         # "urdu" | "arabic" | "latin" | "none"

    # --- Output ---------------------------------------------------------
    output_format: str = "srt"           # "srt" | "vtt"

    extra: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.engine not in VALID_ENGINES:
            raise ValueError(
                f"engine must be one of {VALID_ENGINES}, got {self.engine!r}"
            )
        if self.model not in VALID_MODELS:
            raise ValueError(
                f"model must be one of {VALID_MODELS}, got {self.model!r}"
            )
        if self.task not in ("transcribe", "translate"):
            raise ValueError("task must be 'transcribe' or 'translate'")
        if self.max_chars_per_line < 10:
            raise ValueError("max_chars_per_line is unreasonably small")
        if self.min_cue_duration <= 0 or self.max_cue_duration <= 0:
            raise ValueError("cue durations must be positive")
        if self.min_cue_duration >= self.max_cue_duration:
            raise ValueError("min_cue_duration must be < max_cue_duration")

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "TranscriptionConfig":
        data = json.loads(text)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        cfg = cls(**clean)
        cfg.validate()
        return cfg
