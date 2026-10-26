"""Text-to-speech providers (Edge neural voices, Google Translate TTS).

Both providers are optional so the core renderer stays dependency-light:

    pip install "nayro-studio[voice]"
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

PROVIDERS = ("auto", "edge", "gtts")
DEFAULT_LANG = "ar"
DEFAULT_VOICES = {
    "ar": "ar-LB-LaylaNeural",
    "en": "en-US-AriaNeural",
}


class TTSError(RuntimeError):
    """Raised when no speech provider could synthesize the script."""


def available_providers() -> list[str]:
    """Names of the speech providers importable in this environment."""
    found = []
    if importlib.util.find_spec("edge_tts") is not None:
        found.append("edge")
    if importlib.util.find_spec("gtts") is not None:
        found.append("gtts")
    return found


def default_voice(lang: str) -> str:
    return DEFAULT_VOICES.get((lang or DEFAULT_LANG).split("-")[0], DEFAULT_VOICES["en"])


def _edge_speak(text: str, output: Path, lang: str, voice: str | None) -> None:
    try:
        import asyncio

        import edge_tts
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise TTSError("edge-tts is not installed; run: pip install 'nayro-studio[voice]'") from exc

    async def run() -> None:
        communicate = edge_tts.Communicate(text, voice or default_voice(lang))
        await communicate.save(str(output))

    asyncio.run(run())


def _gtts_speak(text: str, output: Path, lang: str, voice: str | None) -> None:
    try:
        from gtts import gTTS
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise TTSError("gTTS is not installed; run: pip install 'nayro-studio[voice]'") from exc
    gTTS(text=text, lang=lang or DEFAULT_LANG, slow=False).save(str(output))


_PROVIDER_FUNCS: dict[str, Callable[[str, Path, str, str | None], None]] = {
    "edge": _edge_speak,
    "gtts": _gtts_speak,
}


def synthesize_speech(
    text: str,
    output: str | Path,
    *,
    provider: str = "auto",
    lang: str = DEFAULT_LANG,
    voice: str | None = None,
) -> Path:
    """Synthesize *text* into *output* (MP3) and return the written path.

    ``provider="auto"`` tries the highest quality available provider first
    (Edge neural voices, then Google Translate TTS).
    """
    text = " ".join((text or "").split())
    if not text:
        raise TTSError("cannot synthesize empty text")
    if provider not in PROVIDERS:
        raise TTSError(f"unknown provider {provider!r}; choose from {', '.join(PROVIDERS)}")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    order = ["edge", "gtts"] if provider == "auto" else [provider]
    failures: list[str] = []
    for name in order:
        try:
            _PROVIDER_FUNCS[name](text, output, lang, voice)
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            failures.append(f"{name}: {exc}")
            continue
        if output.is_file() and output.stat().st_size > 0:
            return output
        failures.append(f"{name}: produced no audio")

    raise TTSError(
        "speech synthesis failed for all providers ("
        + "; ".join(failures)
        + "). Install the voice extras or check the network connection."
    )
