"""Audio helpers: decode, place voiceover clips, synthesize a music bed, mix."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

SAMPLE_RATE = 44100

# Four-chord ambient progression (frequencies in Hz), roughly A minor 9.
_CHORDS: list[list[float]] = [
    [110.00, 164.81, 246.94, 261.63],  # Am9
    [87.31, 130.81, 164.81, 220.00],   # Fmaj7
    [130.81, 196.00, 246.94, 329.63],  # Cmaj7
    [98.00, 146.83, 246.94, 329.63],   # G6
]
_CHORD_SECONDS = 4.0
_CHORD_CROSSFADE = 1.2


class AudioError(RuntimeError):
    """Raised when audio cannot be decoded or written."""


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_audio(path: str | Path, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Decode *path* (MP3/WAV/...) into mono float32 samples in [-1, 1]."""
    path = Path(path)
    if not path.is_file():
        raise AudioError(f"audio file not found: {path}")
    result = subprocess.run(
        [
            _ffmpeg(),
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise AudioError(f"could not decode {path}: {message or 'no audio stream'}")
    return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def audio_duration(path: str | Path, sample_rate: int = SAMPLE_RATE) -> float:
    return len(load_audio(path, sample_rate)) / float(sample_rate)


def write_wav(samples: np.ndarray, path: str | Path, sample_rate: int = SAMPLE_RATE) -> Path:
    """Write mono float32 *samples* as a 16-bit PCM WAV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    payload = (clipped * 32767.0).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(payload)
    return path


def _apply_edges(clip: np.ndarray, sample_rate: int) -> np.ndarray:
    """Short fades so clips never click when they enter or leave the mix."""
    clip = clip.copy()
    fade_in = min(len(clip), int(0.06 * sample_rate))
    fade_out = min(len(clip), int(0.12 * sample_rate))
    if fade_in:
        clip[:fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    if fade_out:
        clip[-fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32)
    return clip


def mix_clips(
    clips: list[tuple[np.ndarray, float]],
    duration: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Place ``(samples, start_seconds)`` clips on a silent track of *duration*."""
    total = max(1, round(duration * sample_rate))
    track = np.zeros(total, dtype=np.float32)
    for clip, start in clips:
        if clip.size == 0:
            continue
        offset = max(0, round(start * sample_rate))
        if offset >= total:
            continue
        fade = _apply_edges(clip, sample_rate)
        end = min(total, offset + fade.size)
        track[offset:end] += fade[: end - offset]
    return track


def ambient_music(
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    *,
    lowpass_hz: float = 1400.0,
) -> np.ndarray:
    """Generate a soft, slowly evolving pad to sit under the narration."""
    total = max(1, round(duration * sample_rate))
    pad = np.zeros(total, dtype=np.float32)
    step = _CHORD_SECONDS - _CHORD_CROSSFADE
    index = 0
    cursor = 0.0

    while cursor < duration:
        chord = _CHORDS[index % len(_CHORDS)]
        length = min(_CHORD_SECONDS, duration - cursor)
        if length <= 0.05:
            break
        count = round(length * sample_rate)
        time = np.arange(count, dtype=np.float32) / sample_rate

        attack = np.clip(time / 1.6, 0.0, 1.0)
        release = np.clip((length - time) / 1.6, 0.0, 1.0)
        envelope = 0.5 - 0.5 * np.cos(np.pi * np.minimum(attack, release))

        voice = np.zeros(count, dtype=np.float32)
        for note in chord:
            voice += np.sin(2.0 * np.pi * note * time).astype(np.float32)
            voice += 0.35 * np.sin(
                2.0 * np.pi * note * 1.003 * time + 0.6
            ).astype(np.float32)
        voice *= envelope / (len(chord) * 1.35)

        offset = round(cursor * sample_rate)
        end = min(total, offset + count)
        pad[offset:end] += voice[: end - offset]

        cursor += step
        index += 1

    # Soften the highs with a zero-phase FFT low-pass (no scipy dependency).
    spectrum = np.fft.rfft(pad)
    frequencies = np.fft.rfftfreq(pad.size, 1.0 / sample_rate)
    spectrum /= 1.0 + (frequencies / lowpass_hz) ** 2
    pad = np.fft.irfft(spectrum, n=pad.size).astype(np.float32)

    if pad.size:
        time = np.arange(pad.size, dtype=np.float32) / sample_rate
        pad *= (0.85 + 0.15 * np.sin(2.0 * np.pi * 0.07 * time)).astype(np.float32)
        fade = min(int(2.0 * sample_rate), pad.size // 2)
        if fade > 0:
            pad[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
            pad[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)

    peak = float(np.max(np.abs(pad))) if pad.size else 0.0
    if peak > 0:
        pad /= peak
    return pad


def build_soundtrack(
    clips: list[tuple[np.ndarray, float]],
    duration: float,
    output: str | Path,
    *,
    music: bool = False,
    music_volume: float = 0.12,
    sample_rate: int = SAMPLE_RATE,
) -> Path:
    """Mix narration clips and an optional music bed into a WAV soundtrack."""
    track = mix_clips(clips, duration, sample_rate)
    if music:
        gain = float(np.clip(music_volume, 0.0, 1.0))
        if not clips:
            # Music-only videos need an audible bed, not a whisper.
            gain = max(gain, 0.5)
        bed = ambient_music(duration, sample_rate)
        track = track + bed * gain

    peak = float(np.max(np.abs(track))) if track.size else 0.0
    if peak > 0.99:
        track = track * (0.99 / peak)
    return write_wav(track, output, sample_rate)
