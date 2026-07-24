"""Speech-to-text transcription for Urdu using Whisper.

Supports two backends:
  * faster-whisper (CTranslate2)  -- default, fast, low memory
  * openai-whisper                -- reference implementation

Both are optional dependencies; import errors are raised only when a run is
actually attempted, so the rest of the package (subtitle formatting, Resolve
integration, tests) works without the heavy ML stack installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional

from .config import TranscriptionConfig
from .urdu_text import normalize_urdu

ProgressCB = Callable[[float, str], None]


@dataclass
class TranscriptSegment:
    """A single recognized span of speech."""

    start: float          # seconds
    end: float            # seconds
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def _pick_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:  # pragma: no cover - depends on runtime hardware
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _ffmpeg_exe() -> str:
    """Locate an ffmpeg binary.

    Prefers a system ffmpeg on PATH; otherwise falls back to the binary that
    ships with the ``imageio-ffmpeg`` pip package, so users never have to
    install ffmpeg separately.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError(
            "No ffmpeg available. Install ffmpeg, or `pip install "
            "imageio-ffmpeg` (bundled by the plugin installer)."
        ) from exc


def extract_audio(
    input_path: str,
    *,
    sample_rate: int = 16000,
    out_path: Optional[str] = None,
) -> str:
    """Extract mono 16 kHz WAV from any media file using ffmpeg.

    Whisper resamples internally, but doing it up front keeps memory low and
    lets us feed the same WAV to either backend.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(input_path)
    ffmpeg = _ffmpeg_exe()
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="urdu_asr_")
        os.close(fd)
    cmd = [
        ffmpeg, "-y", "-i", input_path,
        "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-acodec", "pcm_s16le", out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-2000:]}")
    return out_path


class UrduTranscriber:
    """High-level transcriber that yields normalized Urdu segments."""

    def __init__(self, config: Optional[TranscriptionConfig] = None):
        self.config = config or TranscriptionConfig()
        self.config.validate()
        self._model = None  # lazy

    # -- backend loading ---------------------------------------------------
    def _load_faster_whisper(self):
        from faster_whisper import WhisperModel  # type: ignore

        device = _pick_device(self.config.device)
        compute = self.config.compute_type
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"
        return WhisperModel(self.config.model, device=device, compute_type=compute)

    def _load_openai_whisper(self):
        import whisper  # type: ignore

        device = _pick_device(self.config.device)
        return whisper.load_model(self.config.model, device=device)

    def load(self) -> None:
        if self._model is not None:
            return
        if self.config.engine == "faster-whisper":
            self._model = self._load_faster_whisper()
        else:
            self._model = self._load_openai_whisper()

    # -- transcription -----------------------------------------------------
    def transcribe(
        self,
        media_path: str,
        *,
        progress: Optional[ProgressCB] = None,
    ) -> List[TranscriptSegment]:
        """Transcribe a media/audio file into normalized Urdu segments."""
        cfg = self.config
        self.load()

        cleanup_wav = False
        audio_path = media_path
        ext = os.path.splitext(media_path)[1].lower()
        if ext not in (".wav",):
            audio_path = extract_audio(media_path)
            cleanup_wav = True

        try:
            if cfg.engine == "faster-whisper":
                segments = self._run_faster_whisper(audio_path, progress)
            else:
                segments = self._run_openai_whisper(audio_path, progress)
        finally:
            if cleanup_wav and os.path.exists(audio_path):
                os.remove(audio_path)

        return self._postprocess(segments)

    def _run_faster_whisper(self, audio_path, progress) -> List[TranscriptSegment]:
        cfg = self.config
        vad_params = {"min_silence_duration_ms": cfg.vad_min_silence_ms}
        seg_iter, info = self._model.transcribe(  # type: ignore[union-attr]
            audio_path,
            language=cfg.language,
            task=cfg.task,
            beam_size=cfg.beam_size,
            temperature=cfg.temperature,
            vad_filter=cfg.vad_filter,
            vad_parameters=vad_params if cfg.vad_filter else None,
            condition_on_previous_text=cfg.condition_on_previous_text,
            log_prob_threshold=cfg.log_prob_threshold,
            no_speech_threshold=cfg.no_speech_threshold,
            initial_prompt=cfg.initial_prompt,
        )
        total = getattr(info, "duration", 0.0) or 0.0
        out: List[TranscriptSegment] = []
        for s in seg_iter:
            out.append(
                TranscriptSegment(
                    start=float(s.start),
                    end=float(s.end),
                    text=s.text or "",
                    avg_logprob=float(getattr(s, "avg_logprob", 0.0) or 0.0),
                    no_speech_prob=float(getattr(s, "no_speech_prob", 0.0) or 0.0),
                )
            )
            if progress and total:
                progress(min(1.0, s.end / total), (s.text or "").strip())
        return out

    def _run_openai_whisper(self, audio_path, progress) -> List[TranscriptSegment]:
        cfg = self.config
        result = self._model.transcribe(  # type: ignore[union-attr]
            audio_path,
            language=cfg.language,
            task=cfg.task,
            beam_size=cfg.beam_size,
            temperature=cfg.temperature,
            condition_on_previous_text=cfg.condition_on_previous_text,
            logprob_threshold=cfg.log_prob_threshold,
            no_speech_threshold=cfg.no_speech_threshold,
            initial_prompt=cfg.initial_prompt,
        )
        segs = result.get("segments", [])
        out: List[TranscriptSegment] = []
        n = len(segs) or 1
        for i, s in enumerate(segs):
            out.append(
                TranscriptSegment(
                    start=float(s["start"]),
                    end=float(s["end"]),
                    text=s.get("text", ""),
                    avg_logprob=float(s.get("avg_logprob", 0.0)),
                    no_speech_prob=float(s.get("no_speech_prob", 0.0)),
                )
            )
            if progress:
                progress((i + 1) / n, s.get("text", "").strip())
        return out

    def _postprocess(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        cfg = self.config
        cleaned: List[TranscriptSegment] = []
        for s in segments:
            text = s.text.strip()
            if not text:
                continue
            if s.no_speech_prob >= cfg.no_speech_threshold and \
                    s.avg_logprob < cfg.log_prob_threshold:
                continue  # very likely silence/hallucination
            if cfg.normalize_text:
                text = normalize_urdu(text, digits=cfg.convert_digits)
            if not text:
                continue
            s.text = text
            cleaned.append(s)
        return cleaned
