from __future__ import annotations

import os
from pathlib import Path

import pytest

from nayro_studio import tts
from nayro_studio.audio import SAMPLE_RATE, audio_duration, write_wav
from nayro_studio.tts import (
    TTSError,
    available_providers,
    default_voice,
    synthesize_speech,
)


def test_default_voice_for_languages() -> None:
    assert default_voice("ar") == "ar-LB-LaylaNeural"
    assert default_voice("ar-SA") == "ar-LB-LaylaNeural"
    assert default_voice("en") == "en-US-AriaNeural"
    assert default_voice("fr").startswith("en-")


def test_available_providers_are_known() -> None:
    assert set(available_providers()) <= {"edge", "gtts"}


def test_synthesize_rejects_empty_text(tmp_path) -> None:
    with pytest.raises(TTSError):
        synthesize_speech("   ", tmp_path / "out.mp3")


def test_synthesize_rejects_unknown_provider(tmp_path) -> None:
    with pytest.raises(TTSError):
        synthesize_speech("hello", tmp_path / "out.mp3", provider="nope")


def test_auto_falls_back_to_second_provider(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    def broken(text, output, lang, voice):
        calls.append("edge")
        raise RuntimeError("offline")

    def works(text, output, lang, voice):
        calls.append("gtts")
        Path(output).write_bytes(b"fake-mp3")

    monkeypatch.setitem(tts._PROVIDER_FUNCS, "edge", broken)
    monkeypatch.setitem(tts._PROVIDER_FUNCS, "gtts", works)

    result = synthesize_speech("مرحبا", tmp_path / "voice.mp3")
    assert result.is_file()
    assert calls == ["edge", "gtts"]


def test_provider_error_is_reported(tmp_path, monkeypatch) -> None:
    def broken(text, output, lang, voice):
        raise RuntimeError("network down")

    monkeypatch.setitem(tts._PROVIDER_FUNCS, "edge", broken)
    with pytest.raises(TTSError) as excinfo:
        synthesize_speech("hello", tmp_path / "voice.mp3", provider="edge")
    assert "network down" in str(excinfo.value)


@pytest.mark.skipif(
    os.environ.get("NAYRO_NETWORK_TESTS") != "1",
    reason="set NAYRO_NETWORK_TESTS=1 to exercise the live speech providers",
)
def test_live_arabic_speech(tmp_path) -> None:
    output = synthesize_speech(
        "مرحباً بكم في استوديو نيرو ليفانت.",
        tmp_path / "live.mp3",
        lang="ar",
    )
    assert output.stat().st_size > 1000
    assert audio_duration(output) > 1.0


def test_wav_is_accepted_by_the_pipeline(tmp_path) -> None:
    from nayro_studio.audio import ambient_music

    path = write_wav(ambient_music(1.0), tmp_path / "music.wav", SAMPLE_RATE)
    assert audio_duration(path) == pytest.approx(1.0, abs=0.01)
