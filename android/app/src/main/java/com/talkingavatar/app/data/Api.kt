package com.talkingavatar.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Streaming
import java.util.concurrent.TimeUnit

@Serializable
data class VoiceInfo(
    @SerialName("voice_id") val voiceId: String,
    val name: String,
    val kind: String,
    val language: String = "auto",
)

@Serializable
data class CloneResponse(@SerialName("voice_id") val voiceId: String)

@Serializable
data class CreateJobResponse(@SerialName("job_id") val jobId: String)

@Serializable
data class JobStatus(
    @SerialName("job_id") val jobId: String,
    val stage: String,
    val progress: Float = 0f,
    val detail: String = "",
    val error: String? = null,
    @SerialName("video_ready") val videoReady: Boolean = false,
)

interface TalkingAvatarApi {
    @GET("v1/voices")
    suspend fun listVoices(): List<VoiceInfo>

    @Multipart
    @POST("v1/voices/clone")
    suspend fun cloneVoice(
        @Part("name") name: RequestBody,
        @Part("transcript") transcript: RequestBody,
        @Part("language") language: RequestBody,
        @Part("consent") consent: RequestBody,
        @Part audio: MultipartBody.Part,
    ): CloneResponse

    @Multipart
    @POST("v1/jobs")
    suspend fun createJob(
        @Part photo: MultipartBody.Part,
        @Part("script") script: RequestBody,
        @Part("voice_id") voiceId: RequestBody,
        @Part("language") language: RequestBody,
        @Part("speed") speed: RequestBody,
        @Part("emotion") emotion: RequestBody,
        @Part("mode") mode: RequestBody,
        @Part("aspect_ratio") aspectRatio: RequestBody,
        @Part("captions") captions: RequestBody,
        @Part("upscale") upscale: RequestBody,
        @Part("consent") consent: RequestBody,
        @Part audio: MultipartBody.Part?,
        @Part background: MultipartBody.Part?,
    ): CreateJobResponse

    @GET("v1/jobs/{jobId}")
    suspend fun jobStatus(@Path("jobId") jobId: String): JobStatus

    @Streaming
    @GET("v1/jobs/{jobId}/video")
    suspend fun downloadVideo(@Path("jobId") jobId: String): ResponseBody
}

object ApiFactory {
    private val json = Json { ignoreUnknownKeys = true }

    fun create(baseUrl: String, token: String): TalkingAvatarApi {
        val client = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.MINUTES) // video download / slow cold starts
            .addInterceptor { chain ->
                chain.proceed(
                    chain.request().newBuilder()
                        .header("Authorization", "Bearer $token")
                        .build()
                )
            }
            .build()

        return Retrofit.Builder()
            .baseUrl(if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(TalkingAvatarApi::class.java)
    }
}
