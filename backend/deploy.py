"""Deploy entrypoint — `modal deploy backend/deploy.py`.

Importing the stage modules registers every function/class on the shared app.
"""

from talking_avatar.common import app  # noqa: F401
from talking_avatar import api, avatar, enhance, lipsync, pipeline, voice  # noqa: F401


@app.local_entrypoint()
def seed_preloaded_voices():
    """One-time helper: upload preloaded-voice reference clips.

    Put 10–30 s WAV clips + transcripts in backend/preloaded_voices/<voice_id>/
    (ref.wav, transcript.txt) before running:
        modal run backend/deploy.py
    Only use clips you have the rights to (your own recordings or
    permissively licensed voice datasets such as LibriTTS).
    """
    from pathlib import Path

    from talking_avatar.common import voice_registry
    from talking_avatar.voice import PRELOADED_VOICES, register_cloned_voice

    src_root = Path(__file__).parent / "preloaded_voices"
    for voice_id, meta in PRELOADED_VOICES.items():
        clip_dir = src_root / voice_id
        wav = clip_dir / "ref.wav"
        if not wav.exists():
            print(f"skip {voice_id}: no {wav}")
            continue
        transcript = (clip_dir / "transcript.txt").read_text().strip() \
            if (clip_dir / "transcript.txt").exists() else ""
        stored_id = register_cloned_voice.remote(
            meta["name"], wav.read_bytes(), transcript, meta["language"]
        )
        # Re-register under the stable preloaded id.
        entry = voice_registry[stored_id]
        entry["kind"] = "preloaded"
        voice_registry[voice_id] = entry
        del voice_registry[stored_id]
        print(f"seeded {voice_id} -> {entry['path']}")
