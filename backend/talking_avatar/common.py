"""Shared Modal app, volumes, and container images for every pipeline stage.

Each heavyweight model gets its own image so a change to one stage does not
force a rebuild of the others, and so each stage can run on the cheapest GPU
that fits it. Model weights are baked into the images at build time (or on
first boot into the weights volume) so cold starts don't re-download them.
"""

import modal

APP_NAME = "talking-avatar"

app = modal.App(APP_NAME)

# Persistent storage shared by all stages:
#   jobs volume    — per-job working dirs (inputs, intermediate media, final MP4)
#   weights volume — model checkpoints downloaded once and reused
#   voices volume  — cloned-voice reference audio + metadata
jobs_volume = modal.Volume.from_name("talking-avatar-jobs", create_if_missing=True)
weights_volume = modal.Volume.from_name("talking-avatar-weights", create_if_missing=True)
voices_volume = modal.Volume.from_name("talking-avatar-voices", create_if_missing=True)

JOBS_DIR = "/jobs"
WEIGHTS_DIR = "/weights"
VOICES_DIR = "/voices"

# Job status shared between the API and the pipeline workers.
job_store = modal.Dict.from_name("talking-avatar-job-store", create_if_missing=True)
voice_registry = modal.Dict.from_name("talking-avatar-voice-registry", create_if_missing=True)

# Bearer token for the personal API. Create with:
#   modal secret create talking-avatar-api API_TOKEN=<long-random-string>
api_secret = modal.Secret.from_name("talking-avatar-api")

CUDA_BASE = "nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04"

# ---------------------------------------------------------------------------
# API image — lightweight, CPU only.
# ---------------------------------------------------------------------------
api_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")  # normalizes uploaded audio in the pipeline
    .pip_install("fastapi[standard]==0.115.*", "python-multipart")
)

# ---------------------------------------------------------------------------
# CosyVoice — TTS with zero-shot voice cloning.
# The CosyVoice2-0.5B checkpoint is the stable release in the FunAudioLLM
# repo; swap COSYVOICE_MODEL_ID for the CosyVoice 3 checkpoint when its
# inference code lands upstream.
# ---------------------------------------------------------------------------
COSYVOICE_REPO = "https://github.com/FunAudioLLM/CosyVoice.git"
COSYVOICE_MODEL_ID = "iic/CosyVoice2-0.5B"

cosyvoice_image = (
    modal.Image.from_registry(CUDA_BASE, add_python="3.10")
    .apt_install("git", "git-lfs", "ffmpeg", "sox", "libsox-dev", "build-essential")
    .run_commands(
        f"git clone --recursive {COSYVOICE_REPO} /opt/CosyVoice",
        "pip install -r /opt/CosyVoice/requirements.txt",
    )
    .pip_install("modelscope")
    .env({"PYTHONPATH": "/opt/CosyVoice:/opt/CosyVoice/third_party/Matcha-TTS"})
)

# ---------------------------------------------------------------------------
# FLOAT — audio-driven talking portrait from a single photo.
# ---------------------------------------------------------------------------
FLOAT_REPO = "https://github.com/deepbrainai-research/float.git"

float_image = (
    modal.Image.from_registry(CUDA_BASE, add_python="3.10")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .run_commands(
        f"git clone {FLOAT_REPO} /opt/float",
        "pip install -r /opt/float/requirements.txt",
    )
    .pip_install("huggingface_hub")
    .env({"PYTHONPATH": "/opt/float"})
)

# ---------------------------------------------------------------------------
# MuseTalk 1.5 — real-time lip-sync refinement pass.
# ---------------------------------------------------------------------------
MUSETALK_REPO = "https://github.com/TMElyralab/MuseTalk.git"

musetalk_image = (
    modal.Image.from_registry(CUDA_BASE, add_python="3.10")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .run_commands(
        f"git clone {MUSETALK_REPO} /opt/MuseTalk",
        "pip install -r /opt/MuseTalk/requirements.txt",
        "pip install --no-cache-dir openmim && mim install mmengine 'mmcv==2.0.1' 'mmdet==3.1.0' 'mmpose==1.1.0'",
    )
    .env({"PYTHONPATH": "/opt/MuseTalk"})
)

# ---------------------------------------------------------------------------
# GFPGAN + FFmpeg — face restoration and final mux/crop.
# ---------------------------------------------------------------------------
enhance_image = (
    modal.Image.from_registry(CUDA_BASE, add_python="3.10")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.1.2",
        "torchvision==0.16.2",
        "gfpgan==1.3.8",
        "realesrgan==0.3.0",
        "basicsr==1.4.2",
        "facexlib==0.3.0",
        "opencv-python-headless",
        "numpy<2",
    )
)
