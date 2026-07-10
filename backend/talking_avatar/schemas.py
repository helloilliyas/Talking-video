"""Pydantic models shared by the API and pipeline."""

from enum import Enum

from pydantic import BaseModel, Field


class OutputMode(str, Enum):
    FAST = "fast"          # FLOAT -> MuseTalk 1.5
    HIGH_QUALITY = "hq"    # Phase 1: fast pipeline + GFPGAN restoration.
                           # Phase 2 swaps MuseTalk for LatentSync here.


class AspectRatio(str, Enum):
    PORTRAIT = "9:16"
    LANDSCAPE = "16:9"
    SQUARE = "1:1"


class JobStage(str, Enum):
    QUEUED = "queued"
    VOICE = "voice"            # TTS / audio prep
    AVATAR = "avatar"          # FLOAT generation
    LIPSYNC = "lipsync"        # MuseTalk refinement
    ENHANCE = "enhance"        # GFPGAN face restoration
    FINALIZE = "finalize"      # mux + aspect ratio + compression
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    kind: str  # "preloaded" | "cloned"
    language: str = "auto"


class JobRequestMeta(BaseModel):
    """Non-file fields of a generation request (files arrive as multipart)."""

    script: str | None = None
    voice_id: str | None = None
    language: str = "auto"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    mode: OutputMode = OutputMode.FAST
    aspect_ratio: AspectRatio = AspectRatio.PORTRAIT
    emotion: str | None = None


class JobStatus(BaseModel):
    job_id: str
    stage: JobStage
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    detail: str = ""
    error: str | None = None
    video_ready: bool = False
