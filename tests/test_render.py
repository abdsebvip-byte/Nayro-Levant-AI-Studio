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
    assert progress and progress[-1] == (16, 16)


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
