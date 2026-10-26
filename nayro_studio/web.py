"""Local web studio: generate narrated videos from a chat-like page."""

from __future__ import annotations

import argparse
import queue
import shutil
import threading
import time
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, request, send_from_directory

from .probe import probe_video
from .storyboard import storyboard_from_prompt
from .theme import THEMES
from .tts import TTSError
from .video import generate_video
from .voice import prepare_voiceover

STATIC_DIR = Path(__file__).resolve().parent / "static"
SIZES: dict[str, tuple[int, int]] = {
    "landscape": (1280, 720),
    "vertical": (720, 1280),
    "square": (900, 900),
}
LANGS = ("ar", "en")
MAX_SCRIPT = 4000


@dataclass
class Job:
    """One generation request coming from the web chat."""

    id: str
    script: str
    settings: dict[str, Any]
    status: str = "queued"
    stage: str = "في الانتظار"
    progress: int = 0
    total: int = 0
    error: str | None = None
    video_path: Path | None = None
    info: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def video_url(self) -> str | None:
        if self.video_path is None or not self.video_path.is_file():
            return None
        return f"/media/{self.id}/video.mp4"

    def to_dict(self) -> dict[str, Any]:
        percent = round(self.progress / self.total * 100) if self.total else 0
        return {
            "id": self.id,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "total": self.total,
            "percent": min(100, max(0, percent)),
            "video_url": self.video_url,
            "error": self.error,
            "info": self.info,
            "created_at": self.created_at,
        }


class Studio:
    """Single-worker render queue shared by all HTTP requests."""

    def __init__(self, output_dir: str | Path, *, start_worker: bool = True) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.queue: queue.Queue[str] = queue.Queue()
        if start_worker:
            self.start_worker()

    def start_worker(self) -> threading.Thread:
        thread = threading.Thread(target=self._worker, name="nayro-render", daemon=True)
        thread.start()
        return thread

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def submit(self, script: str, settings: dict[str, Any]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], script=script, settings=settings)
        with self.lock:
            self.jobs[job.id] = job
        self.queue.put(job.id)
        return job

    # ------------------------------------------------------------- generation
    def _worker(self) -> None:
        while True:
            job_id = self.queue.get()
            job = self.get(job_id)
            if job is None:
                self.queue.task_done()
                continue
            try:
                self._process(job)
            finally:
                self.queue.task_done()

    def _process(self, job: Job) -> None:
        settings = job.settings
        width, height = SIZES[settings["size"]]
        job.status = "running"
        job.stage = "كتابة المشاهد"
        job_dir = self.output_dir / job.id
        job_dir.mkdir(parents=True, exist_ok=True)
        audio_dir = job_dir / ".audio"
        soundtrack = None

        try:
            board = storyboard_from_prompt(
                job.script,
                scene_duration=settings["duration"],
                theme=settings["theme"],
                width=width,
                height=height,
                fps=24,
                max_scenes=settings["max_scenes"],
            )

            if settings["voice"] or settings["music"]:
                job.stage = "توليد الصوت"

                def on_audio(index: int, total: int, _text: str) -> None:
                    job.stage = f"توليد التعليق الصوتي {index}/{total}"

                prepared = prepare_voiceover(
                    board,
                    audio_dir,
                    narrate=settings["voice"],
                    lang=settings["lang"],
                    music=settings["music"],
                    music_volume=0.12,
                    progress=on_audio,
                )
                board, soundtrack = prepared.storyboard, prepared.soundtrack
                job.stage = "مزج الصوت مع الصورة"

            job.stage = "رسم الإطارات"
            job.progress = 0
            job.total = board.frame_count

            def on_frame(done: int, total: int) -> None:
                job.progress = done
                job.total = total

            video = generate_video(
                board,
                job_dir / "video.mp4",
                progress=on_frame,
                audio=soundtrack,
            )
            job.video_path = video
            job.info = probe_video(video)
            job.progress = job.total
            job.stage = "تم إنشاء الفيديو"
            job.status = "done"
        except TTSError as exc:
            job.status = "error"
            job.error = f"تعذّر توليد التعليق الصوتي: {exc}"
        except Exception as exc:  # noqa: BLE001 - surfaced to the browser
            traceback.print_exc()
            job.status = "error"
            job.error = f"حدث خطأ أثناء التوليد: {exc}"
        finally:
            shutil.rmtree(audio_dir, ignore_errors=True)


