"""FLOAT stage — generate a talking portrait video from one photo + audio.

FLOAT (deepbrainai-research/float) is a flow-matching audio-driven talking
head model. It produces natural head motion and expression from a single
reference image; MuseTalk then refines the mouth region for tighter sync.
"""

import subprocess
from pathlib import Path

import modal

from .common import WEIGHTS_DIR, app, float_image, jobs_volume, weights_volume, JOBS_DIR

FLOAT_CKPT = "float.pth"
FLOAT_HF_REPO = "yuvraj108c/float"  # mirror of the official release checkpoint


def _ensure_weights() -> Path:
    from huggingface_hub import hf_hub_download

    ckpt_dir = Path(WEIGHTS_DIR) / "float"
    ckpt = ckpt_dir / FLOAT_CKPT
    if not ckpt.exists():
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        hf_hub_download(FLOAT_HF_REPO, FLOAT_CKPT, local_dir=str(ckpt_dir))
        weights_volume.commit()
    return ckpt


@app.function(
    image=float_image,
    gpu="A10G",
    timeout=1800,
    volumes={JOBS_DIR: jobs_volume, WEIGHTS_DIR: weights_volume},
)
def generate_avatar(job_id: str, emotion: str | None = None) -> str:
    """Run FLOAT for a job. Expects <job>/photo.png and <job>/speech.wav on the
    jobs volume; writes <job>/avatar_raw.mp4 and returns its relative path."""
    ckpt = _ensure_weights()
    job_dir = Path(JOBS_DIR) / job_id
    jobs_volume.reload()

    ref = job_dir / "photo.png"
    aud = job_dir / "speech.wav"
    out = job_dir / "avatar_raw.mp4"

    cmd = [
        "python", "/opt/float/generate.py",
        "--ref_path", str(ref),
        "--aud_path", str(aud),
        "--ckpt_path", str(ckpt),
        "--res_video_path", str(out),
        "--no_crop",  # we pre-crop to a centered face in the finalize stage
    ]
    if emotion:
        # FLOAT supports emotion conditioning (S2E): angry, disgust, fear,
        # happy, neutral, sad, surprise.
        cmd += ["--emo", emotion]

    subprocess.run(cmd, check=True, cwd="/opt/float")
    if not out.exists():
        raise RuntimeError("FLOAT did not produce an output video")

    jobs_volume.commit()
    return f"{job_id}/avatar_raw.mp4"
