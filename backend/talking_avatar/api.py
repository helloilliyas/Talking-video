"""FastAPI app served by Modal — the HTTPS surface the Android app talks to.

Endpoints (all under /v1, bearer-token auth):
  GET  /v1/voices              list preloaded + cloned voices
  POST /v1/voices/clone        multipart: name, transcript, language, audio, consent
  POST /v1/jobs                multipart: photo, script|audio, voice_id, options, consent
  GET  /v1/jobs/{job_id}       poll status
  GET  /v1/jobs/{job_id}/video download final MP4
"""

import os
import uuid
from pathlib import Path

import modal

from .common import JOBS_DIR, api_image, api_secret, app, job_store, jobs_volume, voice_registry
from .schemas import AspectRatio, JobStage, JobStatus, OutputMode, VoiceInfo
from .voice import PRELOADED_VOICES, register_cloned_voice

MAX_PHOTO_BYTES = 15 * 1024 * 1024
MAX_AUDIO_BYTES = 30 * 1024 * 1024


def _build_fastapi():
    from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    web = FastAPI(title="Talking Avatar API", version="0.1.0")
    bearer = HTTPBearer()

    def check_auth(creds: HTTPAuthorizationCredentials = Depends(bearer)):
        if creds.credentials != os.environ["API_TOKEN"]:
            raise HTTPException(status_code=401, detail="invalid token")

    def require_consent(consent: bool):
        # Only media the user owns or has explicit permission to use.
        if not consent:
            raise HTTPException(
                status_code=400,
                detail="You must confirm you have permission to use this photo/voice.",
            )

    @web.get("/healthz")
    def healthz():
        return {"ok": True}

    @web.get("/v1/voices", dependencies=[Depends(check_auth)])
    def list_voices() -> list[VoiceInfo]:
        voices = [
            VoiceInfo(voice_id=vid, name=meta["name"], kind="preloaded",
                      language=meta["language"])
            for vid, meta in PRELOADED_VOICES.items()
        ]
        for vid, meta in voice_registry.items():
            if meta.get("kind") == "cloned":
                voices.append(VoiceInfo(voice_id=vid, name=meta["name"],
                                        kind="cloned", language=meta.get("language", "auto")))
        return voices

    @web.post("/v1/voices/clone", dependencies=[Depends(check_auth)])
    async def clone_voice(
        name: str = Form(...),
        transcript: str = Form(""),
        language: str = Form("auto"),
        consent: bool = Form(False),
        audio: UploadFile = None,
    ):
        require_consent(consent)
        if audio is None:
            raise HTTPException(status_code=400, detail="audio file required")
        data = await audio.read()
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="audio too large")
        voice_id = register_cloned_voice.remote(name, data, transcript, language)
        return {"voice_id": voice_id}

    @web.post("/v1/jobs", dependencies=[Depends(check_auth)])
    async def create_job(
        photo: UploadFile,
        script: str = Form(""),
        voice_id: str = Form(""),
        language: str = Form("auto"),
        speed: float = Form(1.0),
        emotion: str = Form(""),
        mode: OutputMode = Form(OutputMode.FAST),
        aspect_ratio: AspectRatio = Form(AspectRatio.PORTRAIT),
        captions: bool = Form(False),
        upscale: bool = Form(False),
        consent: bool = Form(False),
        audio: UploadFile = None,
        background: UploadFile = None,
    ):
        require_consent(consent)
        if not script and audio is None:
            raise HTTPException(status_code=400, detail="provide a script or an audio file")
        if script and not voice_id:
            raise HTTPException(status_code=400, detail="voice_id required with a script")

        photo_bytes = await photo.read()
        if len(photo_bytes) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="photo too large")

        job_id = uuid.uuid4().hex[:16]
        job_dir = Path(JOBS_DIR) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "photo.png").write_bytes(photo_bytes)
        if audio is not None:
            audio_bytes = await audio.read()
            if len(audio_bytes) > MAX_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="audio too large")
            # Raw upload (any format); the pipeline converts it to WAV.
            (job_dir / "speech_upload").write_bytes(audio_bytes)
        if background is not None:
            bg_bytes = await background.read()
            if len(bg_bytes) > MAX_PHOTO_BYTES:
                raise HTTPException(status_code=413, detail="background too large")
            (job_dir / "background.png").write_bytes(bg_bytes)
        jobs_volume.commit()

        job_store[job_id] = {
            "stage": JobStage.QUEUED.value,
            "progress": 0.0,
            "detail": "Queued",
            "error": None,
            "video_ready": False,
            "params": {
                "script": script,
                "voice_id": voice_id,
                "language": language,
                "speed": speed,
                "emotion": emotion or None,
                "mode": mode.value,
                "aspect_ratio": aspect_ratio.value,
                "captions": captions,
                "upscale": upscale,
            },
        }

        from .pipeline import run_pipeline
        run_pipeline.spawn(job_id)
        return {"job_id": job_id}

    @web.get("/v1/jobs/{job_id}", dependencies=[Depends(check_auth)])
    def job_status(job_id: str) -> JobStatus:
        state = job_store.get(job_id)
        if state is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobStatus(
            job_id=job_id,
            stage=JobStage(state["stage"]),
            progress=state["progress"],
            detail=state.get("detail", ""),
            error=state.get("error"),
            video_ready=state.get("video_ready", False),
        )

    @web.get("/v1/jobs/{job_id}/video", dependencies=[Depends(check_auth)])
    def job_video(job_id: str):
        jobs_volume.reload()
        video = Path(JOBS_DIR) / job_id / "final.mp4"
        if not video.exists():
            raise HTTPException(status_code=404, detail="video not ready")
        return FileResponse(str(video), media_type="video/mp4",
                            filename=f"talking-avatar-{job_id}.mp4")

    return web


@app.function(
    image=api_image,
    secrets=[api_secret],
    volumes={JOBS_DIR: jobs_volume},
    scaledown_window=300,
)
@modal.asgi_app()
def fastapi_app():
    return _build_fastapi()
