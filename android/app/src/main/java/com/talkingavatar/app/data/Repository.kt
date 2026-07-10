package com.talkingavatar.app.data

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

class GenerationOptions(
    val script: String,
    val voiceId: String,
    val language: String,
    val speed: Float,
    val emotion: String,
    val highQuality: Boolean,
    val aspectRatio: String,
)

/** Single entry point the ViewModels use to talk to the backend. */
class Repository(private val context: Context) {
    private val settings = SettingsStore(context)

    private suspend fun api(): TalkingAvatarApi {
        val baseUrl = settings.baseUrl.first()
        val token = settings.token.first()
        require(baseUrl.isNotBlank() && token.isNotBlank()) {
            "Set the backend URL and API token in Settings first."
        }
        return ApiFactory.create(baseUrl, token)
    }

    suspend fun listVoices(): List<VoiceInfo> = api().listVoices()

    suspend fun cloneVoice(name: String, transcript: String, language: String, audio: File): String {
        val part = MultipartBody.Part.createFormData(
            "audio", audio.name, audio.asRequestBody("audio/*".toMediaType())
        )
        return api().cloneVoice(
            name = name.asForm(),
            transcript = transcript.asForm(),
            language = language.asForm(),
            consent = "true".asForm(),
            audio = part,
        ).voiceId
    }

    suspend fun createJob(photoUri: Uri, audioUri: Uri?, options: GenerationOptions): String =
        withContext(Dispatchers.IO) {
            val photoFile = copyToCache(photoUri, "photo")
            val photoPart = MultipartBody.Part.createFormData(
                "photo", "photo.png", photoFile.asRequestBody("image/*".toMediaType())
            )
            val audioPart = audioUri?.let {
                val audioFile = copyToCache(it, "audio")
                MultipartBody.Part.createFormData(
                    "audio", "speech", audioFile.asRequestBody("audio/*".toMediaType())
                )
            }
            api().createJob(
                photo = photoPart,
                script = options.script.asForm(),
                voiceId = options.voiceId.asForm(),
                language = options.language.asForm(),
                speed = options.speed.toString().asForm(),
                emotion = options.emotion.asForm(),
                mode = (if (options.highQuality) "hq" else "fast").asForm(),
                aspectRatio = options.aspectRatio.asForm(),
                consent = "true".asForm(),
                audio = audioPart,
            ).jobId
        }

    suspend fun jobStatus(jobId: String): JobStatus = api().jobStatus(jobId)

    /** Download the finished MP4 into the app cache; caller saves it to the Gallery. */
    suspend fun downloadVideo(jobId: String): File = withContext(Dispatchers.IO) {
        val body = api().downloadVideo(jobId)
        val out = File(context.cacheDir, "result-$jobId.mp4")
        body.byteStream().use { input -> out.outputStream().use { input.copyTo(it) } }
        out
    }

    private fun copyToCache(uri: Uri, prefix: String): File {
        val out = File.createTempFile(prefix, null, context.cacheDir)
        context.contentResolver.openInputStream(uri)!!.use { input ->
            out.outputStream().use { input.copyTo(it) }
        }
        return out
    }

    private fun String.asForm(): RequestBody = toRequestBody("text/plain".toMediaType())
}
