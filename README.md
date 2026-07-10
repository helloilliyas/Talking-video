# Talking Avatar

A personal Android app that turns **one reference photo + a script (or audio)**
into a talking-avatar MP4 with realistic lip-sync — built entirely on
open-source models, running serverless on Modal so it costs ~$0 when idle.

```
Photo + Script/Audio + Voice
        │
        ▼  HTTPS (bearer token)
FastAPI on Modal
        │
        ├── CosyVoice ───────── speech synthesis / zero-shot voice cloning
        ├── FLOAT ───────────── talking portrait from one photo + audio
        ├── MuseTalk 1.5 ────── lip-sync refinement (fast mode)
        ├── GFPGAN ──────────── face restoration (high-quality mode)
        └── FFmpeg ──────────── aspect ratio, mux, H.264 MP4
        │
        ▼
MP4 → previewed in app → saved to Samsung Gallery (Movies/TalkingAvatar)
```

## Repository layout

| Path       | What it is |
|------------|------------|
| `backend/` | FastAPI + Modal GPU pipeline ([backend/README.md](backend/README.md)) |
| `android/` | Kotlin + Jetpack Compose app ([android/README.md](android/README.md)) |

## Phase 1 features (this repo)

- Upload a reference photo
- Type a script **or** upload your own audio
- Preloaded voices, voice cloning from a 10–30 s sample (record or upload)
- Language, speed, and emotion controls
- Fast mode (FLOAT → MuseTalk) and High-Quality mode (+ GFPGAN restoration)
- 9:16 / 16:9 / 1:1 output
- Progress tracking, in-app preview, save to Gallery, share sheet

## Quick start

1. **Backend** — `pip install modal && modal setup`, create the
   `talking-avatar-api` secret, then `modal deploy backend/deploy.py`
   (details in [backend/README.md](backend/README.md)).
2. **App** — open `android/` in Android Studio, run on your phone, and paste
   the Modal URL + API token into the app's Settings tab.
3. Create: pick a photo, type a script, pick a voice, tap **Generate video**.

## Quality expectations vs HeyGen

HeyGen's quality comes from proprietary models plus a controlled capture
pipeline. This stack is the strongest open-source approximation currently
available for single-photo avatars: FLOAT gives natural head motion and
expressions, MuseTalk tightens lip articulation, and GFPGAN recovers facial
detail. Expect results close to HeyGen's "photo avatar" tier — not its
studio-avatar tier, which requires multi-minute training footage. The
biggest levers on output quality:

- a sharp, front-facing, well-lit reference photo (face ≥ 512 px)
- a clean voice sample for cloning (no music, one speaker, 10–30 s)
- High-Quality mode for the final render; Fast mode for iteration

Phase 2 (LatentSync premium lip-sync, Real-ESRGAN 1080p upscale, captions,
background replacement) and Phase 3 (saved avatars, full-body mode,
HunyuanVideo-Avatar) build on the same job pipeline.

## Ethics

Voice cloning and avatar creation are only for **your own media or media
from someone who gave explicit permission**. The API rejects every request
that doesn't carry an explicit consent confirmation, and the app requires
the consent checkbox before generating or cloning.
