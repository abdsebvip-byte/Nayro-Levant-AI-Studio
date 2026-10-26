"""Font discovery and loading (bundled Noto fonts, optional env overrides)."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFont

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
DEFAULT_ARABIC_FONT = ASSET_DIR / "NotoKufiArabic.ttf"
DEFAULT_LATIN_FONT = ASSET_DIR / "NotoSans.ttf"


def _env_path(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    if value and Path(value).is_file():
        return Path(value)
    return fallback


class FontBook:
    """Cached Pillow font loader with weight support for variable fonts."""

    def __init__(self) -> None:
        self._latin_path = _env_path("NAYRO_FONT_LATIN", DEFAULT_LATIN_FONT)
        self._arabic_path = _env_path("NAYRO_FONT_AR", DEFAULT_ARABIC_FONT)
        self._cache: dict[tuple[bool, int, int], ImageFont.FreeTypeFont] = {}
        for path in (self._latin_path, self._arabic_path):
            if not path.is_file():
                raise FileNotFoundError(f"font file not found: {path}")

    def get(self, size: int, weight: int = 400, arabic: bool = False) -> ImageFont.FreeTypeFont:
        size = max(8, int(size))
        weight = max(100, min(900, int(round(weight / 100.0) * 100)))
        key = (arabic, size, weight)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        path = self._arabic_path if arabic else self._latin_path
        font = ImageFont.truetype(str(path), size)
        if weight != 400:
            axes = [weight] if arabic else [100, weight]
            try:
                font.set_variation_by_axes(axes)
            except (OSError, ValueError):  # static font or unexpected axes
                pass
        self._cache[key] = font
        return font
