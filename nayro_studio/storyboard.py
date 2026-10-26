"""Storyboard model and prompt-to-scenes generator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_BRAND = "NAYRO LEVANT · AI STUDIO"
DEFAULT_THEME = "aurora"
MAX_SCENES = 8

_SENTENCE_RE = re.compile(r"[^.!?؟…\n]+[.!?؟…]*")


@dataclass
class Scene:
    """A single card in the video."""

    title: str
    subtitle: str = ""
    duration: float = 3.0
    theme: str | None = None

    def __post_init__(self) -> None:
        self.title = " ".join(str(self.title).split())
        self.subtitle = " ".join(str(self.subtitle).split())
        if not self.title and not self.subtitle:
            raise ValueError("a scene needs a title or a subtitle")
        if self.duration <= 0:
            raise ValueError("scene duration must be positive")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"title": self.title, "duration": self.duration}
        if self.subtitle:
            data["subtitle"] = self.subtitle
        if self.theme:
            data["theme"] = self.theme
        return data


@dataclass
class Storyboard:
    """A complete video description."""

    scenes: list[Scene]
    brand: str = DEFAULT_BRAND
    width: int = 1280
    height: int = 720
    fps: int = 24
    theme: str = DEFAULT_THEME
    transition: float = 0.6
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenes:
            raise ValueError("a storyboard needs at least one scene")
        if self.width < 64 or self.height < 64:
            raise ValueError("video dimensions must be at least 64x64")
        if not 1 <= self.fps <= 120:
            raise ValueError("fps must be between 1 and 120")
        shortest = min(scene.duration for scene in self.scenes)
        self.transition = max(0.0, min(self.transition, shortest / 2))

    @property
    def duration(self) -> float:
        """Total length in seconds, accounting for overlapping crossfades."""
        total = sum(scene.duration for scene in self.scenes)
        return total - self.transition * (len(self.scenes) - 1)

    @property
    def frame_count(self) -> int:
        return max(1, int(round(self.duration * self.fps)))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Storyboard":
        if not isinstance(data, dict):
            raise TypeError("storyboard JSON must be an object")
        scenes_data = data.get("scenes")
        if not scenes_data:
            raise ValueError("storyboard JSON must contain a non-empty 'scenes' list")
        scenes = [
            Scene(
                title=item.get("title", ""),
                subtitle=item.get("subtitle", ""),
                duration=float(item.get("duration", 3.0)),
                theme=item.get("theme"),
            )
            for item in scenes_data
        ]
        return cls(
            scenes=scenes,
            brand=str(data.get("brand", DEFAULT_BRAND)),
            width=int(data.get("width", 1280)),
            height=int(data.get("height", 720)),
            fps=int(data.get("fps", 24)),
            theme=str(data.get("theme", DEFAULT_THEME)),
            transition=float(data.get("transition", 0.6)),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Storyboard":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "brand": self.brand,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "theme": self.theme,
            "transition": round(self.transition, 3),
            "scenes": [scene.to_dict() for scene in self.scenes],
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _split_sentences(prompt: str) -> list[str]:
    sentences = []
    for match in _SENTENCE_RE.finditer(prompt):
        sentence = " ".join(match.group(0).split())
        if sentence:
            sentences.append(sentence)
    return sentences


def _split_headline(sentence: str, max_words: int = 6, max_chars: int = 44) -> tuple[str, str]:
    """Split a sentence into a short headline plus the remaining text."""
    words = sentence.split()
    headline_words: list[str] = []
    for word in words:
        candidate = " ".join(headline_words + [word])
        if headline_words and (len(headline_words) >= max_words or len(candidate) > max_chars):
            break
        headline_words.append(word)
    headline = " ".join(headline_words).rstrip(".,،;؛:!?؟…")
    remainder = " ".join(words[len(headline_words):]).strip()
    return headline, remainder


def storyboard_from_prompt(
    prompt: str,
    *,
    scene_duration: float = 3.0,
    theme: str = DEFAULT_THEME,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    brand: str = DEFAULT_BRAND,
    max_scenes: int = MAX_SCENES,
) -> Storyboard:
    """Turn a free-form prompt (Arabic or English) into a storyboard.

    The opening card carries the first sentence as its title; every following
    sentence becomes a card with a short headline and the rest as subtitle.
    """
    prompt = " ".join((prompt or "").split())
    if not prompt:
        raise ValueError("prompt must not be empty")
    if max_scenes < 1:
        raise ValueError("max_scenes must be at least 1")

    sentences = _split_sentences(prompt) or [prompt]
    title, _ = _split_headline(sentences[0], max_words=10, max_chars=70)
    scenes = [Scene(title=title, duration=scene_duration)]

    for sentence in sentences[1:max_scenes]:
        headline, remainder = _split_headline(sentence)
        scenes.append(Scene(title=headline, subtitle=remainder, duration=scene_duration))

    if len(scenes) == 1:
        # Keep the full prompt readable on a single card.
        scenes[0] = Scene(title=prompt, duration=scene_duration)

    if len(sentences) > max_scenes:
        # Make the truncation explicit instead of silently dropping content.
        overflow = " ".join(sentences[max_scenes - 1:])
        scenes[-1].subtitle = " ".join(filter(None, [scenes[-1].subtitle, overflow]))

    return Storyboard(
        scenes=scenes,
        brand=brand,
        width=width,
        height=height,
        fps=fps,
        theme=theme,
        metadata={"prompt": prompt},
    )
