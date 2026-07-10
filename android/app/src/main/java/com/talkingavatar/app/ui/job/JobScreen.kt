package com.talkingavatar.app.ui.job

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView

private val STAGE_LABELS = mapOf(
    "queued" to "Waiting for a GPU…",
    "voice" to "Generating speech",
    "avatar" to "Animating your photo",
    "lipsync" to "Refining lip-sync",
    "enhance" to "Restoring facial detail",
    "background" to "Replacing background",
    "upscale" to "Upscaling to 1080p",
    "captions" to "Generating captions",
    "finalize" to "Encoding MP4",
)

@Composable
fun JobScreen(jobId: String, onDone: () -> Unit, viewModel: JobViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    LaunchedEffect(jobId) { viewModel.track(jobId) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        val video = state.videoFile
        when {
            state.error != null -> {
                Text("Something went wrong", style = MaterialTheme.typography.headlineSmall)
                Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
                Button(onClick = onDone) { Text("Back") }
            }

            video != null -> {
                Text("Your avatar is ready 🎉", style = MaterialTheme.typography.headlineSmall)

                val player = remember(video) {
                    ExoPlayer.Builder(context).build().apply {
                        setMediaItem(MediaItem.fromUri(video.toURI().toString()))
                        prepare()
                        playWhenReady = true
                    }
                }
                DisposableEffect(player) { onDispose { player.release() } }
                AndroidView(
                    factory = { PlayerView(it).apply { this.player = player } },
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(9f / 16f),
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = viewModel::saveToGallery, enabled = state.savedUri == null) {
                        Text(if (state.savedUri == null) "Save to Gallery" else "Saved ✓")
                    }
                    OutlinedButton(onClick = {
                        val uri = FileProvider.getUriForFile(
                            context, "${context.packageName}.fileprovider", video
                        )
                        val share = Intent(Intent.ACTION_SEND).apply {
                            type = "video/mp4"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        context.startActivity(Intent.createChooser(share, "Share video"))
                    }) { Text("Share") }
                }
                OutlinedButton(onClick = onDone) { Text("Create another") }
            }

            else -> {
                val status = state.status
                Text("Generating…", style = MaterialTheme.typography.headlineSmall)
                LinearProgressIndicator(
                    progress = { status?.progress ?: 0f },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    STAGE_LABELS[status?.stage] ?: status?.detail
                        ?: if (state.downloading) "Downloading video…" else "Starting…",
                    style = MaterialTheme.typography.bodyLarge,
                )
                Text(
                    "First run can take a few extra minutes while models cold-start.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
