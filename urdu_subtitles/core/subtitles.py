"""Convert transcript segments into well-formed subtitle cues.

Handles the subtitle-craft concerns that Whisper does not:
  * splitting over-long / over-fast segments into multiple cues,
  * merging tiny adjacent fragments,
  * clamping durations,
  * wrapping each cue into <= N balanced RTL lines,
  * emitting SRT or WebVTT with correct Urdu direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, TextIO

from .config import TranscriptionConfig
from .transcriber import TranscriptSegment
from .urdu_text import shape_for_display


@dataclass
class SubtitleCue:
    index: int
    start: float
    end: float
    lines: List[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _fmt_ts(seconds: float, sep: str = ",") -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def wrap_lines(text: str, max_chars: int, max_lines: int) -> List[str]:
    """Greedy word-wrap that balances line lengths for readability.

    Works on whitespace-separated tokens; correct for Urdu since words are
    space-delimited. Returns at most ``max_lines`` lines (last line may exceed
    ``max_chars`` if a single token is longer than the limit).
    """
    words = text.split()
    if not words:
        return []

    # First pass: greedy fill.
    lines: List[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    # If we blew past the line budget, re-balance into exactly max_lines.
    if len(lines) > max_lines:
        lines = _rebalance(words, max_lines)
    return lines


def _rebalance(words: List[str], n_lines: int) -> List[str]:
    """Distribute words across n_lines minimizing the longest line length."""
    total = len(" ".join(words))
    target = total / n_lines
    lines: List[str] = []
    cur = ""
    remaining_lines = n_lines
    for i, w in enumerate(words):
        candidate = f"{cur} {w}".strip()
        words_left = len(words) - i
        # Force a break if the current line is near target and there are still
        # enough words to fill the remaining lines.
        if cur and len(candidate) > target and remaining_lines > 1 \
                and words_left >= remaining_lines:
            lines.append(cur)
            cur = w
            remaining_lines -= 1
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines[:n_lines] if len(lines) > n_lines else lines


class SubtitleBuilder:
    """Turn transcript segments into subtitle cues per the config's rules."""

    def __init__(self, config: Optional[TranscriptionConfig] = None):
        self.config = config or TranscriptionConfig()

    def build(self, segments: List[TranscriptSegment]) -> List[SubtitleCue]:
        cfg = self.config
        merged = self._merge_short(segments)
        cues: List[SubtitleCue] = []
        for seg in merged:
            cues.extend(self._split_segment(seg))
        cues = self._clamp_and_dedupe(cues)
        for i, c in enumerate(cues, start=1):
            c.index = i
        return cues

    def _merge_short(self, segs: List[TranscriptSegment]) -> List[TranscriptSegment]:
        cfg = self.config
        if not segs:
            return []
        out = [TranscriptSegment(**vars(segs[0]))]
        for s in segs[1:]:
            prev = out[-1]
            gap = s.start - prev.end
            too_short = prev.duration < cfg.min_cue_duration
            if gap <= cfg.max_cue_gap_merge and too_short and \
                    (prev.duration + s.duration) <= cfg.max_cue_duration:
                prev.end = s.end
                prev.text = f"{prev.text} {s.text}".strip()
            else:
                out.append(TranscriptSegment(**vars(s)))
        return out

    def _split_segment(self, seg: TranscriptSegment) -> List[SubtitleCue]:
        cfg = self.config
        cue_char_budget = cfg.max_chars_per_line * cfg.max_lines_per_cue
        words = seg.text.split()
        need_split = (
            seg.duration > cfg.max_cue_duration
            or len(seg.text) > cue_char_budget
        )
        if not need_split or len(words) < 2:
            lines = wrap_lines(seg.text, cfg.max_chars_per_line, cfg.max_lines_per_cue)
            return [SubtitleCue(0, seg.start, seg.end, lines)]

        # Number of chunks driven by both char budget and reading speed.
        by_chars = -(-len(seg.text) // cue_char_budget)  # ceil div
        by_dur = -(-int(seg.duration) // int(cfg.max_cue_duration)) or 1
        n_chunks = max(by_chars, by_dur, 1)
        per = -(-len(words) // n_chunks)

        cues: List[SubtitleCue] = []
        total_chars = len(seg.text) or 1
        cursor = seg.start
        for i in range(0, len(words), per):
            chunk = words[i:i + per]
            chunk_text = " ".join(chunk)
            frac = len(chunk_text) / total_chars
            dur = seg.duration * frac
            start = cursor
            end = min(seg.end, start + dur)
            cursor = end
            lines = wrap_lines(chunk_text, cfg.max_chars_per_line, cfg.max_lines_per_cue)
            cues.append(SubtitleCue(0, start, end, lines))
        if cues:
            cues[-1].end = seg.end
        return cues

    def _clamp_and_dedupe(self, cues: List[SubtitleCue]) -> List[SubtitleCue]:
        cfg = self.config
        out: List[SubtitleCue] = []
        for c in cues:
            if not c.lines:
                continue
            if c.end - c.start < cfg.min_cue_duration:
                c.end = c.start + cfg.min_cue_duration
            # Avoid overlap with previous cue.
            if out and c.start < out[-1].end:
                c.start = out[-1].end
                if c.end <= c.start:
                    c.end = c.start + cfg.min_cue_duration
            out.append(c)
        return out


def _render_cue_lines(cue: SubtitleCue, cfg: TranscriptionConfig) -> List[str]:
    if cfg.add_rtl_marks:
        return [shape_for_display(ln) for ln in cue.lines]
    return list(cue.lines)


def write_srt(cues: List[SubtitleCue], fh: TextIO, config: Optional[TranscriptionConfig] = None) -> None:
    cfg = config or TranscriptionConfig()
    for c in cues:
        fh.write(f"{c.index}\n")
        fh.write(f"{_fmt_ts(c.start, ',')} --> {_fmt_ts(c.end, ',')}\n")
        for ln in _render_cue_lines(c, cfg):
            fh.write(ln + "\n")
        fh.write("\n")


def write_vtt(cues: List[SubtitleCue], fh: TextIO, config: Optional[TranscriptionConfig] = None) -> None:
    cfg = config or TranscriptionConfig()
    fh.write("WEBVTT\n\n")
    for c in cues:
        fh.write(f"{c.index}\n")
        fh.write(f"{_fmt_ts(c.start, '.')} --> {_fmt_ts(c.end, '.')}\n")
        for ln in _render_cue_lines(c, cfg):
            fh.write(ln + "\n")
        fh.write("\n")


def save_subtitles(cues: List[SubtitleCue], path: str, config: Optional[TranscriptionConfig] = None) -> str:
    cfg = config or TranscriptionConfig()
    writer = write_vtt if path.lower().endswith(".vtt") else write_srt
    with open(path, "w", encoding="utf-8") as fh:
        writer(cues, fh, cfg)
    return path
