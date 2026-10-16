import wave
from pathlib import Path

import pytest

from audio_engines.sensevoice_engine import SenseVoiceEngine


@pytest.fixture
def engine():
    return object.__new__(SenseVoiceEngine)


def test_audio_tags_are_metadata_and_all_results_are_preserved(engine, monkeypatch):
    monkeypatch.setattr(engine, "_audio_duration", lambda _: 7.5)
    parsed = engine._parse_result(
        [{"text": "<|en|><|HAPPY|><|Speech|><|withitn|>Hello."}, {"text": "<|zh|><|NEUTRAL|>你好。"}],
        Path("sample.wav"),
    )
    assert parsed["transcript"] == "Hello.\n你好。"
    assert "<|HAPPY|>" in parsed["raw_transcript"]
    assert parsed["metadata"]["language"] == "mixed"
    assert parsed["metadata"]["duration"] == 7.5
    assert parsed["metadata"]["emotion_enabled"] is True
    assert parsed["metadata"]["timestamps_available"] is False
    assert parsed["segments"][0]["emotion"] == "happy"


def test_audio_word_timestamps_use_model_words(engine, monkeypatch):
    monkeypatch.setattr(engine, "_audio_duration", lambda _: 0)
    parsed = engine._parse_result(
        [{"text": "<|zh|>你好世界", "timestamp": [[100, 300], [350, 800]], "words": ["你好", "世界"]}],
        Path("sample.wav"),
    )
    assert [segment["text"] for segment in parsed["segments"]] == ["你好", "世界"]
    assert parsed["segments"][1]["start"] == 0.35
    assert parsed["metadata"]["duration"] == 0.8
    assert parsed["metadata"]["timestamps_available"] is True


def test_audio_missing_word_alignment_preserves_entire_chinese_text(engine, monkeypatch):
    monkeypatch.setattr(engine, "_audio_duration", lambda _: 0)
    parsed = engine._parse_result(
        [{"text": "完整的中文句子", "timestamp": [[0, 100], [100, 400]], "language": "zh", "emotion": "neutral"}],
        Path("sample.wav"),
    )
    assert parsed["segments"] == [
        {"start": 0, "end": 0.4, "text": "完整的中文句子", "language": "zh", "emotion": "neutral"}
    ]


def test_audio_duration_reads_actual_wave_header(engine, tmp_path):
    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 32000)
    assert engine._audio_duration(path) == pytest.approx(2)
    parsed = engine._parse_result([], path)
    assert parsed["metadata"]["duration"] == pytest.approx(2)
    assert parsed["metadata"]["speaker_count"] == 0
    assert parsed["segments"] == []


def test_audio_invalid_timestamps_do_not_drop_transcript(engine, monkeypatch):
    monkeypatch.setattr(engine, "_audio_duration", lambda _: 3)
    parsed = engine._parse_result(
        [{"text": "still readable", "timestamp": [[-1, 20], [float("nan"), 40]], "words": ["still", "readable"]}],
        Path("sample.wav"),
    )
    assert parsed["segments"][0]["text"] == "still readable"
    assert parsed["metadata"]["timestamps_available"] is False
