"""Job orchestrator — runs the full generation pipeline for one job.

Spawned asynchronously by the API (`run_pipeline.spawn(job_id)`); progress is
written to the shared job_store dict so the phone can poll GET /v1/jobs/{id}.
"""

import traceback
from pathlib import Path

import modal

from .avatar import generate_avatar
from .background import replace_background
from .captions import generate_captions
from .common import JOBS_DIR, api_image, app, job_store, jobs_volume
from .enhance import finalize, restore_faces, upscale_video
from .latentsync import refine_lipsync_premium
from .lipsync import refine_lipsync
from .schemas import JobStage, OutputMode
from .voice import VoiceService


def _update(job_id: str, stage: JobStage, progress: float, detail: str = "", error: str | None = None):
    state = job_store.get(job_id, {})
    state.update(
        stage=stage.value,
        progress=progress,
        detail=detail,
        error=error,
        video_ready=stage == JobStage.COMPLETED,
    )
    job_store[job_id] = state


@app.function(
    image=api_image,
    timeout=3600,
    volumes={JOBS_DIR: jobs_volume},
)
def run_pipeline(job_id: str):
    state = job_store.get(job_id)
    if state is None:
        return
    params = state["params"]

    try:
        job_dir = Path(JOBS_DIR) / job_id
        jobs_volume.reload()

        # 1. Voice — synthesize the script, unless the user uploaded audio
        # (any format the phone produces; normalized to WAV here).
        upload = job_dir / "speech_upload"
        if upload.exists():
            _update(job_id, JobStage.VOICE, 0.05, "Preparing audio")
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(upload),
                 "-ac", "1", "-ar", "16000", str(job_dir / "speech.wav")],
                check=True,
            )
            jobs_volume.commit()
        elif not (job_dir / "speech.wav").exists():
            _update(job_id, JobStage.VOICE, 0.05, "Generating speech")
            wav = VoiceService().synthesize.remote(
                text=params["script"],
                voice_id=params["voice_id"],
                speed=params.get("speed", 1.0),
                emotion=params.get("emotion"),
            )
            (job_dir / "speech.wav").write_bytes(wav)
            jobs_volume.commit()

        hq = params.get("mode") == OutputMode.HIGH_QUALITY.value

        # 2. Avatar — FLOAT talking portrait.
        _update(job_id, JobStage.AVATAR, 0.2, "Animating your photo")
        avatar_rel = generate_avatar.remote(job_id, emotion=params.get("emotion"))

        # 3. Lip-sync — MuseTalk 1.5 (fast) or LatentSync 1.6 (premium).
        if hq:
            _update(job_id, JobStage.LIPSYNC, 0.4, "Refining lip-sync (premium)")
            video_rel = refine_lipsync_premium.remote(job_id)
        else:
            _update(job_id, JobStage.LIPSYNC, 0.4, "Refining lip-sync")
            video_rel = refine_lipsync.remote(job_id)

        # 4. Enhancement — GFPGAN face restoration (HQ mode only).
        if hq:
            _update(job_id, JobStage.ENHANCE, 0.6, "Restoring facial detail")
            video_rel = restore_faces.remote(job_id, video_rel)

        # 5. Upscale — Real-ESRGAN x2 to ~1080p (optional).
        if params.get("upscale"):
            _update(job_id, JobStage.UPSCALE, 0.7, "Upscaling to 1080p")
            video_rel = upscale_video.remote(job_id, video_rel)

        # 6. Background replacement — RVM matting (if an image was uploaded).
        if (job_dir / "background.png").exists():
            _update(job_id, JobStage.BACKGROUND, 0.8, "Replacing background")
            video_rel = replace_background.remote(job_id, video_rel)

        # 7. Captions — transcribe the speech track to SRT (optional).
        if params.get("captions"):
            _update(job_id, JobStage.CAPTIONS, 0.88, "Generating captions")
            generate_captions.remote(job_id, params.get("language", "auto"))

        # 8. Finalize — mux, aspect ratio, caption burn-in, compression.
        _update(job_id, JobStage.FINALIZE, 0.95, "Encoding MP4")
        finalize.remote(
            job_id,
            video_rel,
            params.get("aspect_ratio", "9:16"),
            burn_captions=bool(params.get("captions")),
        )

        _update(job_id, JobStage.COMPLETED, 1.0, "Done")
    except Exception as exc:  # surface the failure to the app
        traceback.print_exc()
        _update(job_id, JobStage.FAILED, 0.0, error=f"{type(exc).__name__}: {exc}")