def _settings_from(payload: dict[str, Any]) -> dict[str, Any]:
    theme = str(payload.get("theme", "aurora"))
    if theme not in THEMES:
        theme = "aurora"
    size = str(payload.get("size", "landscape"))
    if size not in SIZES:
        size = "landscape"
    lang = str(payload.get("lang", "ar"))
    if lang not in LANGS:
        lang = "ar"

    try:
        duration = float(payload.get("duration", 3.0))
    except (TypeError, ValueError):
        duration = 3.0
    duration = max(1.0, min(8.0, duration))

    try:
        max_scenes = int(payload.get("max_scenes", 6))
    except (TypeError, ValueError):
        max_scenes = 6
    max_scenes = max(1, min(12, max_scenes))

    return {
        "theme": theme,
        "size": size,
        "lang": lang,
        "duration": duration,
        "max_scenes": max_scenes,
        "voice": bool(payload.get("voice", True)),
        "music": bool(payload.get("music", True)),
    }


def create_app(
    output_dir: str | Path = "output/web",
    *,
    start_worker: bool = True,
) -> Flask:
    """Build the Flask app; tests can disable the worker thread."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():  # pragma: no cover - packaging mistake
        raise FileNotFoundError(f"web UI missing: {index_path}")
    index_html = index_path.read_text(encoding="utf-8")

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 1_000_000
    studio = Studio(output_dir, start_worker=start_worker)
    app.extensions["studio"] = studio

    @app.get("/")
    def index() -> str:
        return index_html

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True})

    @app.get("/api/themes")
    def themes():
        return jsonify(
            {
                name: {
                    "accent": theme.accent,
                    "top": theme.top,
                    "bottom": theme.bottom,
                }
                for name, theme in THEMES.items()
            }
        )

    @app.post("/api/jobs")
    def create_job():
        payload = request.get_json(silent=True) or {}
        script = " ".join(str(payload.get("script", "")).split())
        if not script:
            return jsonify({"error": "اكتب سكربت الفيديو أولاً."}), 400
        if len(script) > MAX_SCRIPT:
            return jsonify({"error": f"السكربت طويل جداً (الحد {MAX_SCRIPT} حرفاً)."}), 400
        job = studio.submit(script, _settings_from(payload))
        return jsonify(job.to_dict()), 202

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id: str):
        job = studio.get(job_id)
        if job is None:
            return jsonify({"error": "المهمة غير موجودة."}), 404
        return jsonify(job.to_dict())

    @app.get("/media/<job_id>/<path:filename>")
    def media(job_id: str, filename: str):
        job = studio.get(job_id)
        if job is None or job.video_path is None or filename != job.video_path.name:
            abort(404)
        video_path = job.video_path.resolve()
        return send_from_directory(
            video_path.parent,
            filename,
            mimetype="video/mp4",
            conditional=True,
        )

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nayro-web",
        description="Nayro Levant AI Studio - local chat-style video generator.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address")
    parser.add_argument("--port", type=int, default=7860, help="port (default 7860)")
    parser.add_argument("--output-dir", default="output/web", help="where videos are stored")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = parser.parse_args(argv)

    app = create_app(args.output_dir)
    url = f"http://{args.host}:{args.port}"
    print("\n  Nayro Levant AI Studio - استوديو الفيديو")
    print(f"  افتح المتصفح على: {url}")
    print("  أغلق هذه النافذة لإيقاف الخادم (Ctrl+C).\n", flush=True)

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    except OSError as exc:  # pragma: no cover - depends on the user's machine
        print(f"تعذّر تشغيل الخادم على {url}: {exc}")
        print("جرّب منفذاً آخر: python run.py --port 7861")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
