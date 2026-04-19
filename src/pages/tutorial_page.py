import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTime
from PyQt6.QtGui import QIcon

from src.config import ASSETS_DIR
from src.utils.icons import get_icon

# Role-based tutorial content
TUTORIAL_CONTENT = {
    "Pitcher": {
        "title": "Pitcher Tutorial",
        "subtitle": "Learn the fundamentals of proper pitching mechanics tracked by Perfect Pitch.",
        "description": (
            "This tutorial walks you through the correct pitching mechanics that "
            "Perfect Pitch monitors during your sessions. You will learn the key "
            "checkpoints our system tracks from your wind-up and stride to your "
            "arm path and follow-through. Understanding these mechanics will help "
            "you interpret your session results and identify areas to improve. "
            "Watch the full video before starting your first session."
        ),
        "video": "pitcher.mp4",
    },
    "Coach": {
        "title": "Coach Tutorial",
        "subtitle": "Learn how to monitor and manage your pitchers using Perfect Pitch.",
        "description": (
            "This tutorial covers your role as a Coach in Perfect Pitch. You will "
            "learn how to navigate the Pitchers table, interpret each pitcher's "
            "session history and accuracy metrics, and understand the pitch threshold "
            "system based on USA Baseball guidelines. You will also see how to "
            "remove a pitcher from your roster and how to use the Dashboard's "
            "combined view to track your team's overall performance."
        ),
        "video": "coach.mp4",
    },
    "Admin": {
        "title": "Admin Tutorial",
        "subtitle": "Learn how to manage users and oversee the Perfect Pitch system.",
        "description": (
            "This tutorial is for system administrators. You will learn how to "
            "manage user accounts, assign Coach and Pitcher roles, and interpret "
            "the app-wide Dashboard overview. You will also understand the "
            "soft-delete and 90-day data retention system, how inactive accounts "
            "are tracked, and how to use the Users table to monitor the status "
            "of all registered accounts."
        ),
        "video": "admin.mp4",
    },
}

class TutorialPage(QWidget):
    def __init__(self):
        super().__init__()
        self._role = "Pitcher"
        self.setObjectName("contentPage")
        self.build_ui()

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.setSpacing(0)

        # Page title + subtitle
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        outer.addWidget(self.page_title)

        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("tutorialSubtitle")
        self.page_subtitle.setWordWrap(True)
        outer.addWidget(self.page_subtitle)

        outer.addSpacing(24)

        # Main card
        card = QWidget()
        card.setObjectName("tutorialCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(0)

        # Video player
        self._video_widget = QVideoWidget()
        self._video_widget.setObjectName("tutorialVideo")
        self._video_widget.setMinimumHeight(380)
        self._video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._audio.setVolume(0.8)
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)

        card_layout.addWidget(self._video_widget)
        card_layout.addSpacing(14)

        # Custom controls
        controls = QWidget()
        controls.setObjectName("tutorialControls")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(12)

        # Play | Pause
        self._play_btn = QPushButton()
        self._play_btn.setObjectName("tutorialPlayBtn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setIcon(get_icon("player-play", color="#ffffff", size=18))
        self._play_btn.clicked.connect(self._toggle_play)

        # Sleek slider
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setObjectName("tutorialSleek")
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderMoved.connect(self._seek)

        # Time label
        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setObjectName("tutorialTime")
        self._time_lbl.setFixedWidth(90)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Volume slider
        vol_icon = QLabel()
        vol_icon.setFixedSize(16, 16)
        vol_icon.setPixmap(get_icon("volume", color="#555555", size=16).pixmap(16, 16))
        vol_icon.setObjectName("tutorialVolIcon")

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setObjectName("tutorialVol")
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(80)
        self._vol_slider.valueChanged.connect(
            lambda v: self._audio.setVolume(v / 100.0)
        )

        ctrl_layout.addWidget(self._play_btn)
        ctrl_layout.addWidget(self._seek_slider, stretch=1)
        ctrl_layout.addWidget(self._time_lbl)
        ctrl_layout.addWidget(vol_icon)
        ctrl_layout.addWidget(self._vol_slider)

        card_layout.addWidget(controls)
        card_layout.addSpacing(24)

        # Description
        divider = QWidget()
        divider.setObjectName("settingsDivider")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)
        card_layout.addSpacing(20)

        self._desc_lbl = QLabel()
        self._desc_lbl.setObjectName("tutorialDescription")
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setAlignment(Qt.AlignmentFlag.AlignJustify)
        card_layout.addWidget(self._desc_lbl)

        outer.addWidget(card)
        outer.addStretch()

    # Player controls
    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _seek(self, position: int):
        self._player.setPosition(position)

    def _on_playback_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        icon = "player-play" if not playing else "player-pause"
        self._play_btn.setIcon(get_icon(icon, color="#ffffff", size=18))

    def _on_position_changed(self, pos: int):
        self._seek_slider.setValue(pos)
        self._time_lbl.setText(
            f"{self._fmt_ms(pos)} / {self._fmt_ms(self._player.duration())}"
        )

    def _on_duration_changed(self, dur: int):
        self._seek_slider.setRange(0, dur)

    def _fmt_ms(self, ms: int) -> str:
        t = QTime(0, 0).addMSecs(ms)
        return t.toString("m:ss")

    # Lifecycle
    def set_role(self, role: str):
        self._role = role

    def refresh(self):
        content = TUTORIAL_CONTENT.get(self._role, TUTORIAL_CONTENT["Pitcher"])

        self.page_title.setText(content["title"])
        self.page_subtitle.setText(content["subtitle"])
        self._desc_lbl.setText(content["description"])

        # Stop any playing video before switching
        self._player.stop()
        self._seek_slider.setValue(0)
        self._time_lbl.setText("0:00 / 0:00")
        self._play_btn.setIcon(get_icon("player-play", color="#ffffff", size=18))

        video_path = os.path.join(ASSETS_DIR, "videos", content["video"])
        if os.path.isfile(video_path):
            self._player.setSource(QUrl.fromLocalFile(video_path)) 
        else:
            self._player.setSource(QUrl())
