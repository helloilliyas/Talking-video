package com.talkingavatar.app.util

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Saves the finished MP4 into the device Gallery (Movies/TalkingAvatar) via
 * MediaStore — no storage permission needed on API 29+, and Samsung Gallery
 * picks it up immediately.
 */
object VideoSaver {
    suspend fun saveToGallery(context: Context, video: File, displayName: String): Uri =
        withContext(Dispatchers.IO) {
            val values = ContentValues().apply {
                put(MediaStore.Video.Media.DISPLAY_NAME, "$displayName.mp4")
                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                put(
                    MediaStore.Video.Media.RELATIVE_PATH,
                    "${Environment.DIRECTORY_MOVIES}/TalkingAvatar"
                )
                put(MediaStore.Video.Media.IS_PENDING, 1)
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
                ?: error("Could not create MediaStore entry")
            resolver.openOutputStream(uri)!!.use { out ->
                video.inputStream().use { it.copyTo(out) }
            }
            values.clear()
            values.put(MediaStore.Video.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            uri
        }
}
