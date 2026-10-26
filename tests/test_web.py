from __future__ import annotations

import time

import numpy as np
import pytest

from nayro_studio.web import Studio, _settings_from, create_app


def wait_for_job(studio: Studio, job_id: str, timeout: float = 90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = studio.get(job_id)
        assert job is not None
        if job.status in {"done", "error"}:
            return job
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


@pytest.fixture()
def app(tmp_path):
    application = create_app(tmp_path / "web", start_worker=True)
    application.config.update(TESTING=True)
    return application


def test_index_is_arabic_chat_ui(app) -> None:
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'dir="rtl"' in html
    assert "استوديو نيرو ليفانت" in html
    assert "أنشئ الفيديو الآن" in html
    assert "/api/jobs" in html


def test_health_and_themes(app) -> None:
    client = app.test_client()
    assert client.get("/healthz").get_json() == {"ok": True}
    themes = client.get("/api/themes").get_json()
    assert set(themes) == {"aurora", "midnight", "sunrise", "desert"}
    assert "accent" in themes["aurora"]


def test_empty_script_is_rejected(app) -> None:
    response = app.test_client().post("/api/jobs", json={"script": "   "})
    assert response.status_code == 400
    assert "سكربت" in response.get_json()["error"]


def test_script_length_is_limited(app) -> None:
    response = app.test_client().post("/api/jobs", json={"script": "ا" * 5000})
    assert response.status_code == 400


def test_unknown_job_returns_404(app) -> None:
    client = app.test_client()
    assert client.get("/api/jobs/missing").status_code == 404
    assert client.get("/media/missing/video.mp4").status_code == 404


def test_settings_are_normalized() -> None:
    settings = _settings_from(
        {
            "theme": "neon",
            "size": "huge",
            "lang": "fr",
            "duration": 99,
            "max_scenes": 99,
            "voice": "",
            "music": 0,
        }
    )
    assert settings == {
        "theme": "aurora",
        "size": "landscape",
        "lang": "ar",
        "duration": 8.0,
        "max_scenes": 12,
        "voice": False,
        "music": False,
    }


def test_generate_video_without_audio(app) -> None:
    client = app.test_client()
    response = client.post(
        "/api/jobs",
        json={
            "script": "المشهد الأول. المشهد الثاني.",
            "voice": False,
            "music": False,
            "duration": 1.0,
            "max_scenes": 2,
        },
    )
    assert response.status_code == 202
    job = wait_for_job(app.extensions["studio"], response.get_json()["id"])
    assert job.status == "done", job.error
    assert job.video_url == f"/media/{job.id}/video.mp4"
    assert job.info is not None and job.info["has_audio"] is False

    media = client.get(job.video_url)
    assert media.status_code == 200
    assert b"ftyp" in media.data[:64]
    assert media.mimetype == "video/mp4"


def test_generate_narrated_video(app, monkeypatch) -> None:
    import nayro_studio.voice as voice_module
    from nayro_studio.audio import SAMPLE_RATE, write_wav

    def fake_synth(text, output, *, provider="auto", lang="ar", voice=None):
        time_axis = np.arange(int(0.25 * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
        samples = (0.4 * np.sin(2.0 * np.pi * 300.0 * time_axis)).astype(np.float32)
        return write_wav(samples, f"{output}.wav")

    monkeypatch.setattr(voice_module, "synthesize_speech", fake_synth)

    client = app.test_client()
    response = client.post(
        "/api/jobs",
        json={
            "script": "فيديو أول. فيديو ثانٍ.",
            "voice": True,
            "music": True,
            "duration": 0.8,
            "max_scenes": 2,
            "size": "landscape",
        },
    )
    assert response.status_code == 202
    job = wait_for_job(app.extensions["studio"], response.get_json()["id"])
    assert job.status == "done", job.error
    assert job.info is not None
    assert job.info["has_audio"] is True
    assert job.info["audio_codec"] == "aac"
    assert job.info["duration"] > 1.5
    assert client.get(job.video_url).status_code == 200


def test_media_rejects_other_files(app) -> None:
    client = app.test_client()
    response = client.post(
        "/api/jobs",
        json={"script": "اختبار.", "voice": False, "music": False, "duration": 1.0},
    )
    job = wait_for_job(app.extensions["studio"], response.get_json()["id"])
    assert client.get(f"/media/{job.id}/other.mp4").status_code == 404
