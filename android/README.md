# Talking Avatar — Android app

Kotlin + Jetpack Compose (Material 3), single module, MVVM.

## Screens

- **Create** — pick a photo, type a script or upload audio, choose a voice,
  language, speed, emotion, fast/HQ mode, and aspect ratio; consent checkbox;
  starts a generation job.
- **Job** — polls the backend every 3 s, shows the stage/progress, then plays
  the finished MP4 (ExoPlayer) with *Save to Gallery* and *Share*.
- **Voices** — lists preloaded + cloned voices; record (mic) or upload a
  10–30 s sample and clone it.
- **Settings** — backend URL + API token (stored in DataStore).

## Build & run

Open `android/` in Android Studio (Ladybug or newer — it generates the Gradle
wrapper on first sync), or with a local Gradle 8.7+:

```bash
cd android
gradle wrapper --gradle-version 8.7   # one-time, creates gradlew
./gradlew :app:assembleDebug
```

Requires JDK 17 and Android SDK 35. Install the debug APK on your phone,
open **Settings** in the app, and paste the backend URL + token printed by
`modal deploy`.

## Key source files

```
app/src/main/java/com/talkingavatar/app/
├── MainActivity.kt              # nav host + bottom bar
├── data/Api.kt                  # Retrofit API + DTOs
├── data/Repository.kt           # multipart upload, polling, download
├── data/Settings.kt             # DataStore (URL + token)
├── ui/create/…                  # Create screen + ViewModel
├── ui/job/…                     # progress / preview / save
├── ui/voices/…                  # voice list + cloning
├── ui/settings/…                # backend config
└── util/                        # MediaStore saver, MediaRecorder wrapper
```
