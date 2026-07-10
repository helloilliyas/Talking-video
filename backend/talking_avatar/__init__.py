"""Talking Avatar backend — FastAPI on Modal.

Pipeline: CosyVoice (TTS / voice clone) -> FLOAT (talking head) ->
MuseTalk 1.5 (lip-sync refinement) -> GFPGAN (face restoration) ->
FFmpeg (mux + aspect ratio) -> MP4.
"""
