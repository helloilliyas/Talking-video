"""CosyVoice TTS stage — preloaded voices and zero-shot voice cloning.

Runs as a Modal class so the model loads once per container and is reused
across requests. Cloned voices are just a reference WAV (10–30 s) plus its
transcript stored on the voices volume; CosyVoice conditions on them at
inference time (zero-shot), so "cloning" is instant and free.
"""

import json
import os
import uuid
from pathlib import Path

import modal

from .common import (
    COSYVOICE_MODEL_ID,
    VOICES_DIR,
    WEIGHTS_DIR,
    app,
    cosyvoice_image,
    voice_registry,
    voices_volume,
    weights_volume,
)

# Preloaded voices: short studio-quality reference clips checked into the
# voices volume under /voices/preloaded/<id>/{ref.wav,meta.json}.
# Seed them with `modal run backend/deploy.py::seed_preloaded_voices`.
PRELOADED_VOICES = {
    "en_female_warm": {"name": "Ava (warm female)", "language": "en"},
    "en_male_narrator": {"name": "Marcus (narrator male)", "language": "en"},
}


@app.cls(
    image=cosyvoice_image,
    gpu="L4",
    timeout=600,
    scaledown_window=120,
    volumes={WEIGHTS_DIR: weights_volume, VOICES_DIR: voices_volume},
    secrets=[],
)
class VoiceService:
    @modal.enter()
    def load(self):
        from cosyvoice.cli.cosyvoice import CosyVoice2
        from modelscope import snapshot_download

        model_dir = Path(WEIGHTS_DIR) / "cosyvoice" / COSYVOICE_MODEL_ID.split("/")[-1]
        if not model_dir.exists():
            snapshot_download(COSYVOICE_MODEL_ID, local_dir=str(model_dir))
            weights_volume.commit()

        self.model = CosyVoice2(str(model_dir), load_jit=False, load_trt=False, fp16=True)
        self.sample_rate = self.model.sample_rate

    def _load_reference(self, voice_id: str):
        """Return (prompt_wav_16k tensor, prompt_text) for a voice id."""
        import torchaudio
        from cosyvoice.utils.file_utils import load_wav

        meta = voice_registry.get(voice_id)
        if meta is None:
            raise ValueError(f"unknown voice_id: {voice_id}")
        ref_dir = Path(VOICES_DIR) / meta["path"]
        prompt_speech = load_wav(str(ref_dir / "ref.wav"), 16000)
        prompt_text = json.loads((ref_dir / "meta.json").read_text()).get("transcript", "")
        return prompt_speech, prompt_text

    @modal.method()
    def synthesize(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> bytes:
        """Synthesize `text` in the given voice; returns WAV bytes."""
        import io

        import torch
        import torchaudio

        prompt_speech, prompt_text = self._load_reference(voice_id)

        if emotion:
            # Instruct mode lets us steer style ("speak happily", "whisper"...)
            chunks = self.model.inference_instruct2(
                text, f"Speak in a {emotion} tone.", prompt_speech, speed=speed, stream=False
            )
        elif prompt_text:
            chunks = self.model.inference_zero_shot(
                text, prompt_text, prompt_speech, speed=speed, stream=False
            )
        else:
            # No transcript for the reference clip — cross-lingual mode
            # conditions on timbre alone.
            chunks = self.model.inference_cross_lingual(
                text, prompt_speech, speed=speed, stream=False
            )

        audio = torch.cat([c["tts_speech"] for c in chunks], dim=1)
        buf = io.BytesIO()
        torchaudio.save(buf, audio, self.sample_rate, format="wav")
        return buf.getvalue()


@app.function(
    image=cosyvoice_image,
    volumes={VOICES_DIR: voices_volume},
    timeout=120,
)
def register_cloned_voice(name: str, wav_bytes: bytes, transcript: str, language: str) -> str:
    """Store a user-provided reference clip and register it as a cloned voice.

    The clip is converted with ffmpeg (handles m4a/mp3/wav from the phone) to
    16 kHz mono WAV; CosyVoice zero-shot cloning works best with 10–30 s of
    clean, single-speaker audio.
    """
    import subprocess

    voice_id = f"cloned_{uuid.uuid4().hex[:12]}"
    rel_path = f"cloned/{voice_id}"
    ref_dir = Path(VOICES_DIR) / rel_path
    ref_dir.mkdir(parents=True, exist_ok=True)

    raw_path = ref_dir / "raw_upload"
    raw_path.write_bytes(wav_bytes)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_path),
         "-ac", "1", "-ar", "16000", str(ref_dir / "ref.wav")],
        check=True,
    )
    os.remove(raw_path)

    (ref_dir / "meta.json").write_text(
        json.dumps({"name": name, "transcript": transcript, "language": language})
    )
    voices_volume.commit()

    voice_registry[voice_id] = {
        "name": name,
        "kind": "cloned",
        "language": language,
        "path": rel_path,
    }
    return voice_id
