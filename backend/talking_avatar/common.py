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

# The model repos ship legacy setup.py packages whose builds import
# pkg_resources, removed in setuptools 81. PIP_CONSTRAINT applies inside
# pip's isolated build environments too, keeping those builds on a
# setuptools that still bundles it.
PIP_COMPAT_ENV = {"PIP_CONSTRAINT": "/etc/pip-constraints.txt"}
PIP_COMPAT_CMDS = (
    "printf 'setuptools<81\\nwheel\\n' > /etc/pip-constraints.txt",
    "pip install --no-cache-dir 'setuptools<81' wheel",
)

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
    # clang: Modal's Python toolchain compiles C extensions with clang++
    .apt_install("git", "git-lfs", "ffmpeg", "sox", "libsox-dev", "build-essential", "clang")
    .env(PIP_COMPAT_ENV)
    .run_commands(
        *PIP_COMPAT_CMDS,
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
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "build-essential", "clang")
    .env(PIP_COMPAT_ENV)
    .run_commands(
        *PIP_COMPAT_CMDS,
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
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "build-essential", "clang")
    .env(PIP_COMPAT_ENV)
    .run_commands(
        *PIP_COMPAT_CMDS,
        f"git clone {MUSETALK_REPO} /opt/MuseTalk",
        "pip install -r /opt/MuseTalk/requirements.txt",
        # MuseTalk's mmlab stack: pin the torch generation mmcv 2.0.1 has
        # prebuilt wheels for, then install mmcv from OpenMMLab's wheel index
        # (a source build compiles C++14 against C++17-only torch headers).
        "pip install torch==2.0.1 torchvision==0.15.2 --index-url https://download.pytorch.org/whl/cu118",
        "pip install --no-cache-dir mmengine",
        "pip install 'mmcv==2.0.1' -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0/index.html",
        "pip install 'mmdet==3.1.0' 'mmpose==1.1.0'",
    )
    .env({"PYTHONPATH": "/opt/MuseTalk"})
)

# ---------------------------------------------------------------------------
# LatentSync 1.6 — diffusion lip-sync, the HQ-mode premium path (Phase 2).
# ---------------------------------------------------------------------------
LATENTSYNC_REPO = "https://github.com/bytedance/LatentSync.git"

latentsync_image = (
    modal.Image.from_registry(CUDA_BASE, add_python="3.10")
    # build-essential + clang: insightface compiles a C++ extension with clang++
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "build-essential", "clang")
    .env(PIP_COMPAT_ENV)
    .run_commands(
        *PIP_COMPAT_CMDS,
        f"git clone {LATENTSYNC_REPO} /opt/LatentSync",
        "pip install -r /opt/LatentSync/requirements.txt",
    )
    .pip_install("huggingface_hub")
    .env({"PYTHONPATH": "/opt/LatentSync"})
)

# ---------------------------------------------------------------------------
# Captions — faster-whisper on CPU (Phase 2).
# ---------------------------------------------------------------------------
captions_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("faster-whisper==1.0.3")
)

# ---------------------------------------------------------------------------
# GFPGAN + Real-ESRGAN + RVM + FFmpeg — restoration, upscale, matting, mux.
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
