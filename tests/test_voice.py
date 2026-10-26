from __future__ import annotations

import numpy as np
import pytest

from nayro_studio.audio import SAMPLE_RATE, load_audio, write_wav
from nayro_studio.storyboard import Scene, Storyboard
from nayro_studio.voice import LEAD_IN, prepare_voiceover


def fake_voice(duration: float = 0.6):
    calls: list[dict[str, object]] = []

    def synthesize(text, output, *, provider="auto", lang="ar", voice=None):
        calls.append(
            {"text": text, "provider": provider, "lang": lang, "voice": voice}
        )
        samples = np.zeros(int(duration * SAMPLE_RATE), dtype=np.float32)
        time = np.arange(samples.size, dtype=np.float32) / SAMPLE_RATE
        samples[:] = 0.4 * np.sin(2.0 * np.pi * 440.0 * time)
        return write_wav(samples, str(output) + ".wav")

    synthesize.calls = calls  # type: ignore[attr-defined]
    return synthesize


def board() -> Storyboard:
    return Storyboard(
        scenes=[
            Scene("Scene one", "First line", duration=1.0),
            Scene("Scene two", duration=1.0, narration="نص عربي للتعليق"),
        ],
        width=256,
        height=144,
        fps=10,
        transition=0.3,
    )


def test_voiceover_extends_scenes_and_places_narration(tmp_path) -> None:
    synth = fake_voice(0.6)
    result = prepare_voiceover(board(), tmp_path, synthesizer=synth)

    assert len(synth.calls) == 2  # type: ignore[attr-defined]
    assert synth.calls[0]["text"] == "Scene one First line"  # type: ignore[attr-defined]
    assert synth.calls[1]["text"] == "نص عربي للتعليق"  # type: ignore[attr-defined]
    assert synth.calls[0]["provider"] == "auto"  # type: ignore[attr-defined]

    for scene in result.storyboard.scenes:
        assert scene.duration == pytest.approx(LEAD_IN + 0.6 + 0.3 + 0.25)
    assert result.total_duration > board().duration

    audio = load_audio(result.soundtrack)
    assert audio.size == round(result.total_duration * SAMPLE_RATE)
    starts = [0.0, result.storyboard.scenes[0].duration - result.storyboard.transition]
    for start in starts:
        offset = int((start + LEAD_IN) * SAMPLE_RATE)
        window = audio[offset : offset + int(0.2 * SAMPLE_RATE)]
        assert float(np.abs(window).max()) > 0.2, "narration was not mixed at scene start"


def test_voiceover_never_overlaps_next_scene(tmp_path) -> None:
    result = prepare_voiceover(board(), tmp_path, synthesizer=fake_voice(0.6))
    audio = load_audio(result.soundtrack)
    next_start = result.storyboard.scenes[0].duration - result.storyboard.transition
    gap_start = int((next_start - 0.1) * SAMPLE_RATE)
    gap_end = int(next_start * SAMPLE_RATE)
    assert float(np.abs(audio[gap_start:gap_end]).max()) < 0.05


def test_voiceover_preserves_narration(tmp_path) -> None:
    result = prepare_voiceover(board(), tmp_path, synthesizer=fake_voice(0.3))
    assert result.storyboard.scenes[1].narration == "نص عربي للتعليق"
    assert result.storyboard.scenes[0].spoken_text == "Scene one First line"


def test_voiceover_music_only_keeps_timing(tmp_path) -> None:
    original = board()
    result = prepare_voiceover(original, tmp_path, narrate=False, music=True)
    assert [scene.duration for scene in result.storyboard.scenes] == [
        scene.duration for scene in original.scenes
    ]
    audio = load_audio(result.soundtrack)
    assert float(np.abs(audio).max()) > 0.3


def test_voiceover_retimes_with_music(tmp_path) -> None:
    result = prepare_voiceover(
        board(), tmp_path, synthesizer=fake_voice(0.4), music=True, music_volume=0.1
    )
    audio = load_audio(result.soundtrack)
    assert float(np.abs(audio).max()) <= 0.99
    assert float(np.abs(audio).max()) > 0.2
