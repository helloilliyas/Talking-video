"""MuseTalk 1.5 stage — refine the mouth region of the FLOAT video.

MuseTalk inpaints the lower face frame-by-frame conditioned on the audio,
which noticeably tightens lip articulation over raw FLOAT output. This is
the Phase 1 "fast" refiner; Phase 2 adds LatentSync 1.6 as the premium path.
"""

import subprocess
from pathlib import Path

import modal

from .common import JOBS_DIR, WEIGHTS_DIR, app, jobs_volume, musetalk_image, weights_volume


def _ensure_weights() -> Path:
    """Download the MuseTalk 1.5 checkpoint set once into the weights volume."""
    from huggingface_hub import snapshot_download

    root = Path(WEIGHTS_DIR) / "musetalk"
    marker = root / ".download_complete"
    if not marker.exists():
        root.mkdir(parents=True, exist_ok=True)
        snapshot_download("TMElyralab/MuseTalk", local_dir=str(root))
        # Supporting models MuseTalk expects alongside its own weights.
        snapshot_download("stabilityai/sd-vae-ft-mse", local_dir=str(root / "sd-vae"))
        snapshot_download("openai/whisper-tiny", local_dir=str(root / "whisper"))
        marker.touch()
        weights_volume.commit()
    return root


@app.function(
    image=musetalk_image,
    gpu="A10G",
    timeout=1800,
    volumes={JOBS_DIR: jobs_volume, WEIGHTS_DIR: weights_volume},
)
def refine_lipsync(job_id: str) -> str:
    """Refine <job>/avatar_raw.mp4 against <job>/speech.wav.
    Writes <job>/lipsync.mp4 and returns its relative path."""
    weights_root = _ensure_weights()
    jobs_volume.reload()
    job_dir = Path(JOBS_DIR) / job_id

    video_in = job_dir / "avatar_raw.mp4"
    audio_in = job_dir / "speech.wav"
    result_dir = job_dir / "musetalk_out"
    result_dir.mkdir(exist_ok=True)

    config_path = job_dir / "musetalk_inference.yaml"
    config_path.write_text(
        "task_0:\n"
        f"  video_path: {video_in}\n"
        f"  audio_path: {audio_in}\n"
    )

    subprocess.run(
        [
            "python", "-m", "scripts.inference",
            "--inference_config", str(config_path),
            "--result_dir", str(result_dir),
            "--unet_model_path", str(weights_root / "musetalkV15" / "unet.pth"),
            "--unet_config", str(weights_root / "musetalkV15" / "musetalk.json"),
            "--whisper_dir", str(weights_root / "whisper"),
            "--vae_dir", str(weights_root / "sd-vae"),
            "--version", "v15",
        ],
        check=True,
        cwd="/opt/MuseTalk",
    )

    outputs = sorted(result_dir.rglob("*.mp4"))
    if not outputs:
        raise RuntimeError("MuseTalk did not produce an output video")
    final = job_dir / "lipsync.mp4"
    outputs[0].replace(final)

    jobs_volume.commit()
    return f"{job_id}/lipsync.mp4"
