"""Voiceover pipeline: synthesize narration, retime scenes, build soundtrack."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio import SAMPLE_RATE, build_soundtrack, load_audio
from .storyboard import Scene, Storyboard
from .tts import DEFAULT_LANG, synthesize_speech

LEAD_IN = 0.35
TAIL = 0.25

Synthesizer = Callable[..., Path]
ProgressHook = Callable[[int, int, str], None]


@dataclass
class Voiceover:
    """Result of preparing narration: retimed storyboard plus a mixed WAV."""

    storyboard: Storyboard
    soundtrack: Path

    @property
    def total_duration(self) -> float:
        return self.storyboard.duration


def prepare_voiceover(
    storyboard: Storyboard,
    workdir: str | Path,
    *,
    narrate: bool = True,
    provider: str = "auto",
    lang: str = DEFAULT_LANG,
    voice: str | None = None,
    music: bool = False,
    music_volume: float = 0.12,
    synthesizer: Synthesizer | None = None,
    progress: ProgressHook | None = None,
) -> Voiceover:
    """Synthesize each scene's script, extend scenes to fit it, mix the track.

    Narration starts ``LEAD_IN`` seconds into a scene and always finishes
    before the next scene begins, so two voices never overlap.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    synth = synthesizer or synthesize_speech

    clips: list[np.ndarray] = []
    if narrate:
        total_scenes = len(storyboard.scenes)
        for index, scene in enumerate(storyboard.scenes):
            text = scene.spoken_text
            if progress is not None:
                progress(index + 1, total_scenes, text)
            clip_path = workdir / f"scene-{index + 1:02d}.mp3"
            created = synth(text, clip_path, provider=provider, lang=lang, voice=voice)
            clips.append(load_audio(created))
    else:
        clips = []

    transition = storyboard.transition
    durations: list[float] = []
    for index, scene in enumerate(storyboard.scenes):
        duration = scene.duration
        if index < len(clips):
            speech = clips[index].size / float(SAMPLE_RATE)
            required = LEAD_IN + speech + transition + TAIL
            duration = max(duration, round(required, 2))
        durations.append(duration)

    retimed = Storyboard(
        scenes=[
            Scene(
                title=scene.title,
                subtitle=scene.subtitle,
                duration=duration,
                theme=scene.theme,
                narration=scene.narration,
            )
            for scene, duration in zip(storyboard.scenes, durations)
        ],
        brand=storyboard.brand,
        width=storyboard.width,
        height=storyboard.height,
        fps=storyboard.fps,
        theme=storyboard.theme,
        transition=transition,
        metadata=dict(storyboard.metadata),
    )

    starts: list[float] = []
    cursor = 0.0
    for scene in retimed.scenes:
        starts.append(cursor)
        cursor += scene.duration - retimed.transition

    placed = [
        (clip, starts[index] + LEAD_IN)
        for index, clip in enumerate(clips)
    ]
    soundtrack = build_soundtrack(
        placed,
        retimed.duration,
        workdir / "soundtrack.wav",
        music=music,
        music_volume=music_volume,
    )
    return Voiceover(storyboard=retimed, soundtrack=soundtrack)
