import io

from urdu_subtitles.core.config import TranscriptionConfig
from urdu_subtitles.core.subtitles import (
    SubtitleBuilder, wrap_lines, write_srt, write_vtt, _fmt_ts,
)
from urdu_subtitles.core.transcriber import TranscriptSegment


def seg(start, end, text):
    return TranscriptSegment(start=start, end=end, text=text)


def test_fmt_ts_srt_and_vtt():
    assert _fmt_ts(3661.5, ",") == "01:01:01,500"
    assert _fmt_ts(3661.5, ".") == "01:01:01.500"
    assert _fmt_ts(-5, ",") == "00:00:00,000"


def test_wrap_lines_respects_limits():
    text = "ایک دو تین چار پانچ چھ سات آٹھ نو دس"
    lines = wrap_lines(text, max_chars=12, max_lines=2)
    assert len(lines) <= 2
    assert " ".join(lines).split() == text.split()  # no words lost


def test_builder_indexes_and_orders():
    cfg = TranscriptionConfig()
    segs = [seg(0.0, 2.0, "پہلا جملہ"), seg(2.1, 4.0, "دوسرا جملہ")]
    cues = SubtitleBuilder(cfg).build(segs)
    assert [c.index for c in cues] == list(range(1, len(cues) + 1))
    # monotonic, non-overlapping
    for a, b in zip(cues, cues[1:]):
        assert a.end <= b.start + 1e-6


def test_builder_enforces_min_duration():
    cfg = TranscriptionConfig(min_cue_duration=1.0)
    cues = SubtitleBuilder(cfg).build([seg(0.0, 0.2, "مختصر")])
    assert cues[0].end - cues[0].start >= 1.0


def test_long_segment_is_split():
    cfg = TranscriptionConfig(max_cue_duration=3.0, max_chars_per_line=20,
                              max_lines_per_cue=1)
    long_text = " ".join(["لفظ"] * 40)
    cues = SubtitleBuilder(cfg).build([seg(0.0, 12.0, long_text)])
    assert len(cues) > 1
    assert cues[0].start == 0.0
    assert abs(cues[-1].end - 12.0) < 1e-6


def test_srt_output_has_rtl_marks_when_enabled():
    cfg = TranscriptionConfig(add_rtl_marks=True)
    cues = SubtitleBuilder(cfg).build([seg(0.0, 2.0, "سلام دنیا")])
    buf = io.StringIO()
    write_srt(cues, buf, cfg)
    out = buf.getvalue()
    assert "-->" in out and "‫" in out  # RLE embedded
    assert out.strip().splitlines()[0] == "1"


def test_vtt_header():
    cfg = TranscriptionConfig(add_rtl_marks=False)
    cues = SubtitleBuilder(cfg).build([seg(0.0, 2.0, "سلام")])
    buf = io.StringIO()
    write_vtt(cues, buf, cfg)
    assert buf.getvalue().startswith("WEBVTT")
