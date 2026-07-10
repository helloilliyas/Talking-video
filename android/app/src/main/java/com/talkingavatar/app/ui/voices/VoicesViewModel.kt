package com.talkingavatar.app.ui.voices

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.talkingavatar.app.data.Repository
import com.talkingavatar.app.data.VoiceInfo
import com.talkingavatar.app.util.AudioRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

data class VoicesUiState(
    val voices: List<VoiceInfo> = emptyList(),
    val recording: Boolean = false,
    val sampleFile: File? = null,
    val cloneName: String = "",
    val transcript: String = "",
    val consent: Boolean = false,
    val busy: Boolean = false,
    val message: String? = null,
    val error: String? = null,
) {
    val canClone: Boolean
        get() = sampleFile != null && cloneName.isNotBlank() && consent && !busy
}

class VoicesViewModel(app: Application) : AndroidViewModel(app) {
    private val repository = Repository(app)
    private val recorder = AudioRecorder(app)

    private val _state = MutableStateFlow(VoicesUiState())
    val state: StateFlow<VoicesUiState> = _state

    fun refresh() = viewModelScope.launch {
        runCatching { repository.listVoices() }
            .onSuccess { v -> _state.update { it.copy(voices = v, error = null) } }
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
    }

    fun startRecording() {
        runCatching { recorder.start() }
            .onSuccess { _state.update { s -> s.copy(recording = true, message = null) } }
            .onFailure { e -> _state.update { s -> s.copy(error = e.message) } }
    }

    fun stopRecording() {
        val file = recorder.stop()
        _state.update { it.copy(recording = false, sampleFile = file) }
    }

    fun useUploadedSample(uri: Uri) = viewModelScope.launch {
        val context = getApplication<Application>()
        val file = withContext(Dispatchers.IO) {
            val out = File.createTempFile("voice-upload", null, context.cacheDir)
            context.contentResolver.openInputStream(uri)!!.use { input ->
                out.outputStream().use { input.copyTo(it) }
            }
            out
        }
        _state.update { it.copy(sampleFile = file) }
    }

    fun setCloneName(name: String) = _state.update { it.copy(cloneName = name) }
    fun setTranscript(text: String) = _state.update { it.copy(transcript = text) }
    fun setConsent(ok: Boolean) = _state.update { it.copy(consent = ok) }

    fun clone() {
        val s = _state.value
        if (!s.canClone) return
        _state.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            runCatching {
                repository.cloneVoice(s.cloneName, s.transcript, "auto", s.sampleFile!!)
            }.onSuccess {
                _state.update {
                    it.copy(busy = false, message = "Voice cloned!", sampleFile = null,
                            cloneName = "", transcript = "", consent = false)
                }
                refresh()
            }.onFailure { e ->
                _state.update { it.copy(busy = false, error = e.message) }
            }
        }
    }
}
