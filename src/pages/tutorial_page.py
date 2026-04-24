import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTime, QTimer
from PyQt6.QtGui import QMouseEvent, QKeyEvent

from src.config import ASSETS_DIR
from src.utils.icons import get_icon

SEEK_STEP_MS = 5000

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

class ClickableVideoWidget(QVideoWidget):
    """QVideoWidget that toggles play/pause on left click."""
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)

class VolumeSlider(QSlider):
    """QSlider with scroll-to-adjust and pointing cursor."""
    def __init__(self, on_scroll, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._on_scroll = on_scroll
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def wheelEvent(self, event):
        delta = 5 if event.angleDelta().y() > 0 else -5
        self._on_scroll(delta)
        event.accept()

class TutorialPage(QWidget):
    def __init__(self):
        super().__init__()
        self._role = "Pitcher"
        self._is_seeking = False
        self._was_playing = False
        self._skip_seek_start = False
        self._is_muted = False
        self._pre_mute_vol = 50
        self.setObjectName("contentPage")
        # Capture arrow keys on this page
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.build_ui()
        # Timer to resume after seek — gives Media Foundation time to decode
        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self._player_resume)

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
        self._video_widget = ClickableVideoWidget(on_click=self._toggle_play) 
        self._video_widget.setObjectName("tutorialVideo")
        self._video_widget.setMinimumHeight(460)
        self._video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._audio.setVolume(0.5)
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

        # Play | Pause — NoFocus so arrow keys stay on this page
        self._play_btn = QPushButton()
        self._play_btn.setObjectName("tutorialPlayBtn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._play_btn.setIcon(get_icon("player-play", color="#ffffff", size=18))
        self._play_btn.clicked.connect(self._toggle_play)

        # Seek slider — pointing cursor, pause-seek-resume
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setObjectName("tutorialSeek")
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._seek_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._seek_slider.sliderPressed.connect(self._on_seek_start)
        self._seek_slider.sliderMoved.connect(self._on_seek_move)
        self._seek_slider.sliderReleased.connect(self._on_seek_end)
        self._seek_slider.mousePressEvent = self._seek_click

        # Time label
        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setObjectName("tutorialTime")
        self._time_lbl.setFixedWidth(90)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Volume icon — clickable for instant mute
        self._vol_icon = QLabel()
        self._vol_icon.setFixedSize(18, 18)
        self._vol_icon.setObjectName("tutorialVolIcon")
        self._vol_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_vol_icon(50)
    
        # Volume slider — scroll to adjust, pointing cursor
        self._vol_slider = VolumeSlider(on_scroll=self._scroll_volume)
        self._vol_slider.setObjectName("tutorialVol")
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(50)
        self._vol_slider.setFixedWidth(90)
        self._vol_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._vol_slider.mousePressEvent = self._vol_click
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        self._vol_icon.mousePressEvent = self._toggle_mute

        ctrl_layout.addWidget(self._play_btn)
        ctrl_layout.addWidget(self._seek_slider, stretch=1)
        ctrl_layout.addWidget(self._time_lbl)
        ctrl_layout.addWidget(self._vol_icon)
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

    # Keyboard
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        dur = self._player.duration()
        pos = self._player.position()
        finished = dur > 0 and pos >= dur

        if key == Qt.Key.Key_Left:
            new_pos = max(0, pos - SEEK_STEP_MS)
            was_playing = (
                self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                or finished 
            )
            self._is_seeking = True
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.pause()
            self._seek_slider.setValue(new_pos)
            self._player.setPosition(new_pos)
            if was_playing:
                self._resume_timer.start(80)
            else:
                self._is_seeking = False

        elif key == Qt.Key.Key_Right:
            new_pos = min(dur, pos + SEEK_STEP_MS)
            was_playing = (
                self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            )
            self._is_seeking = True
            if was_playing:
                self._player.pause()
            self._seek_slider.setValue(new_pos)
            self._player.setPosition(new_pos)
            if was_playing:
                self._resume_timer.start(80)
            else:
                self._is_seeking = False

        elif key == Qt.Key.Key_Space:
            self._toggle_play()
        elif key == Qt.Key.Key_M:
            self._toggle_mute()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()

    # Player controls
    def _player_resume(self):
        self._is_seeking = False
        self._player.play()

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()
        self.setFocus()

    def _on_seek_start(self):
        """Only called during drag — not during click seeks."""
        if self._skip_seek_start:
            return
        self._was_playing = (
            self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        )
        self._is_seeking = True
        self._resume_timer.stop()
        if self._was_playing:
            self._player.pause()

    def _on_seek_move(self, pos: int):
        self._player.setPosition(pos)

    def _on_seek_end(self):
        if self._skip_seek_start:
            return
        self._player.setPosition(self._seek_slider.value())
        if self._was_playing:
            # self._player.play()
            self._resume_timer.start(80)
        self._is_seeking = False

    def _seek_click(self, event: QMouseEvent):
        """Click-to-jump: handle seek ourselves, skip sliderPressed/Released."""
        if event.button() == Qt.MouseButton.LeftButton:
            dur = self._player.duration()
            pos = self._player.position()
            finished = dur > 0 and pos >= dur
            was_playing = (
                self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                or finished
            )
            ratio = event.position().x() / self._seek_slider.width()
            new_pos = int(ratio * self._seek_slider.maximum())
            self._skip_seek_start = True
            self._is_seeking = True
            self._seek_slider.setValue(new_pos)
            self._player.setPosition(new_pos)
            self._skip_seek_start = False
            if was_playing:
                self._resume_timer.start(80)
            else:
                self._is_seeking = False
        QSlider.mousePressEvent(self._seek_slider, event)
        self.setFocus()

    def _scroll_volume(self, delta: int):
        if self._is_muted:
            self._is_muted = False
        new_val = max(0, min(100, self._vol_slider.value() + delta))
        self._vol_slider.setValue(new_val)
        self.setFocus()

    def _vol_click(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            ratio = event.position().x() / self._vol_slider.width()
            val = int(ratio * 100)
            self._is_muted = False
            self._vol_slider.setValue(val)
        QSlider.mousePressEvent(self._vol_slider, event)
        self.setFocus()

    # Volume
    def _on_volume_changed(self, val: int):
        if not self._is_muted:
            self._audio.setVolume(val / 100.0)
            self._update_vol_icon(val)

    def _toggle_mute(self, event: QMouseEvent = None):
        if self._is_muted:
            # Unmute — restore audio to saved volume 
            self._is_muted = False
            self._vol_slider.blockSignals(True)
            self._vol_slider.setValue(self._pre_mute_vol)
            self._vol_slider.blockSignals(False)
            self._audio.setVolume(self._pre_mute_vol / 100.0)
            self._update_vol_icon(self._pre_mute_vol)
        else:
            # Mute — save last non-zero volume so we never restore to 0
            current = self._vol_slider.value()
            if current > 0:
                self._pre_mute_vol = current
            # _pre_mute_vol keeps its previous value if current is 0
            self._is_muted = True
            self._vol_slider.blockSignals(True)
            self._vol_slider.setValue(0)
            self._vol_slider.blockSignals(False)
            self._audio.setVolume(0.0)
            self._update_vol_icon(0)
        self.setFocus()

    def _update_vol_icon(self, val: int):
        if self._is_muted or val == 0:
            icon_name = "volume-3"
        elif val <= 50:
            icon_name = "volume-2"
        else:
            icon_name = "volume"
        self._vol_icon.setPixmap(
            get_icon(icon_name, color="#555555", size=18).pixmap(18, 18)
        )

    def _on_playback_state(self, state):
        # Don't update icon while user is dragging the seek slider
        if self._is_seeking:
            return
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        stopped = state == QMediaPlayer.PlaybackState.StoppedState
        if stopped and self._player.position() >= self._player.duration() > 0:
            self._play_btn.setIcon(get_icon("reload", color="#ffffff", size=18))
        else:
            icon = "player-pause" if playing else "player-play"
            self._play_btn.setIcon(get_icon(icon, color="#ffffff", size=18))

    def _on_position_changed(self, pos: int):
        if not self._is_seeking:
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
