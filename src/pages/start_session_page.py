from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QDialog, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

from src.utils.icons import get_icon
from src.utils.toast import toast_warning

class SessionSummaryDialog(QDialog):
    """Summary popup shown after END is clicked."""
    def __init__(self, parent, pitch_count: int, mistakes: int, accuracy: float):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("summaryRoot")
        self.setFixedSize(400, 300)
        self._build_ui(pitch_count, mistakes, accuracy)
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        if parent:
            pr = parent.frameGeometry()
            self.move(
                pr.x() + (pr.width() - self.width()) // 2,
                pr.y() + (pr.height() - self.height()) // 2,
            )

    def _build_ui(self, pitch_count: int, mistakes: int, accuracy: float):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("Session Summary")
        title.setObjectName("summaryTitle")
        layout.addWidget(title)

        layout.addSpacing(6)

        subtitle = QLabel("Your session has ended. Here's how you did.")
        subtitle.setObjectName("summarySubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(24)

        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        grid.addWidget(self._stat_card("Pitch Count", str(pitch_count), "#4a9eff"), 0, 0)
        grid.addWidget(self._stat_card("Mistakes", str(mistakes), "#e05555"), 0, 1)
        grid.addWidget(self._stat_card("Accuracy", str(accuracy), "#4ecb71"), 0, 2)
        layout.addLayout(grid)

        layout.addStretch()

        # Save button
        save_btn = QPushButton("Save and Close")
        save_btn.setObjectName("summarySaveBtn")
        save_btn.setFixedHeight(44)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

    def _stat_card(self, label: str, value: str, color: str) -> QWidget:
        card = QWidget()
        card.setObjectName("summaryStatCard")
        col = QVBoxLayout(card)
        col.setContentsMargins(12, 14, 12, 14)
        col.setSpacing(6)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val_lbl = QLabel(value)
        val_lbl.setObjectName("summaryStatValue")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet(f"color: {color}; background: transparent;")

        lbl = QLabel(label)
        lbl.setObjectName("summaryStatLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        col.addWidget(val_lbl)
        col.addWidget(lbl)
        return card

class StartSessionPage(QWidget):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self._running = False
        self._pitch_count = 0
        self._mistakes = 0
        self._threshold = None
        self._capture = None
        self.setObjectName("contentPage")
        self.build_ui()

    def build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Camera feed
        feed_wrapper = QWidget()
        feed_wrapper.setObjectName("feedWrapper")
        feed_layout = QVBoxLayout(feed_wrapper)
        feed_layout.setContentsMargins(0, 0, 0, 0)
        feed_layout.setSpacing(0)

        self.feed_label = QLabel()
        self.feed_label.setObjectName("feedLabel")
        self.feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feed_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self._show_idle_feed()
        feed_layout.addWidget(self.feed_label)

        root.addWidget(feed_wrapper, stretch=3)

        # Stats panel
        panel = QWidget()
        panel.setObjectName("sessionPanel")
        panel.setFixedWidth(280)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 28, 20, 28)
        panel_layout.setSpacing(14)

        # Stats cards
        self.pitch_card = self._stat_card("Pitch Count", "play-handball", "#4a9eff")
        self.mistake_card = self._stat_card("Mistake Count", "x-mark", "#e05555")
        self.accuracy_card = self._stat_card("Accuracy", "target", "#4ecb71")

        self.pitch_val = self.pitch_card.findChild(QLabel, "statValue")
        self.mistake_val = self.mistake_card.findChild(QLabel, "statValue")
        self.accuracy_val = self.accuracy_card.findChild(QLabel, "statValue")

        panel_layout.addWidget(self.pitch_card)
        panel_layout.addWidget(self.mistake_card)
        panel_layout.addWidget(self.accuracy_card)

        # Threshold warning label
        self.threshold_lbl = QLabel()
        self.threshold_lbl.setObjectName("thresholdWarning")
        self.threshold_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_lbl.setWordWrap(True)
        self.threshold_lbl.hide()
        panel_layout.addWidget(self.threshold_lbl)

        panel_layout.addStretch()

        # START button
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("sessionStartBtn")
        self.start_btn.setFixedHeight(60)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._handle_start)
        panel_layout.addWidget(self.start_btn)

        # END button
        self.end_btn = QPushButton("END")
        self.end_btn.setObjectName("sessionEndBtn")
        self.end_btn.setFixedHeight(60)
        self.end_btn.setEnabled(False)
        self.end_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.end_btn.clicked.connect(self._handle_end)
        panel_layout.addWidget(self.end_btn)

        root.addWidget(panel)

    # Stat card builder
    def _stat_card(self, title: str, icon_name: str, color: str) -> QWidget:
        card = QWidget()
        card.setObjectName("sessionStatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("statIcon")
        icon_lbl.setFixedSize(20, 20)
        icon_lbl.setPixmap(get_icon(icon_name, color=color, size=20).pixmap(20, 20))

        title_lbl = QLabel(title)
        title_lbl.setObjectName("statTitle")
        title_lbl.setStyleSheet(f"color: {color}; background: transparent;")

        title_row.addWidget(icon_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Value
        val = QLabel("0")
        val.setObjectName("statValue")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(val)

        return card

    # Feed
    def _show_idle_feed(self):
        self.feed_label.setText("Camera not started")
        self.feed_label.setObjectName("feedLabelIdle")
        self.feed_label.setPixmap(QPixmap())
        self.feed_label.style().unpolish(self.feed_label)
        self.feed_label.style().polish(self.feed_label)

    def update_frame(self, frame):
        """Called by live_capture to push a new frame (numpy BGR array)."""
        # import cv2

    # Stats update (called by live_capture)
    def update_stats(self, pitch_count: int, mistakes: int):
        """Update counters. Called from live_capture after each pitch."""
        self._pitch_count = pitch_count
        self._mistakes = mistakes
        accuracy = ((pitch_count - mistakes) / pitch_count * 100) if pitch_count > 0 else 0.0

        self.pitch_val.setText(str(pitch_count))
        self.mistake_val.setText(str(mistakes))
        self.accuracy_val.setText(f"{accuracy:.2f}%")

        # Block at threshold
        if self._threshold and pitch_count >= self._threshold:
            self._handle_threshold_reached()

    # Threshold
    def _handle_threshold_reached(self):
        if self._running:
            self._stop_capture()
            self.threshold_lbl.setText(
                f"⚠ Daily pitch limit of {self._threshold} reached. Session ended automatically."
            )
            self.threshold_lbl.show()
            self.start_btn.setEnabled(False)
            self.end_btn.setEnabled(True)

    def _check_threshold_on_start(self) -> bool:
        """Returns True if blocked."""
        if self._threshold and self._pitch_count >= self._threshold:
            self.threshold_lbl.setText(
                f"⚠ You've reached your daily pitch limit of {self._threshold}."
            )
            self.threshold_lbl.show()
            return True
        return False
    
    # Handlers
    def _handle_start(self):
        if self._check_threshold_on_start():
            return
    
        self.threshold_lbl.hide()
        self._running = True
        self.start_btn.setEnabled(False)
        self.end_btn.setEnabled(True)

        # Reset stats for new sessions
        self._pitch_count = 0
        self._mistakes = 0
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")

        # live_capture will be wired here
        # self._capture.start()

    def _handle_end(self):
        self._stop_capture()

        accuracy = (
            (self._pitch_count - self._mistakes) / self._pitch_count * 100
            if self._pitch_count > 0 else 0.0
        )

        dlg = SessionSummaryDialog(
            self.window(),
            pitch_count=self._pitch_count,
            mistakes=self._mistakes,
            accuracy=accuracy,
        )
        if dlg.exec():
            self._save_session(accuracy)

    def _stop_capture(self):
        self._running = False
        self.start_btn.setEnabled(True)
        self.end_btn.setEnabled(False)
        self._show_idle_feed()
        # self._capture.stop()

    def _save_session(self, accuracy: float):
        from src.db import get_connection
        conn = get_connection()
        conn.execute(
            """INSERT INTO sessions (user_id, total_pitch, mistakes, accuracy)
               VALUES (?, ?, ?, ?)""",
            (self.user_id, self._pitch_count, self._mistakes, round(accuracy, 2)),
        )
        conn.commit()
        conn.close()

        # Reset for next session
        self._pitch_count = 0
        self._mistakes = 0
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self.threshold_lbl.hide()

    # Lifecycle

    def refresh(self):
        """Called each time the page is navigated to."""
        from src.db import get_user_by_id
        user = get_user_by_id(self.user_id)
        if user:
            self._threshold = user["pitch_threshold"]

        # Re-check threshold in case it was updated in Account Settings
        if self._threshold and self._pitch_count >= self._threshold:
            self.threshold_lbl.setText(
                f"⚠ You've reached your daily pitch limit of {self._threshold}."
            )
            self.threshold_lbl.show()
            self.start_btn.setEnabled(False)
        else:
            self.threshold_lbl.hide()
            self.start_btn.setEnabled(True)
