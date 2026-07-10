package com.talkingavatar.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

/** Backend connection settings — the Modal URL and API token from `modal deploy`. */
class SettingsStore(private val context: Context) {
    private val keyBaseUrl = stringPreferencesKey("base_url")
    private val keyToken = stringPreferencesKey("api_token")

    val baseUrl: Flow<String> = context.dataStore.data.map { it[keyBaseUrl] ?: "" }
    val token: Flow<String> = context.dataStore.data.map { it[keyToken] ?: "" }

    suspend fun save(baseUrl: String, token: String) {
        context.dataStore.edit {
            it[keyBaseUrl] = baseUrl.trim()
            it[keyToken] = token.trim()
        }
    }
}
