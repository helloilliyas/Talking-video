package com.talkingavatar.app.ui.voices

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun VoicesScreen(viewModel: VoicesViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.refresh() }

    val micPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> if (granted) viewModel.startRecording() }

    val audioPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri -> uri?.let(viewModel::useUploadedSample) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Voices", style = MaterialTheme.typography.headlineSmall)

        state.voices.forEach { voice ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(voice.name, style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${voice.kind} · ${voice.language}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }

        Text("Clone a new voice", style = MaterialTheme.typography.titleMedium)
        Text(
            "Record or upload 10–30 seconds of clean speech (no background noise, one speaker).",
            style = MaterialTheme.typography.bodySmall,
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (state.recording) {
                Button(onClick = viewModel::stopRecording) { Text("Stop recording") }
            } else {
                OutlinedButton(onClick = { micPermission.launch(Manifest.permission.RECORD_AUDIO) }) {
                    Text("Record sample")
                }
            }
            OutlinedButton(onClick = { audioPicker.launch("audio/*") }) {
                Text("Upload sample")
            }
        }
        if (state.sampleFile != null) {
            Text("Sample ready ✓", color = MaterialTheme.colorScheme.primary)
        }

        OutlinedTextField(
            value = state.cloneName,
            onValueChange = viewModel::setCloneName,
            label = { Text("Voice name") },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.transcript,
            onValueChange = viewModel::setTranscript,
            label = { Text("Transcript of the sample (improves quality)") },
            minLines = 2,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = state.consent, onCheckedChange = viewModel::setConsent)
            Text(
                "This is my voice, or the speaker gave explicit permission.",
                style = MaterialTheme.typography.bodySmall,
            )
        }

        state.message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Button(
            onClick = viewModel::clone,
            enabled = state.canClone,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.busy) "Cloning…" else "Clone voice")
        }
    }
}
