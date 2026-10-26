"""Text helpers: Arabic shaping, direction detection and word wrapping."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import arabic_reshaper
from bidi.algorithm import get_display

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import ImageFont

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def has_arabic(text: str) -> bool:
    """Return True when *text* contains at least one Arabic-script character."""
    return bool(_ARABIC_RE.search(text))


def shape(text: str) -> str:
    """Return *text* ready for Pillow rendering without a shaping engine.

    Pillow in this environment is built without Raqm, so Arabic letters must be
    joined (``arabic_reshaper``) and reordered right-to-left (``python-bidi``)
    before they are drawn. Latin-only text is returned unchanged.
    """
    if not text or not has_arabic(text):
        return text
    return get_display(arabic_reshaper.reshape(text))


def is_rtl(text: str) -> bool:
    """True when the first strong character of *text* is right-to-left."""
    for char in text:
        if _ARABIC_RE.match(char):
            return True
        if char.isalpha():
            return False
    return False


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int = 3,
) -> list[str]:
    """Wrap *text* into at most *max_lines* lines that fit *max_width*.

    Wrapping happens on the logical (unshaped) text so words stay whole; every
    returned line is already shaped and safe to hand to ``ImageDraw.text``.
    """
    text = " ".join((text or "").split())
    if not text:
        return []

    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if current and font.getlength(shape(candidate)) > max_width:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
        else:
            current = candidate
    else:
        if current:
            lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if not lines:
        return []

    # Trim the last line with an ellipsis when the text was cut short.
    consumed = " ".join(lines)
    if len(consumed) < len(text):
        last = lines[-1]
        while last and font.getlength(shape(last + "…")) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = f"{last}…"

    return [shape(line) for line in lines]


def smoothstep(value: float) -> float:
    """Clamp *value* to [0, 1] and ease it in/out."""
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)
