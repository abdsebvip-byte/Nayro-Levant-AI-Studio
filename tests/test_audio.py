from __future__ import annotations

import numpy as np
import pytest

from nayro_studio.audio import (
    SAMPLE_RATE,
    AudioError,
    ambient_music,
    audio_duration,
    build_soundtrack,
    load_audio,
    mix_clips,
    write_wav,
)


def tone(seconds: float, frequency: float = 440.0, amplitude: float = 0.5) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    return (amplitude * np.sin(2.0 * np.pi * frequency * time)).astype(np.float32)


def test_write_and_load_roundtrip(tmp_path) -> None:
    samples = tone(1.0)
    path = write_wav(samples, tmp_path / "tone.wav")
    loaded = load_audio(path)
    assert loaded.size == pytest.approx(samples.size, abs=2)
    assert audio_duration(path) == pytest.approx(1.0, abs=0.01)
    assert float(np.abs(loaded).max()) == pytest.approx(0.5, abs=0.02)


def test_load_audio_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(AudioError):
        load_audio(tmp_path / "missing.wav")


def test_mix_clips_places_audio_at_offsets() -> None:
    track = mix_clips([(tone(0.5), 1.0)], 2.0)
    assert track.size == 2 * SAMPLE_RATE
    assert float(np.abs(track[: SAMPLE_RATE]).max()) < 1e-6
    assert float(np.abs(track[SAMPLE_RATE + 100 : SAMPLE_RATE + 10000]).max()) > 0.2
    assert float(np.abs(track[-SAMPLE_RATE // 2 :]).max()) < 1e-6


def test_mix_clips_ignores_out_of_range() -> None:
    track = mix_clips([(tone(2.0), 5.0)], 1.0)
    assert float(np.abs(track).max()) == 0.0


def test_ambient_music_length_and_headroom() -> None:
    music = ambient_music(3.0)
    assert music.size == 3 * SAMPLE_RATE
    assert np.isfinite(music).all()
    assert float(np.abs(music).max()) == pytest.approx(1.0, abs=0.01)
    # Fades in: the very first samples are near silent.
    assert abs(float(music[0])) < 0.01


def test_build_soundtrack_with_music(tmp_path) -> None:
    path = build_soundtrack([(tone(0.5), 0.25)], 2.0, tmp_path / "mix.wav", music=True)
    mixed = load_audio(path)
    assert mixed.size == 2 * SAMPLE_RATE
    assert float(np.abs(mixed).max()) > 0.2
    assert float(np.abs(mixed).max()) <= 0.99


def test_build_soundtrack_is_limited(tmp_path) -> None:
    loud = tone(1.0, amplitude=1.0)
    path = build_soundtrack([(loud, 0.0)], 1.0, tmp_path / "loud.wav", music=True)
    mixed = load_audio(path)
    assert float(np.abs(mixed).max()) <= 0.99
