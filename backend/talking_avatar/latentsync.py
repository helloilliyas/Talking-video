"""LatentSync 1.6 stage — premium lip-sync (High-Quality mode).

LatentSync (ByteDance) is a latent-diffusion lip-sync model: slower than
MuseTalk but noticeably sharper mouth detail and better phoneme accuracy.
Phase 2 wires it in as the HQ path; Fast mode keeps MuseTalk 1.5.
"""

import subprocess
from pathlib import Path

from .common import (
    JOBS_DIR,
    WEIGHTS_DIR,
    app,
    jobs_volume,
    latentsync_image,
    weights_volume,
)

LATENTSYNC_HF_REPO = "ByteDance/LatentSync-1.6"


def _ensure_weights() -> Path:
    """LatentSync expects checkpoints/{latentsync_unet.pt, whisper/tiny.pt}."""
    from huggingface_hub import snapshot_download

    ckpt_dir = Path(WEIGHTS_DIR) / "latentsync"
    if not (ckpt_dir / "latentsync_unet.pt").exists():
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            LATENTSYNC_HF_REPO,
            local_dir=str(ckpt_dir),
            allow_patterns=["latentsync_unet.pt", "whisper/*", "stable_syncnet.pt"],
        )
        weights_volume.commit()
    return ckpt_dir


@app.function(
    image=latentsync_image,
    gpu="L40S",  # diffusion UNet; 1.6 fits in 24 GB but L40S keeps it quick
    timeout=2700,
    volumes={JOBS_DIR: jobs_volume, WEIGHTS_DIR: weights_volume},
)
def refine_lipsync_premium(job_id: str) -> str:
    """Refine <job>/avatar_raw.mp4 against <job>/speech.wav with LatentSync.
    Writes <job>/lipsync.mp4 and returns its relative path."""
    ckpt_dir = _ensure_weights()
    jobs_volume.reload()
    job_dir = Path(JOBS_DIR) / job_id
    out = job_dir / "lipsync.mp4"

    # The repo resolves the whisper checkpoint relative to ./checkpoints.
    subprocess.run(
        ["ln", "-sfn", str(ckpt_dir), "/opt/LatentSync/checkpoints"], check=True
    )
    subprocess.run(
        [
            "python", "-m", "scripts.inference",
            "--unet_config_path", "configs/unet/stage2.yaml",
            "--inference_ckpt_path", str(ckpt_dir / "latentsync_unet.pt"),
            "--inference_steps", "20",
            "--guidance_scale", "1.5",
            "--video_path", str(job_dir / "avatar_raw.mp4"),
            "--audio_path", str(job_dir / "speech.wav"),
            "--video_out_path", str(out),
        ],
        check=True,
        cwd="/opt/LatentSync",
    )
    if not out.exists():
        raise RuntimeError("LatentSync did not produce an output video")

    jobs_volume.commit()
    return f"{job_id}/lipsync.mp4"
