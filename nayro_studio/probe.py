"""Read basic stream information out of a rendered video (via ffmpeg)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .video import ffmpeg_path

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Video:\s*([\w-]+).*?,\s*(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")


def probe_video(path: str | Path) -> dict[str, object]:
    """Return codec, width, height, fps and duration for *path*.

    ffprobe is not bundled with imageio-ffmpeg, so the metadata is parsed from
    ffmpeg's own banner output.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    result = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    banner = result.stderr

    duration_match = _DURATION_RE.search(banner)
    video_match = _VIDEO_RE.search(banner)
    if duration_match is None or video_match is None:
        raise ValueError(f"unable to read video metadata from {path}")

    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    fps_match = _FPS_RE.search(banner)

    return {
        "codec": video_match.group(1),
        "width": int(video_match.group(2)),
        "height": int(video_match.group(3)),
        "fps": float(fps_match.group(1)) if fps_match else None,
        "duration": round(duration, 3),
        "size_bytes": path.stat().st_size,
    }
