from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QDialog, QGridLayout, QFrame,
    QComboBox,
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

from src.utils.icons import get_icon
from src.utils.toast import toast_warning, toast_error, toast_success
from src.pitch_worker import PitchWorker

CAMERA_ID = 0

class SessionSummaryDialog(QDialog):
    """
    Session summary — fills the camera feed area:
        Left  : joint-severity skeleton PNG, large and readable
        Right : session stats, worst joint callout, save button

    Sized to match the feed label geometry so it overlays it exactly.
    """
    # Fallback size used when parent geometry is unavailable
    _W_DEFAULT = 940
    _H_DEFAULT = 620

    def __init__(self, parent, pitch_count: int, mistakes: int, accuracy: float,
                 skeleton_path: str):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("summaryRoot")
        self._pitch_count = pitch_count
        self._mistakes = mistakes
        self._accuracy = accuracy
        self._skeleton_path = skeleton_path
        self._build_ui()
        self._size_and_position(parent)

    def _size_and_position(self, parent):
        """Match the dialog to the parent's feed_label geometry."""
        try:
            feed = parent.feed_label
            tl = feed.mapToGlobal(feed.rect().topLeft())
            w, h = feed.width(), feed.height()
        except Exception:
            w, h = self._W_DEFAULT, self._H_DEFAULT
            from PyQt6.QtWidgets import QApplication
            sg = QApplication.primaryScreen().availableGeometry()
            tl = sg.topLeft()
            tl.setX(tl.x() + (sg.width() - w) // 2)
            tl.setY(tl.y() + (sg.height() - h) // 2)
        self.setFixedSize(w, h)
        self.move(tl)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._load_skeleton)

    def _load_skeleton(self):
        import os
        path = self._skeleton_path
        if path and os.path.exists(path):
            pixmap = QPixmap(path) 
            if not pixmap.isNull():
                # Fill the skeleton label as large as possible
                tw = self.skeleton_lbl.width()
                th = self.skeleton_lbl.height()
                scaled = pixmap.scaled(
                    tw, th,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.skeleton_lbl.setPixmap(scaled)
                self.skeleton_pending_lbl.hide()
                return
        # Replace text label with icon + message using the app's get_icon helper
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(16, 16)
        icon_lbl.setStyleSheet("background: transparent;")
        try:
            icon_lbl.setPixmap(
                get_icon("alert-triangle", color="#e05555", size=16).pixmap(16, 16)
            )
        except Exception:
            pass
        self.skeleton_pending_lbl.setText("Skeleton image unavailable")
        # Insert icon just before the text label in the parent layout
        parent_layout = self.skeleton_pending_lbl.parentWidget().layout()
        idx = parent_layout.indexOf(self.skeleton_pending_lbl)
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(icon_lbl)
        row.addWidget(self.skeleton_pending_lbl)
        parent_layout.insertWidget(idx, row_w)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left: skeleton panel
        self.skeleton_panel = QWidget()
        self.skeleton_panel.setObjectName("summarySkeletonPanel")
        sk_layout = QVBoxLayout(self.skeleton_panel)
        sk_layout.setContentsMargins(20, 18, 12, 16)
        sk_layout.setSpacing(6)

        self.skeleton_lbl = QLabel()
        self.skeleton_lbl.setObjectName("summarySkeletonImage")
        self.skeleton_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.skeleton_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        sk_layout.addWidget(self.skeleton_lbl, stretch=1)

        # Pending label overlaid below image slot
        self.skeleton_pending_lbl = QLabel("⏳  Generating joint severity map…")
        self.skeleton_pending_lbl.setObjectName("summarySubtitle")
        self.skeleton_pending_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sk_layout.addWidget(self.skeleton_pending_lbl)

        root.addWidget(self.skeleton_panel, stretch=65)

        # Divider
        div = QFrame()
        div.setObjectName("summaryDivider")
        div.setFrameShape(QFrame.Shape.VLine)
        root.addWidget(div)

        # Right: stats panel
        right = QWidget()
        right.setObjectName("summaryStatsPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(32, 32, 32, 28)
        rl.setSpacing(0)

        # Session ended badge
        badge = QLabel("SESSION COMPLETE")
        badge.setObjectName("summaryBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignLeft)
        rl.addWidget(badge)

        rl.addSpacing(10)

        # Title
        title = QLabel("Session Summary")
        title.setObjectName("summaryTitle")
        rl.addWidget(title)

        subtitle = QLabel("Here's how you performed across all pitches.")
        subtitle.setObjectName("summarySubtitle")
        subtitle.setWordWrap(True)
        rl.addWidget(subtitle)

        rl.addSpacing(28)

        # Stat cards: stacked vertically for the taller layout
        for label, value, color in [
            ("Pitch Count", str(self._pitch_count), "#4a9eff"),
            ("Mistakes", str(self._mistakes), "#e05555"),
            ("Accuracy", f"{self._accuracy:.2f}%", "#4ecb71"),
        ]:
            rl.addWidget(self._stat_card(label, value, color))
            rl.addSpacing(10)
 
        rl.addStretch()
 
        # Accuracy note card 
        acc_int = int(self._accuracy)
        if acc_int >= 80:
            band_color = "#4ecb71"
            band_icon = "star-filled"
            band_head = "Great session!"
            band_body = "Your mechanics are on point. Keep up the consistency."
        elif acc_int >= 50:
            band_color = "#f0a500"
            band_icon = "star-half"
            band_head = "Room to improve."
            band_body = "Review joint feedback and focus on flagged areas."
        else:
            band_color = "#e05555"
            band_icon = "star"
            band_head = "Focus on mechanics."
            band_body = "Several joints exceeded threshold, prioritize form next session."

        note_card = QWidget()
        note_card.setObjectName("summaryNoteCard")
        note_card.setStyleSheet(
            f"QWidget#summaryNoteCard {{"
            f" background: rgba(255,255,255,0.03);"
            f" border: 1px solid {band_color}55;"
            f" border-left: 3px solid {band_color};"
            f" border-radius: 8px;"
            f"}}"
        )
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(14, 12, 14, 12)
        note_layout.setSpacing(5)

        note_head_row = QHBoxLayout()
        note_head_row.setSpacing(8)
        note_head_row.setContentsMargins(0, 0, 0, 0)

        star_lbl = QLabel()
        star_lbl.setFixedSize(15, 15)
        star_lbl.setStyleSheet("background: transparent; border: none;")
        try:
            star_lbl.setPixmap(get_icon(band_icon, color=band_color, size=15).pixmap(15, 15))
        except Exception:
            pass
        note_head_row.addWidget(star_lbl)

        note_head = QLabel(band_head)
        note_head.setStyleSheet(
            f"color: {band_color}; background: transparent; "
            f"font-size: 13px; font-weight: 700; border: none;"
        )
        note_head_row.addWidget(note_head)
        note_head_row.addStretch()

        note_body = QLabel(band_body)
        note_body.setWordWrap(True)
        note_body.setStyleSheet(
            "color: #777777; background: transparent; "
            "font-size: 12px; border: none;"
        )
        note_layout.addLayout(note_head_row)
        note_layout.addWidget(note_body)
        rl.addWidget(note_card)
 
        rl.addSpacing(16)

        # Save button
        save_btn = QPushButton("Save and Close")
        save_btn.setObjectName("summarySaveBtn")
        save_btn.setFixedHeight(52)
        save_btn.setAutoDefault(False)
        save_btn.setDefault(False)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        rl.addWidget(save_btn)

        root.addWidget(right, stretch=35)

    def _stat_card(self, label: str, value: str, color: str) -> QWidget:
        card = QWidget()
        card.setObjectName("summaryStatCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(0)

        lbl = QLabel(label)
        lbl.setObjectName("summaryStatLabel")

        val_lbl = QLabel(value)
        val_lbl.setObjectName("summaryStatValue")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setStyleSheet(f"color: {color}; background: transparent;")

        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val_lbl)
        return card
    
class LiveCameraCombo(QComboBox):
    """QComboBox backed by a background-probed camera cache.

    showPopup() populates instantly from the cache (zero main-thread
    blocking), then kicks off a background re-probe so the next open
    is always fresh. Never probes during a live session.
    """

    def __init__(self, parent=None, populate_fn=None, refresh_fn=None):
        super().__init__(parent)
        self._populate_fn     = populate_fn
        self._refresh_fn      = refresh_fn
        self._is_session_live = False

    def set_session_live(self, live: bool):
        self._is_session_live = live

    def showPopup(self):
        """Show cached list instantly, then trigger background refresh."""
        if not self._is_session_live:
            if self._populate_fn:
                self._populate_fn()
            if self._refresh_fn:
                self._refresh_fn()
        super().showPopup()


class CameraReconnectDialog(QDialog):
    """Shown when the camera disconnects mid-session.
 
    Lets the user pick a working camera from a fresh probe, then
    dismisses so start_session_page can start a clean new session.
    Always starts fresh — no attempt to resume incomplete pitch data.
    """
 
    def __init__(self, parent, lost_camera_index: int, lost_camera_name: str = ""):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("reconnectDialog")
        self._selected_index = 0
        self._lost_index = lost_camera_index
        self._lost_name = lost_camera_name
        self._build_ui()
        self.setFixedSize(440, 270)
        self._center_on_parent()
 
    def _center_on_parent(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.x() + (screen.width() - self.width()) // 2,
            screen.y() + (screen.height() - self.height()) // 2,
        )
 
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
 
        # Header — alert-triangle icon + title
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        alert_icon = QLabel()
        alert_icon.setFixedSize(22, 22)
        alert_icon.setStyleSheet("background: transparent;")
        try:
            alert_icon.setPixmap(
                get_icon("alert-triangle", color="#e05555", size=22).pixmap(22, 22)
            )
        except Exception:
            pass
        title_row.addWidget(alert_icon)

        title = QLabel("Camera Disconnected")
        title.setObjectName("reconnectTitle")
        title.setStyleSheet(
            "color: #e05555; font-size: 18px; font-weight: 700; background: transparent;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        root.addLayout(title_row)

        lost_name = self._lost_name or f"Camera {self._lost_index}"
        sub = QLabel(
            f"\"{lost_name}\" was lost mid-session. "
            "The current session has been discarded. Select a working "
            "camera below to start a fresh session."
        )
        sub.setObjectName("reconnectSub")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #888888; font-size: 12px; background: transparent;")
        root.addWidget(sub)
 
        # Camera selector
        self._combo = QComboBox()
        self._combo.setObjectName("cameraCombo")
        self._combo.setFixedHeight(32)
        self._probe_cameras()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        root.addWidget(self._combo)
 
        root.addStretch()
 
        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
 
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("reconnectCancelBtn")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 6px;"
            "color: #888888; font-size: 13px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
 
        ok_btn = QPushButton("Use This Camera")
        ok_btn.setObjectName("reconnectOkBtn")
        ok_btn.setFixedHeight(40)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(
            "background: #1a3a1a; border: 1px solid #2a5a2a; border-radius: 6px;"
            "color: #4ecb71; font-size: 13px; font-weight: 600;"
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
 
        root.addLayout(btn_row)
 
    def _probe_cameras(self):
        """Probe cameras, fetch real device names via StartSessionPage._get_camera_names,
        and populate combo — excluding or marking the disconnected device."""
        import cv2 as _cv2
        self._combo.clear()

        # Use the same PnP name resolution as the main camera combo
        device_names = StartSessionPage._get_camera_names()

        found = []
        for idx in range(8):
            cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    found.append(idx)
                cap.release()

        if not found:
            self._combo.addItem("No cameras detected", -1)
        else:
            for pos, idx in enumerate(found):
                name = device_names[pos] if pos < len(device_names) else f"Camera {idx}"
                if idx == self._lost_index:
                    label = f"{name}"
                else:
                    label = name
                self._combo.addItem(label, idx)
            # Auto-select first camera that isn't the lost one
            for i in range(self._combo.count()):
                if self._combo.itemData(i) != self._lost_index:
                    self._combo.setCurrentIndex(i)
                    self._selected_index = self._combo.itemData(i)
                    break
 
    def _on_combo_changed(self, i: int):
        idx = self._combo.itemData(i)
        if idx is not None and idx >= 0:
            self._selected_index = idx
 
    def selected_camera_index(self) -> int:
        return self._selected_index

    def selected_camera_name(self) -> str:
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == self._selected_index:
                # Strip the disconnected suffix if present
                return self._combo.itemText(i).replace("  ⚠  (disconnected)", "").strip()
        return f"Camera {self._selected_index}"

class StartSessionPage(QWidget):
    _worker_done = pyqtSignal()      # internal: waiter thread → main thread
    session_started = pyqtSignal()   # emitted when START is pressed
    session_finished = pyqtSignal()  # emitted when summary dialog closes

    def __init__(self, user_id: int, ml_bundle=None):
        super().__init__()
        self.user_id = user_id
        self._ml_bundle = ml_bundle    # (model, scaler, threshold, joint_thresholds)
        self._running = False
        self._pitch_count = 0
        self._mistakes = 0
        self._threshold = None         # user's current token pool
        self._recommended_cap = None   # USA Baseball age-based cap
        self._used_today = 0           # pitches thrown today
        self._tokens_remaining = 0     # threshold - used_today 
        self._throwing_hand = "RHP"   
        self._worker = None
        self._summary_dlg = None       # ref to open dialog for skeleton injection
        self._skeleton_path = ""       # path to last generated skeleton PNG
        self._end_pitch_count = 0      # snapshot at END time for dialog
        self._end_mistakes = 0         # snapshot at END time for dialog
        self._ending_worker = None     # strong ref held during async shutdown
        self._worker_state = ""        # last state emitted by PitchWorker
        self._camera_index        = 0   # active camera device index
        self._desired_camera_name = ""  # name user wants — survives index shifts
        self._active_camera_name  = ""  # name actually in use (set on START)
        self._camera_cache        = []  # cached (idx, name) pairs from last probe
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
        self.pitch_card = self._stat_card("Pitch Count", "play-handball", "#4a9eff")
        self.mistake_card = self._stat_card("Mistake Count", "x-mark", "#e05555")
        self.accuracy_card = self._stat_card("Accuracy", "target", "#4ecb71")

        self.pitch_val = self.pitch_card.findChild(QLabel, "statValue")
        self.mistake_val = self.mistake_card.findChild(QLabel, "statValue")
        self.accuracy_val = self.accuracy_card.findChild(QLabel, "statValue")

        panel_layout.addWidget(self.pitch_card)
        panel_layout.addWidget(self.mistake_card)
        panel_layout.addWidget(self.accuracy_card)
        # Pitches Left card — shows remaining pitches for today
        self.token_card = self._stat_card("Pitches Left", "ball-baseball", "#f0a500")
        self.token_val = self.token_card.findChild(QLabel, "statValue")
        panel_layout.addWidget(self.token_card)

        # Token status widget — alert-triangle icon + message label
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

        token_status_layout.addWidget(self._alert_icon_lbl,
                                      alignment=Qt.AlignmentFlag.AlignTop)
        token_status_layout.addWidget(self.token_status_lbl)
        self.token_status_widget.hide()
        panel_layout.addWidget(self.token_status_widget)

        panel_layout.addStretch()

        self.camera_guide_card = self._build_guide_card()
        panel_layout.addWidget(self.camera_guide_card)

        self.camera_combo = LiveCameraCombo(
            parent=self,
            populate_fn=self._populate_camera_combo,
            refresh_fn=self._refresh_camera_cache,
        )
        self.camera_combo.setObjectName("cameraCombo")
        self.camera_combo.setFixedHeight(28)
        self.camera_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.camera_combo.setToolTip("Select camera source — opens fresh list on click")
        # Initial background probe; combo shows "No cameras found" until done
        self._refresh_camera_cache()
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        panel_layout.addWidget(self.camera_combo)

        # START button
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("sessionStartBtn")
        self.start_btn.setFixedHeight(48)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setAutoDefault(False)
        self.start_btn.setDefault(False)
        self.start_btn.clicked.connect(self._handle_start)
        panel_layout.addWidget(self.start_btn)

        # END button
        self.end_btn = QPushButton("END")
        self.end_btn.setObjectName("sessionEndBtn")
        self.end_btn.setFixedHeight(48)
        self.end_btn.setEnabled(False)
        self.end_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setAutoDefault(False)
        self.start_btn.setDefault(False)
        self.end_btn.clicked.connect(self._handle_end)
        panel_layout.addWidget(self.end_btn)

        root.addWidget(panel)

    # Camera guide card builder
    def _build_guide_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("cameraGuideCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # Header row: title + dismiss button
        header_row = QHBoxLayout()
        header_row.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setSpacing(5)

        cam_icon = QLabel()
        cam_icon.setObjectName("guideIcon")
        cam_icon.setFixedSize(13, 13)
        cam_icon.setPixmap(
            get_icon("camera", color="#aaaaaa", size=13).pixmap(13, 13)
        )

        guide_title = QLabel("Camera Setup")
        guide_title.setObjectName("guideTitle")
        guide_title.setStyleSheet("font-size: 11px; background: transparent;")

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
        layout.addSpacing(2)

        # Registered as row
        reg_row = QHBoxLayout()
        reg_row.setSpacing(4)
        reg_lbl = QLabel("Registered as:")
        reg_lbl.setObjectName("guideLabel")
        reg_lbl.setStyleSheet("font-size: 10px; background: transparent;")
        self.hand_badge = QLabel("RHP")
        self.hand_badge.setObjectName("guideHandBadge")
        reg_row.addWidget(reg_lbl)
        reg_row.addWidget(self.hand_badge)
        reg_row.addStretch()
        layout.addLayout(reg_row)

        # Camera position instruction
        self.camera_side_lbl = QLabel()
        self.camera_side_lbl.setObjectName("guideSideLabel")
        self.camera_side_lbl.setWordWrap(True)
        self.camera_side_lbl.setStyleSheet("font-size: 10px; background: transparent;")
        layout.addWidget(self.camera_side_lbl)

        layout.addSpacing(2)

        # Caution note
        caution_row = QHBoxLayout()
        caution_row.setSpacing(4)
        caution_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        alert_icon = QLabel()
        alert_icon.setObjectName("guideCautionIcon")
        alert_icon.setFixedSize(11, 11)
        alert_icon.setPixmap(
            get_icon("alert-triangle", color="#888888", size=11).pixmap(11, 11)
        )
        alert_icon.setStyleSheet("background: transparent;")

        caution_lbl = QLabel("Your throwing arm must face the camera for accurate analysis.")
        caution_lbl.setObjectName("guideCaution")
        caution_lbl.setWordWrap(True)
        caution_lbl.setStyleSheet("font-size: 10px; background: transparent;")

        caution_row.addWidget(alert_icon, alignment=Qt.AlignmentFlag.AlignTop)
        caution_row.addWidget(caution_lbl)
        layout.addLayout(caution_row)

        return card

    # Stat card builder
    def _stat_card(self, title: str, icon_name: str, color: str) -> QWidget:
        card = QWidget()
        card.setObjectName("sessionStatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # Title row
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

        # Value — inline font size so it scales with panel width
        default = "0.00%" if title == "Accuracy" else "0"
        val = QLabel(default)
        val.setObjectName("statValue")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet("font-size: 28px; font-weight: 700; background: transparent;")
        layout.addWidget(val)

        return card

    # Camera guide toggle
    @staticmethod
    def _get_camera_names() -> list:
        """Return ordered list of DirectShow video device names.

        Strategy — try three queries in order, merge unique results:
        1. Get-PnpDevice -Class Camera   (physical webcams, Win10/11)
        2. Get-PnpDevice -Class Image    (some USB cameras, scanners excluded)
        3. Win32_PnPEntity name filter   (catches OBS Virtual Camera which
           registers as a KsProxy device, not under Camera/Image class)
        Falls back to empty list if PowerShell is unavailable."""
        import subprocess, json as _json
        names = []
        seen = set()

        queries = [
            # Standard webcams
            ("Get-PnpDevice -Class Camera -Status OK | "
             "Select-Object -ExpandProperty FriendlyName | "
             "ConvertTo-Json -Compress"),
            # Image class (catches some webcams + virtual cameras)
            ("Get-PnpDevice -Class Image -Status OK | "
             "Select-Object -ExpandProperty FriendlyName | "
             "ConvertTo-Json -Compress"),
            # Broad WMI name filter — catches OBS Virtual Camera
            ("Get-WmiObject Win32_PnPEntity | "
             "Where-Object { $_.Name -match 'camera|webcam|video|obs' } | "
             "Select-Object -ExpandProperty Name | "
             "ConvertTo-Json -Compress"),
        ]

        for ps in queries:
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, timeout=5
                )
                raw = result.stdout.strip()
                if not raw:
                    continue
                parsed = _json.loads(raw)
                items = [parsed] if isinstance(parsed, str) else list(parsed)
                for name in items:
                    key = name.strip().lower()
                    if key and key not in seen:
                        seen.add(key)
                        names.append(name.strip())
            except Exception:
                continue

        return names

    def _populate_camera_combo(self):
        """Fill the combo from _camera_cache and restore the user's desired camera.

        Selection priority:
          1. _desired_camera_name — the user's explicit choice (survives index shifts)
          2. _camera_index — fallback if name not found in new cache
        Never overwrites _desired_camera_name so it always reflects user intent.
        """
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        cache = self._camera_cache

        if not cache:
            self.camera_combo.addItem("No cameras found", -1)
            self.camera_combo.blockSignals(False)
            return

        for idx, name in cache:
            label = f"{name} (default)" if idx == 0 else name
            self.camera_combo.addItem(label, idx)

        # 1. Try to match by desired name
        selected = False
        if self._desired_camera_name:
            for i in range(self.camera_combo.count()):
                item_idx = self.camera_combo.itemData(i)
                item_name = next((n for ix, n in cache if ix == item_idx), "")
                if item_name == self._desired_camera_name:
                    self.camera_combo.setCurrentIndex(i)
                    self._camera_index = item_idx   # sync index to new position
                    selected = True
                    break

        # 2. Fall back to index match
        if not selected:
            for i in range(self.camera_combo.count()):
                if self.camera_combo.itemData(i) == self._camera_index:
                    self.camera_combo.setCurrentIndex(i)
                    # Also set desired name so future probes select correctly
                    item_idx = self.camera_combo.itemData(i)
                    self._desired_camera_name = next(
                        (n for ix, n in cache if ix == item_idx), ""
                    )
                    break

        self.camera_combo.blockSignals(False)

    def _refresh_camera_cache(self):
        """Probe cameras in a daemon thread; update cache + repopulate combo
        on the main thread when done. Uses isOpened() only — no cap.read()."""
        import threading as _t, cv2 as _cv2
        def _probe():
            device_names = self._get_camera_names()
            found = []
            for idx in range(8):
                cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
                if cap.isOpened():
                    found.append(idx)
                    cap.release()
            cache = []
            for pos, idx in enumerate(found):
                name = (device_names[pos]
                        if pos < len(device_names) else f"Camera {idx}")
                cache.append((idx, name))
            self._camera_cache = cache
            QTimer.singleShot(0, self._populate_camera_combo)
        _t.Thread(target=_probe, daemon=True).start()

    def _on_camera_changed(self, combo_idx: int):
        """Update camera index and desired name — takes effect on next START."""
        idx = self.camera_combo.itemData(combo_idx)
        if idx is not None and idx >= 0:
            self._camera_index = idx
            name = next((n for ix, n in self._camera_cache if ix == idx), "")
            if name:
                self._desired_camera_name = name   # user's explicit choice


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
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
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

        # Decrement token display live during session only
        if self._running:
            pitches_live = max(0, self._tokens_remaining -  pitch_count)
            self.token_val.setText(str(pitches_live))
            # Exhaust check: session pitches have consumed all remaining tokens
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
        from src.db import get_pitch_token_status, get_pitches_used_today
        status = get_pitch_token_status(self.user_id)

        cap = status["recommended_cap"]
        used_today = status["used_today"]
        threshold = status["threshold"]

        # effective_max mirrors account_settings deduction logic exactly
        effective_max = max(0, cap - used_today) 

        # Tokens remaining = what the user can actually still pitch today
        # clamped to both their saved threshold and the effective_max
        self._threshold = threshold
        self._recommended_cap = cap
        self._used_today = used_today
        self._tokens_remaining = min(threshold, effective_max)

        # Update pitches left card
        self.token_val.setText(str(self._tokens_remaining))

        # Build a status dict consistent with _apply_token_locked expectations
        locked_status = {
            "threshold": threshold,
            "recommended_cap": cap,
            "used_today": used_today,
            "headroom": max(0, effective_max - threshold),
            "locked": self._tokens_remaining <= 0,
        }

        if locked_status["locked"]:
            self._apply_token_locked(locked_status)
        else:
            self.token_status_lbl.hide()
            if not self._running:
                self.start_btn.setEnabled(True)

    def _apply_token_locked(self, status: dict):
        """Block START and show appropriate message when tokens are exhausted.

        Inherits effective_max deduction logic from account_settings_page:
            effective_max = recommended_cap - used_today
            headroom      = effective_max - threshold (extra pitches still available)  
        """
        self.start_btn.setEnabled(False)

        cap = status["recommended_cap"]
        threshold = status["threshold"]
        used_today = status.get("used_today", self._used_today)

        # Recompute headroom using effect_max — mirrors account_settings logic
        effective_max = max(0, cap - used_today)
        headroom = max(0, effective_max - threshold)

        if headroom > 0:
            msg = (
                f"You've used all {threshold} of your pitching tokens today. "
                f"You can still pitch {headroom} more and your recommended "
                f"daily limit is {cap}. Increase your threshold in Account Settings."
            )
            icon_color = "#f0a500"
        else:
            msg = (
                f"You've reached your maximum daily pitch limit of {cap}. "
                f"Your pitches replenish at midnight."
            )
            icon_color = "#e05555"

        # Render alert-triangle SVG with inherited color
        self._alert_icon_lbl.setPixmap(
            get_icon("alert-triangle", color=icon_color, size=14).pixmap(14, 14)
        )
        self.token_status_lbl.setText(msg)
        self.token_status_lbl.show()

    def _handle_token_exhausted_mid_session(self):
        """Called during a live session when tokens hit zero mid-pitch."""
        if not self._running:
            return
        self._running = False
        self._end_pitch_count = self._pitch_count
        self._end_mistakes = self._mistakes

        # Snapshot worker BEFORE _stop_capture nulls self._worker
        self._ending_worker = self._worker
        self._worker = None

        self._stop_capture()

        headroom = max(0, (self._recommended_cap or 0) - (self._threshold or 0))
        status = {
            "threshold": self._threshold,
            "recommended_cap": self._recommended_cap,
            "headroom": headroom,
        }
        self._apply_token_locked(status)

        # Show 0 immediately on the panel without touching the DB
        self.token_val.setText("0")
        # Launch the same async summary flow as _handle_end
        self._launch_summary_waiter()

    def _check_tokens_on_start(self) -> bool:
        """Refresh token status, return True (blocked) if no tokens remain."""
        self._refresh_token_status()
        return self._tokens_remaining <= 0
    
    # Handlers
    def _handle_start(self):
        if self._check_tokens_on_start():
            return
    
        self.token_status_widget.hide()
        self._running = True
        # Confirm active camera name at START from desired (or index fallback)
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
        self.session_started.emit()

        # Reset stats for new sessions
        self._pitch_count = 0
        self._mistakes = 0
        self._worker_state = ""
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
        # Pass the full label width — the worker uses panel_layout() internally
        # to split camera vs panel. Never subtract here.

        # Fallback: derive from screen geometry if label hasn't rendered yet
        if feed_w < 100 or feed_h < 100:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            feed_w = screen.width() - 300 - 280
            feed_h = screen.height() - 48

        # Start PitchWorker
        self._worker = PitchWorker(
            camera_id=self._camera_index,
            width=feed_w,
            height=feed_h,
            throwing_hand=self._throwing_hand,
            ml_bundle=self._ml_bundle,
            user_id=self.user_id,
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
        # Guard: ignore if a shutdown is already in progress
        if self._ending_worker is not None or not self._running:
            print("[END] guard hit — shutdown already in progress or not running")
            return

        self._running = False
        self.end_btn.setEnabled(False)
        self._show_idle_feed()
        self._update_camera_guide()

        # Clear feed immediately — session is already processing
        self._show_idle_feed()

        # Snapshot pitch stats now — they must not change before dialog opens
        self._end_pitch_count = self._pitch_count
        self._end_mistakes = self._mistakes
        self._worker_state = ""
        print(f"[END] pitches={self._end_pitch_count} mistakes={self._end_mistakes} worker={self._worker}")

        # Snapshot worker BEFORE anything can null it, then launch waiter 
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
                print(f"[END waiter] worker already stopped, posting immediately")
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
            self.camera_combo.setEnabled(True)
        # Re-show guide card — user may have dismissed it during the session
        self._update_camera_guide()
 
        # Nothing to summarise — session ended before any pitch was thrown
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
        self._summary_dlg = None
        self._ending_worker = None
        # Refresh AFTER dialog closes so the panel never jumps during summary 
        self._refresh_token_status()
        # Ensure feed is black and END is disabled after dialog closes
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

        # Reset for next session
        self._pitch_count = 0
        self._mistakes = 0
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self.token_status_widget.hide()

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
 
        if message == "__camera_disconnected__":
            self._handle_camera_disconnected()
        else:
            toast_error(self, f"Camera error: {message}")

    def _handle_camera_disconnected(self):
        """Camera was lost mid-session — discard session, offer reconnect."""
        # Reset all session counters so the page is clean for a fresh start
        self._pitch_count = 0
        self._mistakes = 0
        self._worker_state = ""
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self._show_idle_feed()
        self.end_btn.setEnabled(False)
        self.session_finished.emit()
 
        # Use the name captured at START — no re-probing needed
        lost_name = self._active_camera_name or f"Camera {self._camera_index}"

        dlg = CameraReconnectDialog(
            self,
            lost_camera_index=self._camera_index,
            lost_camera_name=lost_name,
        )
        if dlg.exec():
            new_idx = dlg.selected_camera_index()
            new_name = dlg.selected_camera_name()
            self._camera_index = new_idx
            self._desired_camera_name = new_name
            self._active_camera_name  = ""
            self._refresh_camera_cache()   # re-probe then repopulate
            toast_warning(
                self,
                f"\"{new_name}\" selected. Press START to begin a new session."
            )
        else:
            toast_warning(self, f"Session discarded — \"{lost_name}\" was disconnected.")

    def _on_worker_state_changed(self, state: str):
        """Track the worker's current state so _handle_end can use it."""
        self._worker_state = state 

    def _on_session_ended(self, log_path: str):
        """Called when PitchWorker finishes. skeleton_path is read directly
        from worker.skeleton_path in _stop_capture, not via this signal."""
        if log_path:
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
