from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

from src.utils.icons import get_icon
from src.utils.toast import toast_warning, toast_error, toast_success
from src.pitch_worker import PitchWorker

from .camera_manager import CameraMixin, LiveCameraCombo, CameraReconnectDialog
from .session_summary import SessionSummaryDialog

class StartSessionPage(QWidget, CameraMixin):
    _worker_done = pyqtSignal()      # internal: waiter thread → main thread
    session_started = pyqtSignal()   # emitted when START is pressed
    session_finished = pyqtSignal()  # emitted when summary dialog closes

    def __init__(self, user_id: int, ml_bundle=None):
        super().__init__()
        self.user_id = user_id
        self._ml_bundle = ml_bundle     # (model, scaler, threshold, joint_thresholds)
        self._running = False
        self._pitch_count = 0
        self._mistakes = 0
        self._threshold = None          # user's current token pool
        self._recommended_cap = None    # USA Baseball age-based cap
        self._used_today = 0            # pitches thrown today
        self._tokens_remaining = 0      # cap - used_today
        self._throwing_hand = "RHP"
        self._worker = None
        self._summary_dlg = None        # ref to open dialog for skeleton injection
        self._skeleton_path = ""        # path to last generated skeleton PNG
        self._end_pitch_count = 0       # snapshot at END time for dialog
        self._end_mistakes = 0          # snapshot at END time for dialog
        self._ending_worker = None      # strong ref held during async shutdown
        self._worker_state = ""         # last state emitted by PitchWorker
        self._camera_index        = -1  # -1 = no camera selected yet
        self._desired_camera_name = ""  # name user wants — survives index shifts
        self._active_camera_name  = ""  # name actually in use (set on START)
        self._camera_cache        = []  # cached (idx, name) pairs from last probe
        # Resolution recorded the first time the external webcam is used.
        # When the integrated camera is later selected, PitchWorker crops its
        # feed to this size so both cameras share the same effective FOV.
        self._reference_resolution: tuple | None = None  # (width, height) or None
        self._worker_done.connect(lambda: self._on_worker_finished(self._ending_worker))
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
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._show_idle_feed()
        feed_layout.addWidget(self.feed_label)
        root.addWidget(feed_wrapper, stretch=3)

        # Stats panel — width 13% of screen, clamped 180-240 px
        from PyQt6.QtWidgets import QApplication as _QApp
        _sw = _QApp.primaryScreen().availableGeometry().width()
        _panel_w = max(180, min(240, int(_sw * 0.13)))
        panel = QWidget()
        panel.setObjectName("sessionPanel")
        panel.setFixedWidth(_panel_w)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 18, 12, 18)
        panel_layout.setSpacing(8)

        # Stats cards
        self.pitch_card    = self._stat_card("Pitch Count",   "play-handball",  "#4a9eff")
        self.mistake_card  = self._stat_card("Mistake Count", "x-mark",         "#e05555")
        self.accuracy_card = self._stat_card("Accuracy",      "target",         "#4ecb71")

        self.pitch_val    = self.pitch_card.findChild(QLabel,    "statValue")
        self.mistake_val  = self.mistake_card.findChild(QLabel,  "statValue")
        self.accuracy_val = self.accuracy_card.findChild(QLabel, "statValue")

        panel_layout.addWidget(self.pitch_card)
        panel_layout.addWidget(self.mistake_card)
        panel_layout.addWidget(self.accuracy_card)

        # Pitches Left card
        self.token_card = self._stat_card("Pitches Left", "ball-baseball", "#f0a500")
        self.token_val  = self.token_card.findChild(QLabel, "statValue")
        panel_layout.addWidget(self.token_card)

        # Token status widget — alert icon + message
        self.token_status_widget = QWidget()
        self.token_status_widget.setObjectName("tokenStatusWidget")
        token_status_layout = QHBoxLayout(self.token_status_widget)
        token_status_layout.setContentsMargins(8, 8, 8, 8)
        token_status_layout.setSpacing(8)
        token_status_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._alert_icon_lbl = QLabel()
        self._alert_icon_lbl.setFixedSize(14, 14)
        self._alert_icon_lbl.setObjectName("tokenAlertIcon")

        self.token_status_lbl = QLabel()
        self.token_status_lbl.setObjectName("thresholdWarning")
        self.token_status_lbl.setWordWrap(True)

        token_status_layout.addWidget(
            self._alert_icon_lbl, alignment=Qt.AlignmentFlag.AlignTop
        )
        token_status_layout.addWidget(self.token_status_lbl)
        self.token_status_widget.hide()
        panel_layout.addWidget(self.token_status_widget)

        panel_layout.addStretch()

        # Camera guide card (built by CameraMixin)
        self.camera_guide_card = self._build_guide_card()
        panel_layout.addWidget(self.camera_guide_card)

        # Camera combo
        guide_toggle_row = QHBoxLayout()
        guide_toggle_row.setContentsMargins(0, 0, 0, 0)
        guide_toggle_row.setSpacing(6)

        self.camera_combo = LiveCameraCombo(parent=self)
        self.camera_combo.setObjectName("cameraCombo")
        self.camera_combo.setFixedHeight(28)
        self.camera_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.camera_combo.setToolTip("Select a camera — click 'Find Cameras' first")
        self.camera_combo.addItem("No camera selected", -1)
        self.camera_combo.setEnabled(False)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        guide_toggle_row.addWidget(self.camera_combo, stretch=1)
        panel_layout.addLayout(guide_toggle_row)

        # Find Cameras + Test row
        find_test_row = QHBoxLayout()
        find_test_row.setContentsMargins(0, 0, 0, 0)
        find_test_row.setSpacing(6)

        self.find_cam_btn = QPushButton("🔍  Find Cameras")
        self.find_cam_btn.setObjectName("findCameraBtn")
        self.find_cam_btn.setFixedHeight(28)
        self.find_cam_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_cam_btn.setAutoDefault(False)
        self.find_cam_btn.setDefault(False)
        self.find_cam_btn.setToolTip("Scan for connected cameras")
        self.find_cam_btn.clicked.connect(self._handle_find_cameras)
        find_test_row.addWidget(self.find_cam_btn, stretch=1)

        self.test_cam_btn = QPushButton("Test")
        self.test_cam_btn.setObjectName("testCameraBtn")
        self.test_cam_btn.setFixedHeight(28)
        self.test_cam_btn.setFixedWidth(46)
        self.test_cam_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_cam_btn.setAutoDefault(False)
        self.test_cam_btn.setDefault(False)
        self.test_cam_btn.setEnabled(False)
        self.test_cam_btn.setToolTip("Preview selected camera")
        self.test_cam_btn.clicked.connect(self._handle_test_camera)
        find_test_row.addWidget(self.test_cam_btn)
        panel_layout.addLayout(find_test_row)

        # START button
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("sessionStartBtn")
        self.start_btn.setFixedHeight(48)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setAutoDefault(False)
        self.start_btn.setDefault(False)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._handle_start)
        panel_layout.addWidget(self.start_btn)

        # END button
        self.end_btn = QPushButton("END")
        self.end_btn.setObjectName("sessionEndBtn")
        self.end_btn.setFixedHeight(48)
        self.end_btn.setEnabled(False)
        self.end_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.end_btn.setAutoDefault(False)
        self.end_btn.setDefault(False)
        self.end_btn.clicked.connect(self._handle_end)
        panel_layout.addWidget(self.end_btn)

        root.addWidget(panel)

    # Stat card builder (panel-local; SessionSummaryDialog has its own)
    def _stat_card(self, title: str, icon_name: str, color: str) -> QWidget:
        card = QWidget()
        card.setObjectName("sessionStatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(5)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("statIcon")
        icon_lbl.setFixedSize(14, 14)
        icon_lbl.setPixmap(get_icon(icon_name, color=color, size=14).pixmap(14, 14))

        title_lbl = QLabel(title)
        title_lbl.setObjectName("statTitle")
        title_lbl.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 11px;"
        )

        title_row.addWidget(icon_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        default = "0.00%" if title == "Accuracy" else "0"
        val = QLabel(default)
        val.setObjectName("statValue")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet("font-size: 28px; font-weight: 700; background: transparent;")
        layout.addWidget(val)

        return card

    # Stats update (called by PitchWorker)
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

        if self._running:
            pitches_live = max(0, self._tokens_remaining - pitch_count)
            self.token_val.setText(str(pitches_live))
            if pitches_live <= 0:
                self._handle_token_exhausted_mid_session()

    # Token system
    def _refresh_token_status(self):
        """Load today's token status from DB and update all token UI.

        Mirrors account_settings_page.py deduction logic:
            effective_max = recommended_cap - used_today
            tokens_remaining = min(threshold, effective_max)
        So if the user pitched 60 of their 120 cap, they have 60 left
        regardless of what their saved threshold is.
        """
        from src.db import get_pitch_token_status
        status = get_pitch_token_status(self.user_id)

        cap        = status["recommended_cap"]
        used_today = status["used_today"]
        threshold  = status["threshold"]
        remaining  = max(0, threshold - used_today)

        self._threshold        = threshold
        self._recommended_cap  = cap
        self._used_today       = used_today
        self._tokens_remaining = remaining

        self.token_val.setText(str(self._tokens_remaining))

        locked_status = {
            "threshold":       threshold,
            "recommended_cap": cap,
            "used_today":      used_today,
            "headroom":        status["headroom"],
            "locked":          self._tokens_remaining <= 0,
        }

        if locked_status["locked"]:
            self._apply_token_locked(locked_status)
        else:
            self.token_status_widget.hide()
            self.token_status_lbl.hide()
            if not self._running and self._camera_index >= 0:
                self.start_btn.setEnabled(True)

    def _apply_token_locked(self, status: dict):
        """Block START and show appropriate message when tokens are exhausted."""
        self.start_btn.setEnabled(False)

        cap      = status["recommended_cap"]
        headroom = status.get("headroom", 0)

        if headroom > 0:
            msg = (
                f"You still have {headroom} pitch{'es' if headroom != 1 else ''} left "
                f"before your daily cap of {cap}. "
                f"Go to Account Settings and raise your threshold."
            )
            icon_color = "#f0a500"
        else:
            msg = (
                f"You've reached your maximum daily pitch limit of {cap}. "
                f"Your pitches replenish at midnight."
            )
            icon_color = "#e05555"

        self._alert_icon_lbl.setPixmap(
            get_icon("alert-triangle", color=icon_color, size=14).pixmap(14, 14)
        )
        self.token_status_lbl.setText(msg)
        self.token_status_lbl.show()
        self.token_status_widget.show()

    def _handle_token_exhausted_mid_session(self):
        """Called during a live session when tokens hit zero mid-pitch."""
        if not self._running:
            return
        self._running = False
        self._end_pitch_count = self._pitch_count
        self._end_mistakes    = self._mistakes

        self._ending_worker = self._worker
        self._worker = None

        self._stop_capture()
        self.token_val.setText("0")
        self._launch_summary_waiter()

    def _check_tokens_on_start(self) -> bool:
        """Refresh token status, return True (blocked) if no tokens remain."""
        self._refresh_token_status()
        return self._tokens_remaining <= 0

    # Session handlers
    def _handle_start(self):
        if self._check_tokens_on_start():
            return

        if self._camera_index < 0:
            toast_warning(self, "Click 'Find Cameras' to detect a camera first.")
            return

        self.token_status_widget.hide()
        self._running = True

        self._active_camera_name = (
            self._desired_camera_name
            or next(
                (name for idx, name in self._camera_cache if idx == self._camera_index),
                f"Camera {self._camera_index}",
            )
        )

        self.start_btn.setEnabled(False)
        self.end_btn.setEnabled(True)
        if hasattr(self, "camera_combo"):
            self.camera_combo.setEnabled(False)
            self.camera_combo.set_session_live(True)
        if hasattr(self, "find_cam_btn"):
            self.find_cam_btn.setEnabled(False)
        if hasattr(self, "test_cam_btn"):
            self.test_cam_btn.setEnabled(False)
        self.session_started.emit()

        self._pitch_count  = 0
        self._mistakes     = 0
        self._worker_state = ""
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")

        self.feed_label.setText("⏳  Initializing camera and model...")
        self.feed_label.setObjectName("feedLabelIdle")
        self.feed_label.style().unpolish(self.feed_label)
        self.feed_label.style().polish(self.feed_label)

        feed_w = self.feed_label.width()
        feed_h = self.feed_label.height()
        if feed_w < 100 or feed_h < 100:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            feed_w = screen.width() - 300 - 280
            feed_h = screen.height() - 48

        is_external = self._camera_index != 0
        if is_external:
            try:
                import cv2 as _cv2
                _peek = _cv2.VideoCapture(self._camera_index, _cv2.CAP_MSMF)
                if _peek.isOpened():
                    _rw = int(_peek.get(_cv2.CAP_PROP_FRAME_WIDTH))
                    _rh = int(_peek.get(_cv2.CAP_PROP_FRAME_HEIGHT))
                    if _rw > 0 and _rh > 0:
                        self._reference_resolution = (_rw, _rh)
                _peek.release()
            except Exception:
                pass

        self._worker = PitchWorker(
            camera_id=self._camera_index,
            width=feed_w,
            height=feed_h,
            throwing_hand=self._throwing_hand,
            ml_bundle=self._ml_bundle,
            user_id=self.user_id,
            reference_resolution=self._reference_resolution if not is_external else None,
            parent=self,
        )
        self._worker.frame_ready.connect(self.update_frame)
        self._worker.stats_updated.connect(self.update_stats)
        self._worker.pitch_done.connect(self._on_pitch_done)
        self._worker.model_loaded.connect(self._on_model_loaded)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.session_ended.connect(self._on_session_ended)
        self._worker.state_changed.connect(self._on_worker_state_changed)
        self._worker.start()

    def _handle_end(self):
        print(f"[END] _handle_end called | _running={self._running} ending_worker={self._ending_worker}")
        if self._ending_worker is not None or not self._running:
            print("[END] guard hit — shutdown already in progress or not running")
            return

        self._running = False
        self.end_btn.setEnabled(False)
        self._show_idle_feed()
        self._update_camera_guide()

        self._end_pitch_count = self._pitch_count
        self._end_mistakes    = self._mistakes
        self._worker_state    = ""
        print(f"[END] pitches={self._end_pitch_count} mistakes={self._end_mistakes} worker={self._worker}")

        self._ending_worker = self._worker
        self._worker = None
        self._launch_summary_waiter()

    def _launch_summary_waiter(self):
        """Spawn a background thread that waits for the worker to exit, then
        posts _on_worker_finished to the main thread via QTimer.singleShot."""
        import threading as _threading

        def _wait_for_worker():
            print(f"[END waiter] thread started | worker={self._ending_worker}")
            w = self._ending_worker
            if w is not None and w.isRunning():
                print("[END waiter] calling w.stop() then w.wait()…")
                w.stop()
                w.wait()
                print("[END waiter] w.wait() returned")
            else:
                print("[END waiter] worker already stopped, posting immediately")
            print("[END waiter] emitting _worker_done signal")
            self._worker_done.emit()

        _threading.Thread(target=_wait_for_worker, daemon=True).start()
        print("[END] waiter thread launched")

    def _on_worker_finished(self, worker):
        """Called on the main thread once the worker QThread has fully exited."""
        print(f"[END] _on_worker_finished called | worker={worker}")
        skeleton_path = getattr(worker, "skeleton_path", "") if worker is not None else ""
        print(f"[END] skeleton path={skeleton_path!r}")

        self.start_btn.setEnabled(True)
        if hasattr(self, "camera_combo"):
            self.camera_combo.set_session_live(False)
            self.camera_combo.setEnabled(True)
        if hasattr(self, "find_cam_btn"):
            self.find_cam_btn.setEnabled(True)
        if hasattr(self, "test_cam_btn") and self._camera_index >= 0:
            self.test_cam_btn.setEnabled(True)
        self._update_camera_guide()

        if self._end_pitch_count == 0:
            self._refresh_token_status()
            self._show_idle_feed()
            self.end_btn.setEnabled(False)
            self._ending_worker = None
            self.session_finished.emit()
            return

        accuracy = (
            (self._end_pitch_count - self._end_mistakes) / self._end_pitch_count * 100
            if self._end_pitch_count > 0 else 0.0
        )

        dlg = SessionSummaryDialog(
            self,
            pitch_count=self._end_pitch_count,
            mistakes=self._end_mistakes,
            accuracy=accuracy,
            skeleton_path=skeleton_path,
        )

        self._summary_dlg = dlg
        if dlg.exec():
            self._save_session(accuracy)
            from src.db import get_pitch_token_status
            fresh = get_pitch_token_status(self.user_id)
            fresh_headroom = max(0, fresh["recommended_cap"] - fresh["used_today"])
            if self._tokens_remaining <= 0:
                locked_status = {
                    "threshold":       fresh["threshold"],
                    "recommended_cap": fresh["recommended_cap"],
                    "used_today":      fresh["used_today"],
                    "headroom":        fresh_headroom,
                    "locked":          True,
                }
                self._apply_token_locked(locked_status)

        self._summary_dlg   = None
        self._ending_worker = None
        self._refresh_token_status()
        self._show_idle_feed()
        self.end_btn.setEnabled(False)
        self.session_finished.emit()

    def _stop_capture(self):
        """Stop the worker synchronously (used by error/token-exhausted paths).

        For the normal END button flow use _handle_end, which stops the worker
        non-blockingly via the finished signal so the UI never freezes.
        """
        self._running = False
        self.end_btn.setEnabled(False)
        self._show_idle_feed()
        self._update_camera_guide()

        worker = self._worker
        self._worker = None
        if worker and worker.isRunning():
            worker.stop()
            finished = worker.wait(15_000)
            if not finished and worker.isRunning():
                worker.terminate()
                worker.wait(2000)

        self.start_btn.setEnabled(True)
        if hasattr(self, "camera_combo"):
            self.camera_combo.set_session_live(False)
            self.camera_combo.setEnabled(True)
        if hasattr(self, "find_cam_btn"):
            self.find_cam_btn.setEnabled(True)
        if hasattr(self, "test_cam_btn") and self._camera_index >= 0:
            self.test_cam_btn.setEnabled(True)
        self._refresh_token_status()

    def _save_session(self, accuracy: float):
        toast_success(self, "Session saved successfully.")
        skeleton_path = getattr(self._ending_worker, "skeleton_path", "") or None
        from src.db import get_connection, _manila_now
        conn = get_connection()
        conn.execute(
            """INSERT INTO sessions (user_id, date, total_pitch, mistakes, accuracy, path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (self.user_id, _manila_now(),
             self._pitch_count, self._mistakes, round(accuracy, 2),
             skeleton_path),
        )
        conn.commit()
        conn.close()

        self._pitch_count = 0
        self._mistakes    = 0
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self.token_status_widget.hide()
        self._refresh_token_status()

    # PitchWorker signal handlers
    def _on_model_loaded(self):
        self._show_idle_feed()

    def _on_pitch_done(self, result: dict):
        verdict = result.get("verdict", "")
        issue   = result.get("main_issue") or "None"
        mse     = result.get("mse", 0.0)
        pitch   = result.get("pitch_number", self._pitch_count)
        print(f"Pitch {pitch}: {verdict} | Issue: {issue} | MSE: {mse:.5f}")

    def _on_worker_error(self, message: str):
        """Called when PitchWorker hits a fatal error."""
        self._stop_capture()
        if message == "__camera_disconnected__":
            self._handle_camera_disconnected()
        else:
            toast_error(self, f"Camera error: {message}")

    def _on_worker_state_changed(self, state: str):
        self._worker_state = state

    def _on_session_ended(self, log_path: str):
        """Called when PitchWorker finishes writing its session log."""
        if log_path:
            print(f"Session log → {log_path}")

    # Lifecycle
    def refresh(self):
        """Called each time the page is navigated to."""
        from src.db import get_user_by_id
        user = get_user_by_id(self.user_id)
        if user:
            self._throwing_hand = user["throwing_hand"]
        self._update_camera_guide()
        self._refresh_token_status()
