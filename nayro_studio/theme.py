"""Colour themes used by the renderer."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageColor


@dataclass(frozen=True)
class Theme:
    name: str
    top: str
    bottom: str
    accent: str
    accent_secondary: str
    text: str = "#F7F8FC"
    muted: str = "#C3C8DA"

    @property
    def top_rgb(self) -> tuple[int, int, int]:
        return ImageColor.getrgb(self.top)

    @property
    def bottom_rgb(self) -> tuple[int, int, int]:
        return ImageColor.getrgb(self.bottom)

    @property
    def accent_rgb(self) -> tuple[int, int, int]:
        return ImageColor.getrgb(self.accent)

    @property
    def accent_secondary_rgb(self) -> tuple[int, int, int]:
        return ImageColor.getrgb(self.accent_secondary)

    @property
    def text_rgb(self) -> tuple[int, int, int]:
        return ImageColor.getrgb(self.text)

    @property
    def muted_rgb(self) -> tuple[int, int, int]:
        return ImageColor.getrgb(self.muted)


THEMES: dict[str, Theme] = {
    "aurora": Theme(
        name="aurora",
        top="#061726",
        bottom="#0B2C3D",
        accent="#35E0C4",
        accent_secondary="#4C7DFF",
    ),
    "midnight": Theme(
        name="midnight",
        top="#0B0B1E",
        bottom="#1B1440",
        accent="#8B5CF6",
        accent_secondary="#F472B6",
    ),
    "sunrise": Theme(
        name="sunrise",
        top="#2A1030",
        bottom="#5B2131",
        accent="#FF9A5A",
        accent_secondary="#FFD166",
    ),
    "desert": Theme(
        name="desert",
        top="#1A140C",
        bottom="#3A2A16",
        accent="#E2B15B",
        accent_secondary="#C97B4A",
    ),
}


def get_theme(name: str) -> Theme:
    """Return a theme by name, falling back to the default one."""
    return THEMES.get((name or "").lower(), THEMES["aurora"])
