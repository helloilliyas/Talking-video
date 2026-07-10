package com.talkingavatar.app.ui.create

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.talkingavatar.app.data.GenerationOptions
import com.talkingavatar.app.data.Repository
import com.talkingavatar.app.data.VoiceInfo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CreateUiState(
    val photoUri: Uri? = null,
    val script: String = "",
    val audioUri: Uri? = null,          // uploaded speech instead of a script
    val voices: List<VoiceInfo> = emptyList(),
    val selectedVoiceId: String? = null,
    val language: String = "auto",
    val speed: Float = 1.0f,
    val emotion: String = "",
    val highQuality: Boolean = false,
    val aspectRatio: String = "9:16",
    val captions: Boolean = false,
    val upscale: Boolean = false,
    val backgroundUri: Uri? = null,
    val consent: Boolean = false,
    val submitting: Boolean = false,
    val error: String? = null,
) {
    val canSubmit: Boolean
        get() = photoUri != null && consent && !submitting &&
            (audioUri != null || (script.isNotBlank() && selectedVoiceId != null))
}

class CreateViewModel(app: Application) : AndroidViewModel(app) {
    private val repository = Repository(app)

    private val _state = MutableStateFlow(CreateUiState())
    val state: StateFlow<CreateUiState> = _state

    fun refreshVoices() = viewModelScope.launch {
        runCatching { repository.listVoices() }
            .onSuccess { voices ->
                _state.update {
                    it.copy(
                        voices = voices,
                        selectedVoiceId = it.selectedVoiceId ?: voices.firstOrNull()?.voiceId,
                        error = null,
                    )
                }
            }
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
    }

    fun setPhoto(uri: Uri?) = _state.update { it.copy(photoUri = uri) }
    fun setScript(text: String) = _state.update { it.copy(script = text) }
    fun setAudio(uri: Uri?) = _state.update { it.copy(audioUri = uri) }
    fun selectVoice(id: String) = _state.update { it.copy(selectedVoiceId = id) }
    fun setLanguage(lang: String) = _state.update { it.copy(language = lang) }
    fun setSpeed(speed: Float) = _state.update { it.copy(speed = speed) }
    fun setEmotion(emotion: String) = _state.update { it.copy(emotion = emotion) }
    fun setHighQuality(hq: Boolean) = _state.update { it.copy(highQuality = hq) }
    fun setAspectRatio(ratio: String) = _state.update { it.copy(aspectRatio = ratio) }
    fun setCaptions(on: Boolean) = _state.update { it.copy(captions = on) }
    fun setUpscale(on: Boolean) = _state.update { it.copy(upscale = on) }
    fun setBackground(uri: Uri?) = _state.update { it.copy(backgroundUri = uri) }
    fun setConsent(ok: Boolean) = _state.update { it.copy(consent = ok) }

    fun submit(onJobStarted: (String) -> Unit) {
        val s = _state.value
        if (!s.canSubmit) return
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            runCatching {
                repository.createJob(
                    photoUri = s.photoUri!!,
                    audioUri = s.audioUri,
                    backgroundUri = s.backgroundUri,
                    options = GenerationOptions(
                        script = s.script,
                        voiceId = s.selectedVoiceId.orEmpty(),
                        language = s.language,
                        speed = s.speed,
                        emotion = s.emotion,
                        highQuality = s.highQuality,
                        aspectRatio = s.aspectRatio,
                        captions = s.captions,
                        upscale = s.upscale,
                    ),
                )
            }.onSuccess { jobId ->
                _state.update { it.copy(submitting = false) }
                onJobStarted(jobId)
            }.onFailure { e ->
                _state.update { it.copy(submitting = false, error = e.message) }
            }
        }
    }
}
