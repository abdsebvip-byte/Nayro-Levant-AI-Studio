from __future__ import annotations

import numpy as np
import pytest

from nayro_studio.cli import main
from nayro_studio.probe import probe_video
from nayro_studio.renderer import Renderer
from nayro_studio.storyboard import Scene, Storyboard
from nayro_studio.video import generate_video


def tiny_board() -> Storyboard:
    return Storyboard(
        scenes=[
            Scene("NAYRO LEVANT", "AI Content Studio", duration=1.0, theme="aurora"),
            Scene("مرحبا بكم", "نصنع المحتوى بالذكاء الاصطناعي", duration=1.0, theme="midnight"),
        ],
        width=256,
        height=144,
        fps=10,
        transition=0.4,
    )


def test_frame_shape_and_content() -> None:
    renderer = Renderer(tiny_board())
    frame = renderer.frame(6)
    assert frame.shape == (144, 256, 3)
    assert frame.dtype == np.uint8
    # Not a flat image: the animated gradient and text produce variance.
    assert float(frame.std()) > 3.0
    assert float(frame.max()) > 200


def test_arabic_scene_renders_bright_glyphs() -> None:
    board = Storyboard(
        scenes=[Scene("استوديو نيرو ليفانت", "نصنع المحتوى بالذكاء الاصطناعي", duration=1.0)],
        width=320,
        height=180,
        fps=10,
        transition=0.0,
    )
    frame = Renderer(board).frame(5)
    bright = int((frame.mean(axis=2) > 200).sum())
    assert bright > 200, "Arabic text should be drawn as bright pixels"


def test_frame_count_matches_duration() -> None:
    renderer = Renderer(tiny_board())
    assert renderer.frame_count == round(1.6 * 10)


def test_generate_video_end_to_end(tmp_path) -> None:
    output = tmp_path / "nested" / "video.mp4"
    progress: list[tuple[int, int]] = []
    generate_video(tiny_board(), output, progress=lambda done, total: progress.append((done, total)))

    assert output.is_file() and output.stat().st_size > 1000
    info = probe_video(output)
    assert info["codec"] == "h264"
    assert (info["width"], info["height"]) == (256, 144)
    assert info["fps"] == pytest.approx(10.0)
    assert info["duration"] == pytest.approx(1.6, abs=0.15)
    assert info["has_audio"] is False
    assert info["audio_codec"] is None
    assert progress and progress[-1] == (16, 16)


def test_generate_video_with_audio(tmp_path) -> None:
    from nayro_studio.audio import SAMPLE_RATE, load_audio, write_wav

    time = np.arange(int(1.6 * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    tone = 0.4 * np.sin(2.0 * np.pi * 330.0 * time)
    narration = write_wav(tone.astype(np.float32), tmp_path / "voice.wav")

    output = tmp_path / "voiced.mp4"
    generate_video(tiny_board(), output, audio=narration)

    info = probe_video(output)
    assert info["has_audio"] is True
    assert info["audio_codec"] == "aac"
    decoded = load_audio(output)
    assert float(np.abs(decoded).max()) > 0.2
    assert decoded.size / SAMPLE_RATE == pytest.approx(1.6, abs=0.2)


def test_cli_renders_from_prompt(tmp_path, capsys) -> None:
    output = tmp_path / "prompt.mp4"
    code = main(
        [
            "--prompt",
            "استوديو نيرو ليفانت. فيديو جاهز للنشر.",
            "--duration",
            "0.8",
            "--width",
            "256",
            "--height",
            "144",
            "--fps",
            "10",
            "--out",
            str(output),
            "--quiet",
        ]
    )
    assert code == 0
    assert output.is_file()
    captured = capsys.readouterr().out
    assert "Video created" in captured
    assert probe_video(output)["duration"] == pytest.approx(1.2, abs=0.15)


def test_cli_with_voiceover_and_music(tmp_path, monkeypatch) -> None:
    import nayro_studio.voice as voice_module
    from nayro_studio.audio import SAMPLE_RATE, load_audio, write_wav

    def fake_synth(text, output, *, provider="auto", lang="ar", voice=None):
        time = np.arange(int(0.3 * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
        samples = (0.4 * np.sin(2.0 * np.pi * 440.0 * time)).astype(np.float32)
        return write_wav(samples, f"{output}.wav")

    monkeypatch.setattr(voice_module, "synthesize_speech", fake_synth)

    output = tmp_path / "voiced.mp4"
    code = main(
        [
            "--prompt",
            "جملة أولى للتعليق. جملة ثانية للتعليق.",
            "--duration",
            "0.6",
            "--width",
            "256",
            "--height",
            "144",
            "--fps",
            "10",
            "--voice",
            "--music",
            "--out",
            str(output),
            "--quiet",
        ]
    )
    assert code == 0
    info = probe_video(output)
    assert info["has_audio"] is True
    assert info["audio_codec"] == "aac"
    assert info["duration"] > 1.5
    assert float(np.abs(load_audio(output)).max()) > 0.1


def test_cli_dry_run(tmp_path) -> None:
    board_path = tmp_path / "board.json"
    code = main(
        [
            "--prompt",
            "First sentence. Second sentence.",
            "--dry-run",
            "--save-storyboard",
            str(board_path),
        ]
    )
    assert code == 0
    assert board_path.is_file()
    assert len(board_path.read_text(encoding="utf-8")) > 50


def test_cli_list_themes(capsys) -> None:
    assert main(["--list-themes"]) == 0
    out = capsys.readouterr().out
    for name in ("aurora", "midnight", "sunrise", "desert"):
        assert name in out


def test_cli_rejects_unknown_theme() -> None:
    with pytest.raises(SystemExit):
        main(["--prompt", "Hello", "--theme", "neon"])
