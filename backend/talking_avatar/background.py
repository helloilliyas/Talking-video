"""Background replacement — Robust Video Matting + composite.

RVM (PeterL1n/RobustVideoMatting) produces temporally-stable alpha mattes,
which avoids the edge flicker you get from per-frame segmentation. The
avatar is composited over a user-supplied image (<job>/background.png).
"""

from pathlib import Path

from .common import JOBS_DIR, WEIGHTS_DIR, app, enhance_image, jobs_volume, weights_volume


@app.function(
    image=enhance_image,
    gpu="T4",
    timeout=1800,
    volumes={JOBS_DIR: jobs_volume, WEIGHTS_DIR: weights_volume},
)
def replace_background(job_id: str, input_rel: str) -> str:
    """Matte <input_rel> with RVM and composite over <job>/background.png.
    Writes <job>/background_out.mp4 (video only) and returns its rel path."""
    import cv2
    import numpy as np
    import torch

    # Cache the torch.hub checkout + weights on the weights volume.
    hub_dir = Path(WEIGHTS_DIR) / "torchhub"
    hub_dir.mkdir(parents=True, exist_ok=True)
    torch.hub.set_dir(str(hub_dir))
    model = torch.hub.load(
        "PeterL1n/RobustVideoMatting", "mobilenetv3", pretrained=True
    ).cuda().eval()
    weights_volume.commit()

    jobs_volume.reload()
    job_dir = Path(JOBS_DIR) / job_id
    src = Path(JOBS_DIR) / input_rel
    bg_path = job_dir / "background.png"

    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    bg = cv2.imread(str(bg_path))
    bg = cv2.resize(bg, (width, height), interpolation=cv2.INTER_AREA)
    bg_t = torch.from_numpy(cv2.cvtColor(bg, cv2.COLOR_BGR2RGB)).cuda()
    bg_t = bg_t.permute(2, 0, 1).float().div(255).unsqueeze(0)

    out_path = job_dir / "background_out.mp4"
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )

    rec = [None] * 4  # RVM recurrent states
    downsample = min(512 / max(width, height), 1.0)
    with torch.no_grad():
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            src_t = torch.from_numpy(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).cuda()
            src_t = src_t.permute(2, 0, 1).float().div(255).unsqueeze(0)
            fgr, pha, *rec = model(src_t, *rec, downsample_ratio=downsample)
            comp = fgr * pha + bg_t * (1 - pha)
            comp = comp[0].permute(1, 2, 0).mul(255).byte().cpu().numpy()
            writer.write(cv2.cvtColor(comp, cv2.COLOR_RGB2BGR))
    cap.release()
    writer.release()

    jobs_volume.commit()
    return f"{job_id}/background_out.mp4"
