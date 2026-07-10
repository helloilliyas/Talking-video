# Talking Avatar Backend (FastAPI on Modal)

Serverless GPU pipeline: **CosyVoice** (TTS + voice cloning) → **FLOAT**
(talking portrait) → **MuseTalk 1.5** (lip-sync refinement) → **GFPGAN**
(face restoration, HQ mode) → **FFmpeg** (aspect ratio + MP4).

## Layout

```
backend/
├── deploy.py                  # `modal deploy backend/deploy.py`
└── talking_avatar/
    ├── common.py              # Modal app, images, volumes, dicts, secret
    ├── schemas.py             # Pydantic models / enums
    ├── api.py                 # FastAPI app (auth, uploads, job polling)
    ├── pipeline.py            # orchestrator (spawned per job)
    ├── voice.py               # CosyVoice service + voice cloning
    ├── avatar.py              # FLOAT generation
    ├── lipsync.py             # MuseTalk 1.5 refinement
    └── enhance.py             # GFPGAN restoration + FFmpeg finalize
```

## Setup

1. Install Modal and authenticate:

   ```bash
   pip install -r backend/requirements.txt
   modal setup
   ```

2. Create the API token secret (the Android app sends it as a Bearer token):

   ```bash
   modal secret create talking-avatar-api API_TOKEN=$(openssl rand -hex 32)
   ```

3. Deploy:

   ```bash
   cd backend
   modal deploy deploy.py
   ```

   Modal prints the public URL of `fastapi_app`
   (e.g. `https://<user>--talking-avatar-fastapi-app.modal.run`). Put that
   URL and the token into the Android app's Settings screen.

4. (Optional) Seed preloaded voices — drop `ref.wav` + `transcript.txt` into
   `backend/preloaded_voices/<voice_id>/` for the ids listed in
   `voice.py:PRELOADED_VOICES`, then:

   ```bash
   modal run deploy.py
   ```

   Only use clips you own or that are permissively licensed (e.g. your own
   recordings, LibriTTS).

## API

All endpoints require `Authorization: Bearer <API_TOKEN>`.

| Method | Path                    | Body                                                        | Returns |
|--------|-------------------------|-------------------------------------------------------------|---------|
| GET    | `/v1/voices`            | —                                                           | voice list |
| POST   | `/v1/voices/clone`      | multipart: `name`, `transcript`, `language`, `audio`, `consent=true` | `{voice_id}` |
| POST   | `/v1/jobs`              | multipart: `photo`, `script` or `audio`, `voice_id`, `speed`, `emotion`, `mode` (`fast`/`hq`), `aspect_ratio`, `consent=true` | `{job_id}` |
| GET    | `/v1/jobs/{id}`         | —                                                           | stage/progress/error |
| GET    | `/v1/jobs/{id}/video`   | —                                                           | final MP4 |

`consent=true` is mandatory — the API refuses jobs without an explicit
confirmation that you have permission to use the photo and voice.

## Cost notes

Everything scales to zero. Weights live on a persistent volume so cold
starts skip the multi-GB downloads. Rough per-video GPU time for a 30 s
clip: ~1 min CosyVoice (L4) + ~2–4 min FLOAT (A10G) + ~1–2 min MuseTalk
(A10G) + ~2 min GFPGAN (T4, HQ only) — comfortably inside a $30/month
budget at personal usage levels.

## First-run caveats

The model repos pinned in `common.py` move fast; if an upstream
`requirements.txt` or CLI flag changes, the affected image build or stage
will fail loudly — pin to a commit SHA in `common.py` once you have a
working build. FLOAT checkpoint is fetched from a HF mirror
(`yuvraj108c/float`); you can also request the official checkpoint from
DeepBrain AI and upload it to the weights volume manually.
