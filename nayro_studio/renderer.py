"""Frame renderer: animated gradients, Arabic-ready typography, crossfades."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from .fonts import FontBook
from .storyboard import Scene, Storyboard
from .text import has_arabic, shape, smoothstep, wrap_text
from .theme import Theme, get_theme


class Renderer:
    """Renders a :class:`Storyboard` into RGB frames on demand."""

    def __init__(self, storyboard: Storyboard) -> None:
        self.storyboard = storyboard
        self.width = storyboard.width
        self.height = storyboard.height
        self.fps = storyboard.fps
        self.scale = self.height / 720.0
        self.fonts = FontBook()

        self._starts: list[float] = []
        cursor = 0.0
        for scene in storyboard.scenes:
            self._starts.append(cursor)
            cursor += scene.duration - storyboard.transition
        self.total_duration = self._starts[-1] + storyboard.scenes[-1].duration

        ys, xs = np.mgrid[0 : self.height, 0 : self.width]
        self._x = (xs.astype(np.float32) / max(1, self.width - 1))
        self._y = (ys.astype(np.float32) / max(1, self.height - 1))
        radius = (self._x - 0.5) ** 2 + (self._y - 0.5) ** 2
        self._vignette = np.clip(1.0 - 1.35 * radius, 0.45, 1.0).astype(np.float32)[..., None]
        self._gradients: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ layout
    def scene_start(self, index: int) -> float:
        return self._starts[index]

    def _gradient(self, theme: Theme) -> np.ndarray:
        cached = self._gradients.get(theme.name)
        if cached is not None:
            return cached
        top = np.array(theme.top_rgb, dtype=np.float32)
        bottom = np.array(theme.bottom_rgb, dtype=np.float32)
        ramp = np.linspace(0.0, 1.0, self.height, dtype=np.float32)[:, None, None]
        gradient = top[None, None, :] * (1.0 - ramp) + bottom[None, None, :] * ramp
        gradient = np.broadcast_to(gradient, (self.height, self.width, 3)).astype(np.float32)
        self._gradients[theme.name] = gradient
        return gradient

    def _background(self, theme: Theme, local: float, index: int) -> Image.Image:
        frame = self._gradient(theme).copy()
        phase = index * 1.9
        for k in range(3):
            cx = 0.5 + 0.30 * math.sin(local * 0.32 + phase + k * 2.1)
            cy = 0.44 + 0.24 * math.cos(local * 0.26 + phase * 0.7 + k * 1.4)
            sigma = 0.24 + 0.06 * math.sin(local * 0.19 + k * 1.7 + phase)
            mask = np.exp(-(((self._x - cx) ** 2 + (self._y - cy) ** 2) / (2.0 * sigma * sigma)))
            colour = theme.accent_rgb if k % 2 == 0 else theme.accent_secondary_rgb
            weight = 0.42 - 0.09 * k
            frame += np.array(colour, dtype=np.float32) * mask[..., None] * weight

        frame *= self._vignette
        np.clip(frame, 0, 255, out=frame)
        return Image.fromarray(frame.astype(np.uint8), mode="RGB")

    # -------------------------------------------------------------- typography
    def _fit(
        self,
        text: str,
        weight: int,
        base_size: int,
        max_width: int,
        max_lines: int,
        arabic: bool,
    ) -> tuple[object, list[str]]:
        """Shrink the font until *text* fits in *max_lines* without truncation."""
        size = max(12, int(base_size))
        minimum = max(12, int(base_size * 0.45))
        while size >= minimum:
            font = self.fonts.get(size, weight, arabic)
            lines = wrap_text(text, font, max_width, max_lines)
            if lines and not lines[-1].endswith("…"):
                return font, lines
            size -= 2
        font = self.fonts.get(minimum, weight, arabic)
        return font, wrap_text(text, font, max_width, max_lines)

    def _draw_scene_text(
        self,
        draw: ImageDraw.ImageDraw,
        scene: Scene,
        theme: Theme,
        local: float,
    ) -> None:
        width, height, scale = self.width, self.height, self.scale
        appear = smoothstep(local / 0.55)
        leave = smoothstep((scene.duration - local) / 0.4)
        alpha = int(255 * appear * min(1.0, leave))
        if alpha <= 0:
            return

        title_arabic = has_arabic(scene.title)
        title_font, title_lines = self._fit(
            scene.title, 700, int(84 * scale), int(0.84 * width), 3, title_arabic
        )
        sub_font, sub_lines = (None, [])
        if scene.subtitle:
            sub_font, sub_lines = self._fit(
                scene.subtitle,
                400,
                int(30 * scale),
                int(0.76 * width),
                3,
                has_arabic(scene.subtitle),
            )

        title_line_h = int(title_font.size * 1.3)  # type: ignore[attr-defined]
        sub_line_h = int(sub_font.size * 1.5) if sub_font else 0  # type: ignore[attr-defined]
        ascent, descent = title_font.getmetrics()
        bar_height = max(2, int(4 * scale))
        gap = int(22 * scale)

        # Place the accent bar below the glyphs (descent included) so Arabic
        # descenders are never crossed.
        bar_offset = (len(title_lines) - 1) * title_line_h + ascent + descent + int(14 * scale)
        subtitle_offset = bar_offset + bar_height + gap
        block_height = subtitle_offset + len(sub_lines) * sub_line_h

        top = (height - block_height) / 2 + (1.0 - appear) * 26 * scale
        text_rgb = theme.text_rgb
        y = top

        for line in title_lines:
            draw.text(
                (width / 2, y),
                line,
                font=title_font,
                fill=(*text_rgb, alpha),
                anchor="ma",
            )
            y += title_line_h

        bar_width = int(76 * scale * max(0.15, appear))
        bar_y = top + bar_offset
        draw.rounded_rectangle(
            (width / 2 - bar_width / 2, bar_y, width / 2 + bar_width / 2, bar_y + bar_height),
            radius=bar_height / 2,
            fill=(*theme.accent_rgb, alpha),
        )
        y = top + subtitle_offset

        for line in sub_lines:
            draw.text(
                (width / 2, y),
                line,
                font=sub_font,
                fill=(*theme.muted_rgb, int(alpha * 0.92)),
                anchor="ma",
            )
            y += sub_line_h

    # ------------------------------------------------------------------ chrome
    def _draw_chrome(self, draw: ImageDraw.ImageDraw, scene_index: int, t: float) -> None:
        width, height, scale = self.width, self.height, self.scale
        total = self.total_duration or 1.0
        fade_in = smoothstep(t / 0.8)
        fade_out = smoothstep((total - t) / 0.6)
        alpha = int(170 * min(fade_in, fade_out))

        if self.storyboard.brand and alpha > 0:
            brand_font = self.fonts.get(max(11, int(16 * scale)), 600, False)
            draw.text(
                (width / 2, 0.075 * height),
                shape(self.storyboard.brand),
                font=brand_font,
                fill=(*get_theme(self.storyboard.theme).muted_rgb, alpha),
                anchor="ma",
            )

        accent = get_theme(
            self.storyboard.scenes[scene_index].theme or self.storyboard.theme
        ).accent_rgb
        counter_font = self.fonts.get(max(10, int(15 * scale)), 500, False)
        draw.text(
            (width - 44 * scale, height - 44 * scale),
            f"{scene_index + 1:02d} / {len(self.storyboard.scenes):02d}",
            font=counter_font,
            fill=(*accent, int(alpha * 0.9)),
            anchor="ra",
        )

        margin = 44 * scale
        track_y = height - 16 * scale
        track_h = max(2.0, 3 * scale)
        draw.rounded_rectangle(
            (margin, track_y, width - margin, track_y + track_h),
            radius=track_h / 2,
            fill=(255, 255, 255, 40),
        )
        progress = max(0.0, min(1.0, t / total))
        end = margin + (width - 2 * margin) * progress
        if end > margin:
            draw.rounded_rectangle(
                (margin, track_y, end, track_y + track_h),
                radius=track_h / 2,
                fill=(*accent, 210),
            )

    # ------------------------------------------------------------------- frames
    def _scene_image(self, index: int, local: float) -> Image.Image:
        scene = self.storyboard.scenes[index]
        theme = get_theme(scene.theme or self.storyboard.theme)
        background = self._background(theme, local, index).convert("RGBA")
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self._draw_scene_text(ImageDraw.Draw(overlay), scene, theme, local)
        return Image.alpha_composite(background, overlay).convert("RGB")

    def frame(self, index: int) -> np.ndarray:
        """Render frame number *index* as an ``(h, w, 3)`` uint8 array."""
        t = max(0.0, min(index / self.fps, self.total_duration - 1e-6))
        current = 0
        for i, start in enumerate(self._starts):
            if t >= start - 1e-9:
                current = i
        local = t - self._starts[current]
        image = self._scene_image(current, local)

        following = current + 1
        transition = self.storyboard.transition
        if following < len(self.storyboard.scenes) and transition > 0:
            next_start = self._starts[following]
            if t >= next_start:
                mix = min(1.0, (t - next_start) / transition)
                incoming = self._scene_image(following, t - next_start)
                image = Image.blend(image, incoming, mix)

        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self._draw_chrome(ImageDraw.Draw(overlay), current, t)
        composed = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        return np.asarray(composed, dtype=np.uint8)

    @property
    def frame_count(self) -> int:
        return max(1, round(self.total_duration * self.fps))

    def frames(self):
        """Yield every frame as raw RGB bytes, ready for the encoder."""
        for index in range(self.frame_count):
            yield self.frame(index).tobytes()
