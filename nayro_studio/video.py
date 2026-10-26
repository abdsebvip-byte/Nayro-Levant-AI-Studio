"""MP4/H.264 encoding through the ffmpeg binary bundled with imageio-ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Iterable

import imageio_ffmpeg

from .renderer import Renderer
from .storyboard import Storyboard

ProgressCallback = Callable[[int, int], None]


class VideoEncodingError(RuntimeError):
    """Raised when ffmpeg rejects a render."""


def ffmpeg_path() -> str:
    """Absolute path of the ffmpeg executable used for encoding."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode_frames(
    frames: Iterable[bytes],
    output: str | Path,
    *,
    width: int,
    height: int,
    fps: int,
    crf: int = 20,
    preset: str = "medium",
) -> Path:
    """Pipe raw RGB frames into ffmpeg and write an H.264 MP4 file."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None and process.stderr is not None

    written = 0
    try:
        for frame in frames:
            process.stdin.write(frame)
            written += 1
        process.stdin.close()
    except BrokenPipeError:
        pass

    stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
    return_code = process.wait()
    if return_code != 0 or not output.is_file():
        raise VideoEncodingError(
            f"ffmpeg exited with code {return_code}: {stderr or 'no output'}"
        )
    if written == 0:
        raise VideoEncodingError("no frames were rendered")
    return output


def generate_video(
    storyboard: Storyboard,
    output: str | Path,
    *,
    progress: ProgressCallback | None = None,
) -> Path:
    """Render *storyboard* and encode it to *output*; returns the output path."""
    renderer = Renderer(storyboard)
    total = renderer.frame_count

    def frames():
        for index in range(total):
            yield renderer.frame(index).tobytes()
            if progress is not None:
                progress(index + 1, total)

    return encode_frames(
        frames(),
        output,
        width=storyboard.width,
        height=storyboard.height,
        fps=storyboard.fps,
    )
