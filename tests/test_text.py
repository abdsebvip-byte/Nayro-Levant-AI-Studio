from __future__ import annotations

import pytest

from nayro_studio.fonts import FontBook
from nayro_studio.text import has_arabic, is_rtl, shape, smoothstep, wrap_text


@pytest.fixture(scope="module")
def fonts() -> FontBook:
    return FontBook()


def test_has_arabic_detects_scripts() -> None:
    assert has_arabic("مرحبا")
    assert has_arabic("Nayro ليفانت")
    assert not has_arabic("Nayro Levant AI Studio")
    assert not has_arabic("")


def test_shape_joins_arabic_letters() -> None:
    raw = "مرحبا بكم"
    shaped = shape(raw)
    assert shaped != raw
    # Arabic presentation forms prove the letters were joined for Pillow.
    assert any("\ufe70" <= char <= "\ufeff" for char in shaped)


def test_shape_leaves_latin_untouched() -> None:
    assert shape("Nayro Levant") == "Nayro Levant"


def test_is_rtl() -> None:
    assert is_rtl("مرحبا Nayro")
    assert not is_rtl("Nayro مرحبا")
    assert not is_rtl("123")


def test_wrap_text_respects_width_and_line_limit(fonts: FontBook) -> None:
    font = fonts.get(32)
    text = "Nayro Levant AI Studio turns a short prompt into a finished video for every platform"
    lines = wrap_text(text, font, 240, max_lines=4)
    assert 1 <= len(lines) <= 4
    assert all(font.getlength(line) <= 240 for line in lines)


def test_wrap_text_truncates_with_ellipsis(fonts: FontBook) -> None:
    font = fonts.get(32)
    text = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    lines = wrap_text(text, font, 120, max_lines=2)
    assert len(lines) == 2
    assert lines[-1].endswith("…")


def test_wrap_text_handles_arabic(fonts: FontBook) -> None:
    font = fonts.get(30, arabic=True)
    lines = wrap_text("استوديو نيرو ليفانت يصنع المحتوى بالذكاء الاصطناعي", font, 220, max_lines=3)
    assert lines
    assert all(any("\ufe70" <= char <= "\ufeff" for char in line) for line in lines)


def test_wrap_text_empty(fonts: FontBook) -> None:
    assert wrap_text("", fonts.get(20), 100) == []


def test_smoothstep_bounds() -> None:
    assert smoothstep(-1) == 0.0
    assert smoothstep(0) == 0.0
    assert smoothstep(1) == 1.0
    assert smoothstep(2) == 1.0
    assert 0.0 < smoothstep(0.5) < 1.0
