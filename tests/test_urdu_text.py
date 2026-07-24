import io

from urdu_subtitles.core.urdu_text import (
    normalize_urdu, shape_for_display, strip_display_marks,
    is_urdu_text, convert_digits, RLE, PDF,
)


def test_arabic_to_urdu_char_mapping():
    # Arabic kaf (ك) and yeh (ي) -> Urdu keheh (ک) and farsi yeh (ی)
    out = normalize_urdu("كيا", digits="none")
    assert "ك" not in out and "ي" not in out
    assert "ک" in out and "ی" in out


def test_tatweel_and_tashkeel_removed():
    text = "کتـــاب"  # contains kashida
    assert "ـ" not in normalize_urdu(text)


def test_latin_punctuation_to_urdu():
    out = normalize_urdu("kya haal hai?", digits="none")
    assert out.endswith("؟")


def test_digit_conversion_roundtrip():
    urdu = convert_digits("123", "urdu")
    assert urdu == "۱۲۳"
    back = convert_digits(urdu, "latin")
    assert back == "123"


def test_is_urdu_text():
    assert is_urdu_text("یہ اردو ہے")
    assert not is_urdu_text("this is english")


def test_shape_and_strip_roundtrip():
    shaped = shape_for_display("سلام")
    assert shaped.startswith(RLE) and shaped.endswith(PDF)
    assert strip_display_marks(shaped) == "سلام"


def test_whitespace_collapsed():
    assert normalize_urdu("سلام    دنیا") == "سلام دنیا"
