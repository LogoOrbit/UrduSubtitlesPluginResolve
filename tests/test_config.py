import pytest

from urdu_subtitles.core.config import TranscriptionConfig


def test_defaults_validate():
    TranscriptionConfig().validate()


def test_invalid_model_rejected():
    with pytest.raises(ValueError):
        TranscriptionConfig(model="huge").validate()


def test_invalid_durations_rejected():
    with pytest.raises(ValueError):
        TranscriptionConfig(min_cue_duration=5, max_cue_duration=2).validate()


def test_json_roundtrip():
    cfg = TranscriptionConfig(model="medium", task="translate", max_chars_per_line=30)
    restored = TranscriptionConfig.from_json(cfg.to_json())
    assert restored.model == "medium"
    assert restored.task == "translate"
    assert restored.max_chars_per_line == 30
