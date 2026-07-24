"""Urdu / RTL text normalization and shaping helpers.

Whisper often emits Urdu using Arabic-preferred code points (e.g. Arabic
kaf/yeh instead of Urdu keheh/yeh), inconsistent diacritics, and Western
digits. This module cleans that up so the resulting subtitles are *proper*
Urdu and render correctly in RTL-aware players and in DaVinci Resolve.
"""

from __future__ import annotations

import re
import unicodedata

# Bidi control characters (used to keep punctuation on the correct side).
RLE = "‫"   # Right-to-Left Embedding
PDF = "‬"   # Pop Directional Formatting
RLM = "‏"   # Right-to-Left Mark

# Map Arabic-preferred code points to their Urdu equivalents.
_CHAR_MAP = {
    "ي": "ی",  # Arabic yeh          -> Urdu farsi yeh
    "ى": "ی",  # Alef maksura        -> Urdu farsi yeh
    "ك": "ک",  # Arabic kaf          -> Urdu keheh
    "ۀ": "ہ",  # heh with yeh above  -> heh goal (context dep.)
    "ة": "ہ",  # teh marbuta         -> heh goal
}

# Characters we strip entirely: tatweel/kashida and tashkeel (harakat) that
# ASR models add inconsistently and that hurt subtitle readability.
_TATWEEL = "ـ"
_TASHKEEL_RE = re.compile(r"[ؐ-ًؚ-ْٰۖ-ۭ]")

# Digit maps.
_LATIN_DIGITS = "0123456789"
_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"          # U+0660..
_EXT_ARABIC_INDIC = "۰۱۲۳۴۵۶۷۸۹"     # U+06F0.. (used for Urdu/Persian)

# Urdu block ranges for detection.
_URDU_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def is_urdu_text(text: str, threshold: float = 0.2) -> bool:
    """Return True if a meaningful fraction of letters are Urdu/Arabic script."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    urdu = sum(1 for c in letters if _URDU_RE.match(c))
    return (urdu / len(letters)) >= threshold


def convert_digits(text: str, target: str) -> str:
    """Convert digit glyphs. target: 'urdu' | 'arabic' | 'latin' | 'none'."""
    if target == "none":
        return text
    if target == "urdu":
        table = str.maketrans(
            _LATIN_DIGITS + _ARABIC_INDIC, _EXT_ARABIC_INDIC * 2
        )
    elif target == "arabic":
        table = str.maketrans(
            _LATIN_DIGITS + _EXT_ARABIC_INDIC, _ARABIC_INDIC * 2
        )
    elif target == "latin":
        table = str.maketrans(
            _ARABIC_INDIC + _EXT_ARABIC_INDIC, _LATIN_DIGITS * 2
        )
    else:
        raise ValueError(f"unknown digit target {target!r}")
    return text.translate(table)


def normalize_urdu(
    text: str,
    *,
    strip_tashkeel: bool = True,
    digits: str = "urdu",
) -> str:
    """Normalize Urdu text to consistent, readable code points.

    - NFC normalize
    - map Arabic-preferred glyphs to Urdu equivalents
    - remove kashida and (optionally) tashkeel
    - normalize whitespace and Urdu punctuation spacing
    - convert digit glyphs
    """
    if not text:
        return text

    text = unicodedata.normalize("NFC", text)
    text = text.replace(_TATWEEL, "")
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    if strip_tashkeel:
        text = _TASHKEEL_RE.sub("", text)

    # Normalize common Latin punctuation to Urdu equivalents.
    text = text.replace("?", "؟").replace(";", "؛")
    text = re.sub(r"(?<!\.)\.(?!\.)", "۔", text)  # full stop -> Urdu '۔'

    # Collapse whitespace; no space *before* Urdu punctuation, one space after.
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([۔،؟؛])", r"\1", text)
    text = re.sub(r"([۔،؟؛])(?=\S)", r"\1 ", text)

    text = convert_digits(text, digits)
    return text.strip()


def shape_for_display(text: str) -> str:
    """Wrap a line in RTL embedding marks so mixed content renders correctly.

    Players that are not fully bidi-aware (and some NLE subtitle tracks) place
    trailing Latin punctuation or numbers on the wrong side. Embedding the line
    forces right-to-left base direction for that cue only.
    """
    text = text.strip()
    if not text:
        return text
    return f"{RLE}{text}{PDF}"


def strip_display_marks(text: str) -> str:
    """Remove bidi control characters (inverse of shaping)."""
    for ch in (RLE, PDF, RLM, "‪", "‭", "‮", "⁦",
               "⁧", "⁨", "⁩"):
        text = text.replace(ch, "")
    return text
