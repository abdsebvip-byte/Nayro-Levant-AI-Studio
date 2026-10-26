"""Command line interface: ``nayro-video`` / ``python -m nayro_studio``."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .probe import probe_video
from .storyboard import Storyboard, storyboard_from_prompt
from .theme import THEMES, get_theme
from .tts import PROVIDERS, TTSError
from .video import generate_video
from .voice import prepare_voiceover


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nayro-video",
        description="Nayro Levant AI Studio - turn a text prompt into a branded MP4 video.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-p", "--prompt", help="text prompt (Arabic or English)")
    source.add_argument("-s", "--storyboard", help="path to a storyboard JSON file")
    source.add_argument("--list-themes", action="store_true", help="show available themes and exit")

    parser.add_argument("-o", "--out", default="output/nayro-video.mp4", help="output .mp4 path")
    parser.add_argument("--duration", type=float, default=3.0, help="seconds per scene (prompt mode)")
    parser.add_argument("--theme", default="aurora", choices=sorted(THEMES), help="colour theme")
    parser.add_argument("--width", type=int, default=1280, help="frame width in pixels")
    parser.add_argument("--height", type=int, default=720, help="frame height in pixels")
    parser.add_argument("--fps", type=int, default=24, help="frames per second")
    parser.add_argument("--brand", default=None, help="text shown at the top of every scene")
    parser.add_argument("--max-scenes", type=int, default=8, help="maximum scenes in prompt mode")
    parser.add_argument(
        "--save-storyboard",
        metavar="JSON",
        help="write the generated storyboard next to the video for editing",
    )
    parser.add_argument("--dry-run", action="store_true", help="build the storyboard only")
    parser.add_argument("-q", "--quiet", action="store_true", help="hide the progress bar")

    audio = parser.add_argument_group("voiceover")
    audio.add_argument(
        "--voice",
        action="store_true",
        help="narrate every scene with a text-to-speech voice",
    )
    audio.add_argument(
        "--tts",
        default="auto",
        choices=list(PROVIDERS),
        help="speech provider (auto tries edge then gtts)",
    )
    audio.add_argument("--lang", default="ar", help="speech language, e.g. ar or en")
    audio.add_argument("--voice-name", default=None, help="provider voice, e.g. ar-LB-LaylaNeural")
    audio.add_argument("--music", action="store_true", help="add an ambient music bed")
    audio.add_argument(
        "--music-volume",
        type=float,
        default=0.12,
        help="music level between 0 and 1 (default 0.12)",
    )
    return parser


def _storyboard(args: argparse.Namespace) -> Storyboard:
    if args.storyboard:
        return Storyboard.from_json_file(args.storyboard)
    return storyboard_from_prompt(
        args.prompt,
        scene_duration=args.duration,
        theme=args.theme,
        width=args.width,
        height=args.height,
        fps=args.fps,
        max_scenes=args.max_scenes,
        **({"brand": args.brand} if args.brand else {}),
    )


def _print_summary(path: Path) -> None:
    info = probe_video(path)
    audio = f" | {info['audio_codec']} audio" if info["has_audio"] else " | silent"
    print(f"\nVideo created: {path}")
    print(
        f"  {info['width']}x{info['height']} | {info['fps']:.0f} fps | "
        f"{info['duration']:.2f}s | {info['codec']}{audio} | "
        f"{info['size_bytes'] / 1024:.0f} KiB"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_themes:
        for name, theme in sorted(THEMES.items()):
            print(f"{name:<10} {theme.accent} on {theme.top} -> {theme.bottom}")
        return 0

    try:
        board = _storyboard(args)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover - argparse raises SystemExit

    output = Path(args.out)
    if args.save_storyboard:
        board.to_json_file(args.save_storyboard)

    if args.dry_run:
        print(f"Storyboard with {len(board.scenes)} scene(s), {board.duration:.2f}s total:")
        for index, scene in enumerate(board.scenes, start=1):
            print(f"  {index:02d}. {scene.title} [{get_theme(scene.theme or board.theme).name}]")
        return 0

    def progress(done: int, total: int) -> None:
        if args.quiet:
            return
        share = done / total
        filled = int(share * 28)
        bar = "#" * filled + "-" * (28 - filled)
        print(f"\r[{bar}] {share * 100:5.1f}% ({done}/{total} frames)", end="", flush=True)

    def narration_progress(index: int, total: int, text: str) -> None:
        if args.quiet:
            return
        excerpt = text if len(text) <= 48 else f"{text[:45]}..."
        print(f"Narration {index}/{total}: {excerpt}", flush=True)

    audio_dir: tempfile.TemporaryDirectory[str] | None = None
    soundtrack: Path | None = None
    try:
        if args.voice or args.music:
            output.parent.mkdir(parents=True, exist_ok=True)
            audio_dir = tempfile.TemporaryDirectory(
                prefix=".nayro-audio-", dir=str(output.parent)
            )
            prepared = prepare_voiceover(
                board,
                audio_dir.name,
                narrate=args.voice,
                provider=args.tts,
                lang=args.lang,
                voice=args.voice_name,
                music=args.music,
                music_volume=args.music_volume,
                progress=narration_progress,
            )
            board, soundtrack = prepared.storyboard, prepared.soundtrack
            if args.save_storyboard:
                board.to_json_file(args.save_storyboard)
            if not args.quiet:
                print(f"Audio ready: {prepared.total_duration:.2f}s total runtime")

        video = generate_video(board, output, progress=progress, audio=soundtrack)
    except TTSError as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover - argparse raises SystemExit
    finally:
        if audio_dir is not None:
            audio_dir.cleanup()

    if not args.quiet:
        print()
    _print_summary(video)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
