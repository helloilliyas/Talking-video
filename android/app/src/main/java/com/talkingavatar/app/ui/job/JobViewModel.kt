package com.talkingavatar.app.ui.job

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.talkingavatar.app.data.JobStatus
import com.talkingavatar.app.data.Repository
import com.talkingavatar.app.util.VideoSaver
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

data class JobUiState(
    val status: JobStatus? = null,
    val videoFile: File? = null,
    val savedUri: Uri? = null,
    val downloading: Boolean = false,
    val error: String? = null,
)

class JobViewModel(app: Application) : AndroidViewModel(app) {
    private val repository = Repository(app)

    private val _state = MutableStateFlow(JobUiState())
    val state: StateFlow<JobUiState> = _state

    /** Poll the backend until the job completes or fails, then auto-download. */
    fun track(jobId: String) = viewModelScope.launch {
        while (true) {
            val status = runCatching { repository.jobStatus(jobId) }.getOrNull()
            if (status != null) {
                _state.update { it.copy(status = status) }
                when (status.stage) {
                    "completed" -> {
                        download(jobId)
                        return@launch
                    }
                    "failed" -> {
                        _state.update { it.copy(error = status.error ?: "Generation failed") }
                        return@launch
                    }
                }
            }
            delay(3000)
        }
    }

    private suspend fun download(jobId: String) {
        _state.update { it.copy(downloading = true) }
        runCatching { repository.downloadVideo(jobId) }
            .onSuccess { file -> _state.update { it.copy(downloading = false, videoFile = file) } }
            .onFailure { e -> _state.update { it.copy(downloading = false, error = e.message) } }
    }

    fun saveToGallery() = viewModelScope.launch {
        val file = _state.value.videoFile ?: return@launch
        runCatching {
            VideoSaver.saveToGallery(getApplication(), file, "TalkingAvatar-${System.currentTimeMillis()}")
        }.onSuccess { uri -> _state.update { it.copy(savedUri = uri) } }
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
    }
}
