package com.talkingavatar.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.VideoCall
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.talkingavatar.app.ui.create.CreateScreen
import com.talkingavatar.app.ui.job.JobScreen
import com.talkingavatar.app.ui.settings.SettingsScreen
import com.talkingavatar.app.ui.theme.TalkingAvatarTheme
import com.talkingavatar.app.ui.voices.VoicesScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            TalkingAvatarTheme {
                TalkingAvatarApp()
            }
        }
    }
}

private data class Tab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@androidx.compose.runtime.Composable
fun TalkingAvatarApp() {
    val navController = rememberNavController()
    val tabs = listOf(
        Tab("create", "Create", Icons.Filled.VideoCall),
        Tab("voices", "Voices", Icons.Filled.RecordVoiceOver),
        Tab("settings", "Settings", Icons.Filled.Settings),
    )
    val backStack by navController.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route

    Scaffold(
        bottomBar = {
            if (currentRoute?.startsWith("job/") != true) {
                NavigationBar {
                    tabs.forEach { tab ->
                        NavigationBarItem(
                            selected = currentRoute == tab.route,
                            onClick = {
                                navController.navigate(tab.route) {
                                    popUpTo("create") { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        }
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = "create",
            modifier = Modifier.padding(padding),
        ) {
            composable("create") {
                CreateScreen(onJobStarted = { jobId -> navController.navigate("job/$jobId") })
            }
            composable("voices") { VoicesScreen() }
            composable("settings") { SettingsScreen() }
            composable("job/{jobId}") { entry ->
                JobScreen(
                    jobId = entry.arguments?.getString("jobId").orEmpty(),
                    onDone = { navController.popBackStack("create", inclusive = false) },
                )
            }
        }
    }
}
