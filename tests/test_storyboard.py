from __future__ import annotations

import json

import pytest

from nayro_studio.storyboard import Scene, Storyboard, storyboard_from_prompt


def test_scene_rejects_empty_content() -> None:
    with pytest.raises(ValueError):
        Scene(title="   ", subtitle="")


def test_scene_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError):
        Scene(title="Hello", duration=0)


def test_storyboard_requires_scenes() -> None:
    with pytest.raises(ValueError):
        Storyboard(scenes=[])


def test_storyboard_duration_accounts_for_transitions() -> None:
    board = Storyboard(
        scenes=[Scene("One", duration=3), Scene("Two", duration=3), Scene("Three", duration=3)],
        transition=0.5,
    )
    assert board.duration == pytest.approx(8.0)
    assert board.frame_count == round(8.0 * board.fps)


def test_transition_is_clamped_to_short_scenes() -> None:
    board = Storyboard(scenes=[Scene("Short", duration=1.0)], transition=5.0)
    assert board.transition == pytest.approx(0.5)


def test_from_dict_roundtrip(tmp_path) -> None:
    payload = {
        "brand": "NAYRO",
        "width": 640,
        "height": 360,
        "fps": 30,
        "theme": "midnight",
        "transition": 0.4,
        "scenes": [
            {"title": "مرحبا", "subtitle": "أهلاً بكم", "duration": 2.5, "theme": "desert"},
            {"title": "Bye", "duration": 2.0},
        ],
    }
    board = Storyboard.from_dict(payload)
    assert board.width == 640 and board.fps == 30
    assert board.scenes[0].title == "مرحبا"
    assert board.scenes[0].theme == "desert"

    path = tmp_path / "board.json"
    board.to_json_file(path)
    reloaded = Storyboard.from_json_file(path)
    assert reloaded.to_dict() == board.to_dict()
    assert json.loads(path.read_text(encoding="utf-8"))["scenes"][0]["subtitle"] == "أهلاً بكم"


def test_from_dict_rejects_missing_scenes() -> None:
    with pytest.raises(ValueError):
        Storyboard.from_dict({"scenes": []})


def test_prompt_generates_one_scene_per_sentence() -> None:
    prompt = "استوديو نيرو ليفانت. نصنع المحتوى بالذكاء الاصطناعي. جاهز للنشر على كل المنصات."
    board = storyboard_from_prompt(prompt, scene_duration=2.0, width=640, height=360, fps=20)
    assert len(board.scenes) == 3
    assert board.scenes[0].title == "استوديو نيرو ليفانت"
    assert board.scenes[1].title
    assert "نصنع المحتوى" in board.scenes[1].title + " " + board.scenes[1].subtitle
    assert board.metadata["prompt"] == prompt
    assert board.duration == pytest.approx(2.0 * 3 - 0.6 * 2)


def test_prompt_single_sentence_keeps_full_text() -> None:
    prompt = "فيديو تعريفي قصير عن استوديو نيرو ليفانت للذكاء الاصطناعي"
    board = storyboard_from_prompt(prompt)
    assert len(board.scenes) == 1
    assert board.scenes[0].title == prompt


def test_prompt_respects_max_scenes_and_keeps_overflow() -> None:
    prompt = "أولاً. ثانياً. ثالثاً. رابعاً. خامساً."
    board = storyboard_from_prompt(prompt, max_scenes=3, scene_duration=1.0)
    assert len(board.scenes) == 3
    assert "رابعاً" in board.scenes[-1].subtitle
    assert "خامساً" in board.scenes[-1].subtitle


def test_prompt_requires_text() -> None:
    with pytest.raises(ValueError):
        storyboard_from_prompt("   ")


def test_prompt_rejects_invalid_max_scenes() -> None:
    with pytest.raises(ValueError):
        storyboard_from_prompt("Hello", max_scenes=0)
