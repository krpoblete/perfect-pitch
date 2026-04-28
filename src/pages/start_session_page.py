from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QDialog, QGridLayout, QFrame,
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

class StartSessionPage(QWidget):
    _worker_done = pyqtSignal()      # internal: waiter thread → main thread
    session_started = pyqtSignal()   # emitted when START is pressed
    session_finished = pyqtSignal()  # emitted when summary dialog closes

    def __init__(self, user_id: int, ml_bundle=None):
        super().__init__()
        self.user_id = user_id
        self._ml_bundle = ml_bundle        # (model, scaler, threshold, joint_thresholds)
        self._running = False
        self._pitch_count = 0
        self._mistakes = 0
        self._threshold = None             # user's current token pool
        self._recommended_cap = None       # USA Baseball age-based cap
        self._used_today = 0               # pitches thrown today
        self._tokens_remaining = 0         # threshold - used_today 
        self._throwing_hand = "RHP"   
        self._worker = None
        self._summary_dlg = None           # ref to open dialog for skeleton injection
        self._skeleton_path = ""           # path to last generated skeleton PNG
        self._end_pitch_count = 0          # snapshot at END time for dialog
        self._end_mistakes = 0             # snapshot at END time for dialog
        self._ending_worker = None         # strong ref held during async shutdown
        self._worker_state = ""            # last state emitted by PitchWorker
        self._camera_index = 0             # active camera device index
        self._worker_done.connect(lambda: self._on_worker_finished(self._ending_worker))
        # Start polling for camera connect/disconnect
        # self._start_camera_monitor()
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

        # Stats panel
        from PyQt6.QtWidgets import QApplication as _QApp
        _sw = _QApp.primaryScreen().availableGeometry().width()
        _panel_w = max(220, min(300, int(_sw * 0.155)))
        panel = QWidget()
        panel.setObjectName("sessionPanel")
        panel.setFixedWidth(_panel_w)
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

        # Bottom row: camera selector + guide toggle
        from PyQt6.QtWidgets import QComboBox
        guide_toggle_row = QHBoxLayout()
        guide_toggle_row.setContentsMargins(0, 0, 0, 0)
        guide_toggle_row.setSpacing(6)

        self.camera_combo = QComboBox()
        self.camera_combo.setObjectName("cameraCombo")
        self.camera_combo.setFixedHeight(28)
        self.camera_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.camera_combo.setToolTip("Select camera source")
        self._populate_camera_combo()
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        guide_toggle_row.addWidget(self.camera_combo, stretch=1)

        self.guide_toggle_btn = QPushButton()
        self.guide_toggle_btn.setObjectName("guideToggleBtn")
        self.guide_toggle_btn.setFixedSize(28, 28)
        self.guide_toggle_btn.setIcon(get_icon("help", color="#555555", size=20))
        self.guide_toggle_btn.setIconSize(QSize(20, 20))
        self.guide_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.guide_toggle_btn.setToolTip("Show/hide camera setup guide")
        self.guide_toggle_btn.setAutoDefault(False)
        self.guide_toggle_btn.setDefault(False)
        self.guide_toggle_btn.clicked.connect(self._toggle_guide_card)
        guide_toggle_row.addWidget(self.guide_toggle_btn)

        panel_layout.addLayout(guide_toggle_row)

        # START button
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("sessionStartBtn")
        self.start_btn.setFixedHeight(60)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setAutoDefault(False)
        self.start_btn.setDefault(False)
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
        # Accuracy card gets a formatted default; others use plain "0"
        default = "0.00%" if title == "Accuracy" else "0"
        val = QLabel(default)
        val.setObjectName("statValue")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(val)

        return card

    # Camera guide toggle
    @staticmethod
    def _get_camera_names() -> dict:
        """Return {index: name} for all DirectShow video devices using WMI.
        Falls back to generic labels if WMI is unavailable."""
        names = {}
        try:
            import subprocess, json as _json
            # Query Win32_PnPEntity for camera-class devices via PowerShell
            ps = (
                "Get-WmiObject Win32_PnPEntity | "
                "Where-Object {$_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image'} | "
                "Select-Object -ExpandProperty Name | ConvertTo-Json"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=5
            )
            raw = result.stdout.strip()
            if raw:
                parsed = _json.loads(raw)
                device_names = [parsed] if isinstance(parsed, str) else parsed
                for i, name in enumerate(device_names):
                    names[i] = name
        except Exception:
            pass
        return names

    def _populate_camera_combo(self):
        """Probe camera indices 0-9, fetch real device names, populate combo."""
        import cv2 as _cv2
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()

        device_names = self._get_camera_names()
        found = []
        for idx in range(10):
            cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
            if cap.isOpened():
                found.append(idx)
                cap.release()

        if not found:
            self.camera_combo.addItem("No cameras found", -1)
        else:
            for idx in found:
                name = device_names.get(idx, f"Camera {idx}")
                label = f"{name}" if idx > 0 else f"{name} (default)"
                self.camera_combo.addItem(label, idx)

        for i in range(self.camera_combo.count()):
            if self.camera_combo.itemData(i) == self._camera_index:
                self.camera_combo.setCurrentIndex(i)
                break

        self.camera_combo.blockSignals(False)

    def _on_camera_changed(self, combo_idx: int):
        """Update active camera index — takes effect on next START."""
        idx = self.camera_combo.itemData(combo_idx)
        if idx is not None and idx >= 0:
            self._camera_index = idx

    # def _start_camera_monitor(self):
    #     """Poll every 3 s for camera connect/disconnect and refresh combo."""
    #     self._camera_monitor = QTimer(self)
    #     self._camera_monitor.setInterval(3000)
    #     self._camera_monitor.timeout.connect(self._check_camera_changes)
    #     self._camera_monitor.start()

    def _check_camera_changes(self):
        """Refresh the camera combo if the device list has changed."""
        if self._running:
            return   # never disrupt a live session
        import cv2 as _cv2
        current_indices = set()
        for idx in range(10):
            cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
            if cap.isOpened():
                current_indices.add(idx)
                cap.release()
        # Compare against what's currently in the combo
        combo_indices = {
            self.camera_combo.itemData(i)
            for i in range(self.camera_combo.count())
            if self.camera_combo.itemData(i) is not None and
               self.camera_combo.itemData(i) >= 0
        }
        if current_indices != combo_indices:
            prev = self._camera_index
            self._populate_camera_combo()
            # If the selected camera disappeared, reset to 0
            if prev not in current_indices:
                self._camera_index = 0
                self.camera_combo.setCurrentIndex(0)

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

        # Update recommended threshold card
        self.rec_val_lbl.setText(
            f"{cap} pitches/day" if cap else "—"
        )

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
        self.camera_guide_card.hide()
        self._running = True
        self.start_btn.setEnabled(False)
        self.end_btn.setEnabled(True)

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
        self._refresh_token_status()

    def _save_session(self, accuracy: float):
        toast_success(self, "Session saved successfully.")
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
        toast_error(self, f"Camera error: {message}")

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
