"""GFPGAN face restoration + FFmpeg finalization.

`restore_faces` runs GFPGAN v1.4 frame-by-frame (HQ mode only in Phase 1).
`finalize` muxes the chosen video with the speech audio, applies the target
aspect ratio via pad (never distorting the face), and compresses to a
phone-friendly H.264 MP4.
"""

import subprocess
from pathlib import Path

import modal

from .common import JOBS_DIR, WEIGHTS_DIR, app, enhance_image, jobs_volume, weights_volume

GFPGAN_URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"


@app.function(
    image=enhance_image,
    gpu="T4",
    timeout=1800,
    volumes={JOBS_DIR: jobs_volume, WEIGHTS_DIR: weights_volume},
)
def restore_faces(job_id: str, input_rel: str) -> str:
    """GFPGAN restoration over every frame of <input_rel>.
    Writes <job>/enhanced.mp4 (video only, audio re-attached in finalize)."""
    import cv2
    from gfpgan import GFPGANer

    ckpt = Path(WEIGHTS_DIR) / "gfpgan" / "GFPGANv1.4.pth"
    if not ckpt.exists():
        ckpt.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["python", "-c", (
            "from basicsr.utils.download_util import load_file_from_url;"
            f"load_file_from_url('{GFPGAN_URL}', model_dir='{ckpt.parent}')"
        )], check=True)
        weights_volume.commit()

    jobs_volume.reload()
    job_dir = Path(JOBS_DIR) / job_id
    src = Path(JOBS_DIR) / input_rel

    restorer = GFPGANer(
        model_path=str(ckpt),
        upscale=1,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=None,
    )

    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = job_dir / "enhanced.mp4"
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        _, _, restored = restorer.enhance(
            frame, has_aligned=False, only_center_face=True, paste_back=True
        )
        writer.write(restored if restored is not None else frame)
    cap.release()
    writer.release()

    jobs_volume.commit()
    return f"{job_id}/enhanced.mp4"


# Aspect-ratio pad expressions: fit the source inside the target canvas and
# pad with blurred background bars (HeyGen-style) rather than stretching.
_CANVAS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


@app.function(
    image=enhance_image,
    timeout=600,
    volumes={JOBS_DIR: jobs_volume},
)
def finalize(job_id: str, video_rel: str, aspect_ratio: str) -> str:
    """Mux video + speech.wav, letterbox onto the target canvas with a blurred
    self-background, encode H.264/AAC. Writes <job>/final.mp4."""
    jobs_volume.reload()
    job_dir = Path(JOBS_DIR) / job_id
    video = Path(JOBS_DIR) / video_rel
    audio = job_dir / "speech.wav"
    out = job_dir / "final.mp4"

    w, h = _CANVAS.get(aspect_ratio, _CANVAS["9:16"])
    filter_complex = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},boxblur=40:8[bg];"
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(audio),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(out),
        ],
        check=True,
    )

    jobs_volume.commit()
    return f"{job_id}/final.mp4"
