from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QDialog, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

from src.utils.icons import get_icon
from src.utils.toast import toast_warning, toast_error, toast_success
from src.pitch_worker import PitchWorker

CAMERA_ID = 0

class SessionSummaryDialog(QDialog):
    """Summary popup shown after END is clicked."""
    def __init__(self, parent, pitch_count: int, mistakes: int, accuracy: float):
        super().__init__(parent)
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
    def __init__(self, user_id: int, ml_bundle=None):
        super().__init__()
        self.user_id = user_id
        self._ml_bundle = ml_bundle   # (model, scaler, threshold, joint_thresholds)
        self._running = False
        self._pitch_count = 0
        self._mistakes = 0
        self._threshold = None        # user's current token pool
        self._recommended_cap = None  # USA Baseball age-based cap
        self._used_today = 0          # pitches thrown today
        self._tokens_remaining = 0    # threshold - used_today 
        self._throwing_hand = "RHP"   
        self._worker = None
        self.setObjectName("contentPage")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        panel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        # Recommended threshold card — shows USA Baseball recommended daily limit
        self.rec_card = self._rec_card()
        panel_layout.addWidget(self.rec_card)

        # Pitches Left card — shows remaining pitches for today
        self.token_card = self._stat_card("Pitches Left", "ball-baseball", "#f0a500")
        self.token_val = self.token_card.findChild(QLabel, "statValue")
        panel_layout.addWidget(self.token_card)

        # Token status label — shown when locked or near limit
        self.token_status_lbl = QLabel()
        self.token_status_lbl.setObjectName("thresholdWarning")
        self.token_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.token_status_lbl.setWordWrap(True)
        self.token_status_lbl.hide()
        panel_layout.addWidget(self.token_status_lbl)

        panel_layout.addStretch()

        # Help icon button — always visible, toggles camera guide card
        guide_toggle_row = QHBoxLayout()
        guide_toggle_row.setContentsMargins(0, 0, 0, 0)
        guide_toggle_row.addStretch()
        self.guide_toggle_btn = QPushButton()
        self.guide_toggle_btn.setObjectName("guideToggleBtn")
        self.guide_toggle_btn.setFixedSize(28, 28)
        self.guide_toggle_btn.setIcon(get_icon("help", color="#555555", size=20))
        self.guide_toggle_btn.setIconSize(QSize(20, 20))
        self.guide_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.guide_toggle_btn.setToolTip("Show/hide camera setup guide")
        self.guide_toggle_btn.setAutoDefault(False)
        self.guide_toggle_btn.setDefault(False)
        self.guide_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus) 
        self.guide_toggle_btn.clicked.connect(self._toggle_guide_card)
        guide_toggle_row.addWidget(self.guide_toggle_btn)
        panel_layout.addLayout(guide_toggle_row)

        # Camera guide card
        self.camera_guide_card = self._build_guide_card()
        panel_layout.addWidget(self.camera_guide_card)

        # START button
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("sessionStartBtn")
        self.start_btn.setFixedHeight(60)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setAutoDefault(False)
        self.start_btn.setDefault(False)
        self.start_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.start_btn.clicked.connect(self._handle_start)
        panel_layout.addWidget(self.start_btn)

        # END button
        self.end_btn = QPushButton("END")
        self.end_btn.setObjectName("sessionEndBtn")
        self.end_btn.setFixedHeight(60)
        self.end_btn.setEnabled(False)
        self.end_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setAutoDefault(False)
        self.start_btn.setDefault(False)
        self.start_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.end_btn.clicked.connect(self._handle_end)
        panel_layout.addWidget(self.end_btn)

        root.addWidget(panel)

    # Camera guide card builder
    def _build_guide_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("cameraGuideCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header row: title + dismiss button
        header_row = QHBoxLayout()
        header_row.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        cam_icon = QLabel()
        cam_icon.setObjectName("guideIcon")
        cam_icon.setFixedSize(16, 16)
        cam_icon.setPixmap(
            get_icon("camera", color="#aaaaaa", size=16).pixmap(16, 16)
        )

        guide_title = QLabel("Camera Setup")
        guide_title.setObjectName("guideTitle")

        title_row.addWidget(cam_icon)
        title_row.addWidget(guide_title)
        title_row.addStretch()

        header_row.addLayout(title_row)
        layout.addLayout(header_row)

        # Divider
        div = QFrame()
        div.setObjectName("guideDivider")
        div.setFixedHeight(1)
        layout.addWidget(div)
        layout.addSpacing(4)

        # Registered as row
        reg_row = QHBoxLayout()
        reg_row.setSpacing(6)
        reg_lbl = QLabel("Registered as:")
        reg_lbl.setObjectName("guideLabel")
        self.hand_badge = QLabel("RHP")
        self.hand_badge.setObjectName("guideHandBadge")
        reg_row.addWidget(reg_lbl)
        reg_row.addWidget(self.hand_badge)
        reg_row.addStretch()
        layout.addLayout(reg_row)

        layout.addSpacing(2)

        # Camera position instruction
        self.camera_side_lbl = QLabel()
        self.camera_side_lbl.setObjectName("guideSideLabel")
        self.camera_side_lbl.setWordWrap(True)
        layout.addWidget(self.camera_side_lbl)

        layout.addSpacing(4)

        # Caution note — alert-triangle icon inherits guideCaution color
        caution_row = QHBoxLayout()
        caution_row.setSpacing(6)
        caution_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        alert_icon = QLabel()
        alert_icon.setObjectName("guideCautionIcon")
        alert_icon.setFixedSize(14, 14)
        alert_icon.setPixmap(
            get_icon("alert-triangle", color="#888888", size=14).pixmap(14, 14)
        )

        caution_lbl = QLabel("Your throwing arm must face the camera for accurate analysis.")
        caution_lbl.setObjectName("guideCaution")
        caution_lbl.setWordWrap(True)

        caution_row.addWidget(alert_icon, alignment=Qt.AlignmentFlag.AlignTop)
        caution_row.addWidget(caution_lbl) 
        layout.addLayout(caution_row)

        return card

    # Recommended threshold card builder
    def _rec_card(self) -> QWidget:
        """Small info card show the USA Baseball recommended daily threshold."""
        card = QWidget()
        card.setObjectName("recThresholdCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("recIcon")
        icon_lbl.setFixedSize(16, 16)
        icon_lbl.setPixmap(get_icon("target-arrow", color="#666666", size=16).pixmap(16, 16))

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        rec_title = QLabel("Recommended")
        rec_title.setObjectName("recTitle")

        self.rec_val_lbl = QLabel("—")
        self.rec_val_lbl.setObjectName("recValue")

        text_col.addWidget(rec_title)
        text_col.addWidget(self.rec_val_lbl)

        layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_col)
        layout.addStretch()

        return card

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

    # Camera guide toggle
    def _toggle_guide_card(self):
        """Toggle the camera guide card visibility and update help icon color."""
        if self.camera_guide_card.isVisible():
            self.camera_guide_card.hide()
            self.guide_toggle_btn.setIcon(get_icon("help", color="#555555", size=20))
        else:
            self.camera_guide_card.show()
            self.guide_toggle_btn.setIcon(get_icon("help", color="#aaaaaa", size=20))

    # Camera guide updater
    def _update_camera_guide(self):
        hand = self._throwing_hand
        if hand == "RHP":
            side = "3rd base side of the mound"
            color = "#4a9eff"
        else:
            side = "1st base side of the mound"
            color = "#f0a500"

        self.hand_badge.setText(hand)
        self.hand_badge.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;"
        )
        self.camera_side_lbl.setText(f"Position camera at:\n{side}")

        # Re-show the guide card (in case it was dismissed and user navigated away)
        self.camera_guide_card.show()
        self.guide_toggle_btn.setIcon(get_icon("help", color="#aaaaaa", size=20))

    # Feed
    def _show_idle_feed(self):
        self.feed_label.setText("Camera not started")
        self.feed_label.setObjectName("feedLabelIdle")
        self.feed_label.setPixmap(QPixmap())
        self.feed_label.style().unpolish(self.feed_label)
        self.feed_label.style().polish(self.feed_label)

    def update_frame(self, frame):
        """Called by live_capture to push a new frame (numpy BGR array)."""
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        scaled = img.scaled(
            self.feed_label.width(),
            self.feed_label.height(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.feed_label.setObjectName("feedLabel")
        self.feed_label.setPixmap(QPixmap.fromImage(scaled))

    # Stats update (called by live_capture)
    def update_stats(self, pitch_count: int, mistakes: int):
        """Update counters. Called from live_capture after each pitch."""
        self._pitch_count = pitch_count
        self._mistakes = mistakes
        accuracy = (
            (pitch_count - mistakes) / pitch_count * 100
            if pitch_count > 0 else 0.0
        )
        self.pitch_val.setText(str(pitch_count))
        self.mistake_val.setText(str(mistakes))
        self.accuracy_val.setText(f"{accuracy:.2f}%")

        # Block at threshold
        # Decrement token display live during session
        tokens_live = max(0, self._tokens_remaining - pitch_count)
        self.token_val.setText(str(tokens_live))

        # Check if tokens exhausted mid-session
        if self._threshold and pitch_count >= self._tokens_remaining:
            self._handle_token_exhausted_mid_session()

    # Token system
    def _refresh_token_status(self):
        """Load today's token status from DB and update all token UI."""
        from src.db import get_pitch_token_status
        status = get_pitch_token_status(self.user_id)

        self._threshold = status["threshold"]
        self._recommended_cap = status["recommended_cap"]
        self._used_today = status["used_today"]
        self._tokens_remaining = status["remaining"]

        # Update recommended threshold card
        self.rec_val_lbl.setText(
            f"{status['recommended_cap']} pitches/day"
            if status["recommended_cap"] else "—"
        )

        # Update pitches left card value
        self.token_val.setText(str(self._tokens_remaining))

        if status["locked"]:
            self._apply_token_locked(status)
        else:
            self.token_status_lbl.hide()
            if not self._running:
                self.start_btn.setEnabled(True)

    def _apply_token_locked(self, status: dict):
        """Block START and show appropriate message when tokens are exhausted."""
        self.start_btn.setEnabled(False)
        headroom = status["headroom"]
        threshold = status["threshold"]
        cap = status["recommended_cap"]

        if headroom > 0:
            msg = (
                f"⚠ You've used all {threshold} of your pitching tokens today.\n"
                f"You can still add {headroom} more — your recommended daily "
                f"cap is {cap}. Increase your threshold in Account Settings."
            )
        else:
            msg = (
                f"⚠ You've reached your maximum daily pitch limit of {cap}. "
                f"Come back tomorrow to pitch again."
            )
        self.token_status_lbl.setText(msg)
        self.token_status_lbl.show()

    def _handle_token_exhausted_mid_session(self):
        """Called during a live session when tokens hit zero mid-pitch."""
        if self._running:
            self._stop_capture()
            headroom = max(0, (self._recommended_cap or 0) - (self._threshold or 0))
            status = {
                "threshold": self._threshold,
                "recommended_cap": self._recommended_cap,
                "headroom": headroom,
            }
            self._apply_token_locked(status)
            self.end_btn.setEnabled(True)

    def _check_tokens_on_start(self) -> bool:
        """Refresh token status, return True (blocked) if no tokens remain."""
        self._refresh_token_status()
        return self._tokens_remaining <= 0
    
    # Handlers
    def _handle_start(self):
        if self._check_tokens_on_start():
            return
    
        self.token_status_lbl.hide()
        self.camera_guide_card.hide()
        self._running = True
        self.start_btn.setEnabled(False)
        self.end_btn.setEnabled(True)

        # Reset stats for new sessions
        self._pitch_count = 0
        self._mistakes = 0
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")

        # Show loading indicator immediately while worker initializes
        self.feed_label.setText("⏳  Initializing camera and model...")
        self.feed_label.setObjectName("feedLabelIdle")
        self.feed_label.style().unpolish(self.feed_label)
        self.feed_label.style().polish(self.feed_label)

        feed_w = self.feed_label.width()
        feed_h = self.feed_label.height()

        # Fallback: derive from screen geometry if label hasn't rendered yet
        if feed_w < 100 or feed_h < 100:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            feed_w = screen.width() - 300 - 280
            feed_h = screen.height() - 48

        # Start PitchWorker
        self._worker = PitchWorker(
            camera_id=CAMERA_ID,
            width=feed_w,
            height=feed_h,
            throwing_hand=self._throwing_hand,
            ml_bundle=self._ml_bundle,
            parent=self,
        )
        self._worker.frame_ready.connect(self.update_frame)
        self._worker.stats_updated.connect(self.update_stats)
        self._worker.pitch_done.connect(self._on_pitch_done)
        self._worker.model_loaded.connect(self._on_model_loaded)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.session_ended.connect(self._on_session_ended)
        self._worker.start()

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
        self._update_camera_guide()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()
            self._worker = None
        # Re-evaluate token lock state after session ends
        self._refresh_token_status()

    def _save_session(self, accuracy: float):
        from src.db import get_connection, _manila_now
        conn = get_connection()
        conn.execute(
            """INSERT INTO sessions (user_id, date, total_pitch, mistakes, accuracy)
               VALUES (?, ?, ?, ?, ?)""",
            (self.user_id, _manila_now(),
             self._pitch_count, self._mistakes, round(accuracy, 2)),
        )
        conn.commit()
        conn.close()

        # Reset for next session
        self._pitch_count = 0
        self._mistakes = 0
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self.token_status_lbl.hide()

        # Refresh token card immediately after save so it reflects pitches used
        self._refresh_token_status()

    # PitchWorker signal handlers
    def _on_model_loaded(self):
        self._show_idle_feed()

    def _on_pitch_done(self, result: dict):
        """Receives full pitch result after each pitch is analyzed."""
        verdict = result.get("verdict", "")
        issue = result.get("main_issue") or "None"
        mse = result.get("mse", 0.0)
        pitch = result.get("pitch_number", self._pitch_count)
        print(f"Pitch {pitch}: {verdict} | Issue: {issue} | MSE: {mse:.5f}")

    def _on_worker_error(self, message: str):
        """Called when PitchWorker hits a fatal error."""
        self._stop_capture()
        toast_error(self, f"Camera error: {message}")

    def _on_session_ended(self, log_path: str):
        """Called when PitchWorker finishes — log path is ready."""
        toast_success(self, f"Session log saved.")
        print(f"Session log → {log_path}")

    # Lifecycle
    def refresh(self):
        """Called each time the page is navigated to."""
        from src.db import get_user_by_id
        user = get_user_by_id(self.user_id)
        if user:
            self._throwing_hand = user["throwing_hand"]

        # Update camera guide for current throwing hand
        self._update_camera_guide()

        # Refresh token status — handles lock/unlock and token card value.
        # Daily reset is automatic: get_pitch_token_status queries today's
        # sessions from the DB, so tokens reset naturally each new day.
        self._refresh_token_status()
