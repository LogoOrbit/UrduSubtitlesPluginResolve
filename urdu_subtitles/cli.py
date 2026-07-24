"""Command-line interface for standalone Urdu transcription.

Usage:
    python -m urdu_subtitles.cli input.mp4 -o out.srt --model large-v3
    python -m urdu_subtitles.cli input.wav --translate --format vtt
"""

from __future__ import annotations

import argparse
import sys

from .core.config import TranscriptionConfig, VALID_MODELS, VALID_ENGINES
from .core.pipeline import transcribe_to_subtitles


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="urdu-subtitles",
        description="Generate proper Urdu subtitles from any media file.",
    )
    p.add_argument("input", help="Path to audio/video file")
    p.add_argument("-o", "--output", help="Output subtitle path (.srt/.vtt)")
    p.add_argument("--engine", choices=VALID_ENGINES, default="faster-whisper")
    p.add_argument("--model", choices=VALID_MODELS, default="large-v3")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--translate", action="store_true",
                   help="Translate to English instead of Urdu transcription")
    p.add_argument("--format", choices=["srt", "vtt"], default="srt")
    p.add_argument("--no-rtl", action="store_true",
                   help="Do not add RTL embedding marks")
    p.add_argument("--no-normalize", action="store_true",
                   help="Skip Urdu text normalization")
    p.add_argument("--digits", choices=["urdu", "arabic", "latin", "none"],
                   default="urdu")
    p.add_argument("--max-chars", type=int, default=42,
                   help="Max characters per subtitle line")
    p.add_argument("--beam-size", type=int, default=5)
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = TranscriptionConfig(
        engine=args.engine,
        model=args.model,
        device=args.device,
        task="translate" if args.translate else "transcribe",
        output_format=args.format,
        add_rtl_marks=not args.no_rtl,
        normalize_text=not args.no_normalize,
        convert_digits=args.digits,
        max_chars_per_line=args.max_chars,
        beam_size=args.beam_size,
    )
    try:
        cfg.validate()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def progress(frac, text):
        if not args.quiet:
            bar = "#" * int(frac * 30)
            print(f"\r[{bar:<30}] {int(frac*100):3d}%  {text[:40]:<40}",
                  end="", file=sys.stderr, flush=True)

    try:
        out = transcribe_to_subtitles(
            args.input, args.output, cfg,
            progress=None if args.quiet else progress,
        )
    except (FileNotFoundError, RuntimeError, ImportError) as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
