"""Caption generation — transcribe the final speech track into an SRT file.

Uses faster-whisper on CPU (the clips are short, so this stays cheap even
when the user uploaded audio and we have no script text to align). The SRT
is burned into the video by the finalize stage's subtitles filter.
"""

from pathlib import Path

from .common import JOBS_DIR, WEIGHTS_DIR, app, captions_image, jobs_volume, weights_volume


def _format_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@app.function(
    image=captions_image,
    timeout=900,
    cpu=4,
    volumes={JOBS_DIR: jobs_volume, WEIGHTS_DIR: weights_volume},
)
def generate_captions(job_id: str, language: str = "auto") -> str:
    """Transcribe <job>/speech.wav into <job>/captions.srt; returns rel path."""
    from faster_whisper import WhisperModel

    model = WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
        download_root=str(Path(WEIGHTS_DIR) / "whisper-ct2"),
    )
    weights_volume.commit()

    jobs_volume.reload()
    job_dir = Path(JOBS_DIR) / job_id
    segments, _info = model.transcribe(
        str(job_dir / "speech.wav"),
        language=None if language == "auto" else language,
        vad_filter=True,
    )

    lines = []
    for i, seg in enumerate(segments, start=1):
        text = seg.text.strip()
        if not text:
            continue
        lines.append(f"{i}\n{_format_ts(seg.start)} --> {_format_ts(seg.end)}\n{text}\n")

    srt_path = job_dir / "captions.srt"
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    jobs_volume.commit()
    return f"{job_id}/captions.srt"
