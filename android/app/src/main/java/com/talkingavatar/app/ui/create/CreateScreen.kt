package com.talkingavatar.app.ui.create

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage

private val EMOTIONS = listOf("", "happy", "neutral", "sad", "surprise", "angry")
private val LANGUAGES = listOf("auto", "en", "zh", "ja", "ko", "es", "fr", "de")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreateScreen(
    onJobStarted: (String) -> Unit,
    viewModel: CreateViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.refreshVoices() }

    val photoPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { viewModel.setPhoto(it) }
    val audioPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { viewModel.setAudio(it) }
    val backgroundPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { viewModel.setBackground(it) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Create a talking avatar", style = MaterialTheme.typography.headlineSmall)

        // --- Reference photo -------------------------------------------------
        Text("1. Reference photo", style = MaterialTheme.typography.titleMedium)
        if (state.photoUri != null) {
            AsyncImage(
                model = state.photoUri,
                contentDescription = "Selected photo",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(160.dp)
                    .clip(RoundedCornerShape(12.dp)),
            )
        }
        OutlinedButton(onClick = {
            photoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        }) {
            Text(if (state.photoUri == null) "Choose photo" else "Change photo")
        }

        // --- Script or uploaded audio ----------------------------------------
        Text("2. What should it say?", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.script,
            onValueChange = viewModel::setScript,
            label = { Text("Script") },
            minLines = 3,
            enabled = state.audioUri == null,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = { audioPicker.launch("audio/*") }) {
                Text(if (state.audioUri == null) "…or upload audio" else "Audio selected ✓")
            }
            if (state.audioUri != null) {
                Spacer(Modifier.size(8.dp))
                AssistChip(onClick = { viewModel.setAudio(null) }, label = { Text("Clear") })
            }
        }

        // --- Voice ------------------------------------------------------------
        if (state.audioUri == null) {
            Text("3. Voice", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                // Simple chip row; long voice lists scroll horizontally.
                androidx.compose.foundation.lazy.LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.voices.size) { i ->
                        val voice = state.voices[i]
                        FilterChip(
                            selected = voice.voiceId == state.selectedVoiceId,
                            onClick = { viewModel.selectVoice(voice.voiceId) },
                            label = { Text(voice.name + if (voice.kind == "cloned") " (cloned)" else "") },
                        )
                    }
                }
            }

            Text("Language", style = MaterialTheme.typography.labelLarge)
            androidx.compose.foundation.lazy.LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(LANGUAGES.size) { i ->
                    FilterChip(
                        selected = LANGUAGES[i] == state.language,
                        onClick = { viewModel.setLanguage(LANGUAGES[i]) },
                        label = { Text(LANGUAGES[i]) },
                    )
                }
            }

            Text("Speed: %.2fx".format(state.speed), style = MaterialTheme.typography.labelLarge)
            Slider(
                value = state.speed,
                onValueChange = viewModel::setSpeed,
                valueRange = 0.5f..2.0f,
                steps = 5,
            )

            Text("Emotion", style = MaterialTheme.typography.labelLarge)
            androidx.compose.foundation.lazy.LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(EMOTIONS.size) { i ->
                    FilterChip(
                        selected = EMOTIONS[i] == state.emotion,
                        onClick = { viewModel.setEmotion(EMOTIONS[i]) },
                        label = { Text(EMOTIONS[i].ifEmpty { "default" }) },
                    )
                }
            }
        }

        // --- Output options ----------------------------------------------------
        Text("4. Output", style = MaterialTheme.typography.titleMedium)
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            listOf(false to "Fast", true to "High quality").forEachIndexed { index, (hq, label) ->
                SegmentedButton(
                    selected = state.highQuality == hq,
                    onClick = { viewModel.setHighQuality(hq) },
                    shape = SegmentedButtonDefaults.itemShape(index = index, count = 2),
                ) { Text(label) }
            }
        }
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            val ratios = listOf("9:16", "16:9", "1:1")
            ratios.forEachIndexed { index, ratio ->
                SegmentedButton(
                    selected = state.aspectRatio == ratio,
                    onClick = { viewModel.setAspectRatio(ratio) },
                    shape = SegmentedButtonDefaults.itemShape(index = index, count = ratios.size),
                ) { Text(ratio) }
            }
        }

        // --- Extras (Phase 2) -----------------------------------------------------
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Burn-in captions", style = MaterialTheme.typography.bodyLarge)
            Switch(checked = state.captions, onCheckedChange = viewModel::setCaptions)
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Upscale to 1080p", style = MaterialTheme.typography.bodyLarge)
            Switch(checked = state.upscale, onCheckedChange = viewModel::setUpscale)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = {
                backgroundPicker.launch(
                    PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                )
            }) {
                Text(if (state.backgroundUri == null) "Replace background…" else "Background set ✓")
            }
            if (state.backgroundUri != null) {
                Spacer(Modifier.size(8.dp))
                AssistChip(onClick = { viewModel.setBackground(null) }, label = { Text("Clear") })
            }
        }

        // --- Consent + submit ----------------------------------------------------
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = state.consent, onCheckedChange = viewModel::setConsent)
            Text(
                "I own this photo/voice or have explicit permission to use them.",
                style = MaterialTheme.typography.bodySmall,
            )
        }

        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        Button(
            onClick = { viewModel.submit(onJobStarted) },
            enabled = state.canSubmit,
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (state.submitting) {
                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
            } else {
                Text("Generate video")
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}
