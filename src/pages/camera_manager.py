from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from src.utils.icons import get_icon
from src.utils.toast import toast_warning

# LiveCameraCombo
class LiveCameraCombo(QComboBox):
    """Passive camera selector combo.

    Populated only when the user explicitly clicks 'Find Cameras'.
    Never probes hardware on its own — no LEDs activate, no startup lag.
    set_session_live() disables interaction during a live session.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_session_live = False

    def set_session_live(self, live: bool):
        self._is_session_live = live

    def showPopup(self):
        """Block dropdown expansion during a live session."""
        if self._is_session_live:
            return
        super().showPopup()


# CameraReconnectDialog
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
        """Probe cameras and populate the reconnect combo.

        Uses CAP_MSMF (no LED activation, no cap.read()).
        Names are fetched via CameraMixin._get_camera_names(), which
        returns a (physical_names, virtual_names) tuple — both lists are
        merged in order to match the MSMF + DSHOW enumeration sequence.

        The lost camera is already gone from the OS by the time this runs,
        so its index will not appear in the MSMF scan. We therefore show
        every found camera and auto-select the first one — no skip needed.
        """
        import cv2 as _cv2
        self._combo.clear()

        # _get_camera_names returns (phys_names, virt_names) — flatten in order
        phys_names, virt_names = CameraMixin._get_camera_names()
        all_names = phys_names + virt_names

        # MSMF: isOpened() only — no read, no LED
        msmf_found = []
        for idx in range(8):
            cap = _cv2.VideoCapture(idx, _cv2.CAP_MSMF)
            if cap.isOpened():
                msmf_found.append(idx)
            cap.release()

        # DSHOW-only (virtual cameras not visible via MSMF)
        dshow_only = []
        for idx in range(8):
            if idx in msmf_found:
                continue
            cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
            if cap.isOpened():
                dshow_only.append(idx)
            cap.release()

        found = msmf_found + dshow_only

        if not found:
            self._combo.addItem("No cameras detected", -1)
            return

        for i, idx in enumerate(found):
            label = all_names[i] if i < len(all_names) else f"Camera {idx}"
            self._combo.addItem(label, idx)

        # Auto-select the first available camera — the lost device is already
        # gone from the OS so it will not appear in `found`
        self._combo.setCurrentIndex(0)
        self._selected_index = self._combo.itemData(0)

    def _on_combo_changed(self, i: int):
        idx = self._combo.itemData(i)
        if idx is not None and idx >= 0:
            self._selected_index = idx

    def selected_camera_index(self) -> int:
        return self._selected_index

    def selected_camera_name(self) -> str:
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == self._selected_index:
                return self._combo.itemText(i).replace("  ⚠  (disconnected)", "").strip()
        return f"Camera {self._selected_index}"


# CameraMixin
class CameraMixin:
    """Camera probe, combo management, preview, and guide card logic.

    Mixed into StartSessionPage. Assumes the page provides these attributes
    (all created in build_ui / __init__):
        Widgets : camera_combo, find_cam_btn, test_cam_btn, start_btn,
                  feed_label, hand_badge, camera_side_lbl, camera_guide_card
        State   : _camera_index, _desired_camera_name, _camera_cache,
                  _throwing_hand, _running
    """

    # Static hardware query
    @staticmethod
    def _get_camera_names() -> tuple:
        """Return (physical_names, virtual_names) for the camera pairing step.

        - physical_names: WMI Win32_PnPEntity names for real hardware cameras
          sorted by PNPDeviceID to match the MSMF enumeration order OpenCV uses.
        - virtual_names: registry KSCATEGORY_VIDEO names for software/virtual
          cameras (OBS Virtual Camera, etc.) that only appear via DirectShow.

        The caller pairs physical_names with MSMF-found indices sequentially,
        then virtual_names with DSHOW-only indices sequentially.
        """
        import subprocess, json as _json

        ps_script = (
            "$phys = Get-WmiObject Win32_PnPEntity -ErrorAction SilentlyContinue "
            "| Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } "
            "| Sort-Object PNPDeviceID "
            "| Select-Object -ExpandProperty Name; "
            "$guid = '{e5323777-f976-4f5b-9b55-b94699c46e44}'; "
            "$base = \"HKLM:\\SYSTEM\\CurrentControlSet\\Control\\DeviceClasses\\$guid\"; "
            "$virt = @(); "
            "if (Test-Path $base) { "
            "  Get-ChildItem $base -ErrorAction SilentlyContinue "
            "  | Sort-Object Name "
            "  | ForEach-Object { "
            "    $fn = $null; "
            "    $hash = Join-Path $_.PSPath '#'; "
            "    if (Test-Path $hash) { "
            "      $fn = (Get-ItemProperty $hash -Name FriendlyName "
            "             -ErrorAction SilentlyContinue).FriendlyName } "
            "    if (-not $fn) { "
            "      $fn = (Get-ItemProperty $_.PSPath -Name FriendlyName "
            "             -ErrorAction SilentlyContinue).FriendlyName } "
            "    if ($fn) { $virt += $fn.Trim() } "
            "  } "
            "}; "
            "$physLower = $phys | ForEach-Object { $_.ToLower() }; "
            "$virtOnly = $virt | Where-Object { $physLower -notcontains $_.ToLower() }; "
            "@{ phys = @($phys); virt = @($virtOnly) } | ConvertTo-Json -Compress"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True, timeout=8
            )
            raw = result.stdout.strip()
            if not raw:
                return ([], [])
            parsed = _json.loads(raw)
            phys = [n.strip() for n in (parsed.get("phys") or []) if n and n.strip()]
            virt = [n.strip() for n in (parsed.get("virt") or []) if n and n.strip()]
            return (phys, virt)
        except Exception:
            return ([], [])

    # Combo population
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

        names_in_cache = [n for _, n in cache]
        for idx, name in cache:
            is_duplicate = names_in_cache.count(name) > 1
            label = f"{name} ({idx})" if is_duplicate else name
            self.camera_combo.addItem(label, idx)

        # 1. Try to match by desired name
        selected = False
        if self._desired_camera_name:
            for i in range(self.camera_combo.count()):
                item_idx = self.camera_combo.itemData(i)
                item_name = next((n for ix, n in cache if ix == item_idx), "")
                if item_name == self._desired_camera_name:
                    self.camera_combo.setCurrentIndex(i)
                    self._camera_index = item_idx
                    selected = True
                    break

        # 2. Fall back to index match
        if not selected:
            for i in range(self.camera_combo.count()):
                if self.camera_combo.itemData(i) == self._camera_index:
                    self.camera_combo.setCurrentIndex(i)
                    item_idx = self.camera_combo.itemData(i)
                    self._desired_camera_name = next(
                        (n for ix, n in cache if ix == item_idx), ""
                    )
                    break

        self.camera_combo.blockSignals(False)

    # Probe
    def _refresh_camera_cache(self):
        """Probe cameras in a daemon thread; posts _on_camera_probe_done when done.

        Uses a hybrid strategy:
        - MSMF (CAP_MSMF): enumerates physical cameras without activating LEDs.
        - DirectShow (CAP_DSHOW, isOpened() only, no read): catches virtual
          cameras such as OBS Virtual Camera that MSMF cannot see at all.

        Both sub-tasks (name fetch + enumerate) run in parallel to keep
        wall-clock time short.
        """
        import threading as _t, cv2 as _cv2

        def _probe():
            physical_names: list = []
            virtual_names:  list = []
            msmf_found: list = []
            dshow_only: list = []

            def _fetch_names():
                result = CameraMixin._get_camera_names()
                physical_names.extend(result[0])
                virtual_names.extend(result[1])

            def _enum_cameras():
                msmf_set = set()
                for idx in range(8):
                    cap = _cv2.VideoCapture(idx, _cv2.CAP_MSMF)
                    if cap.isOpened():
                        msmf_set.add(idx)
                    cap.release()

                dshow_set = set()
                for idx in range(8):
                    cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
                    if cap.isOpened():
                        dshow_set.add(idx)
                    cap.release()

                msmf_found.extend(sorted(msmf_set))
                dshow_only.extend(sorted(dshow_set - msmf_set))

            t_names = _t.Thread(target=_fetch_names, daemon=True)
            t_enum  = _t.Thread(target=_enum_cameras, daemon=True)
            t_names.start()
            t_enum.start()
            t_names.join()
            t_enum.join()

            cache: list = []
            for i, idx in enumerate(msmf_found):
                name = physical_names[i] if i < len(physical_names) else f"Camera {idx}"
                cache.append((idx, name))
            for i, idx in enumerate(dshow_only):
                name = virtual_names[i] if i < len(virtual_names) else f"Camera {idx}"
                cache.append((idx, name))

            self._camera_cache = cache
            QTimer.singleShot(0, self._on_camera_probe_done)

        _t.Thread(target=_probe, daemon=True).start()

    def _on_camera_probe_done(self):
        """Main-thread callback after _refresh_camera_cache finishes.

        Populates the combo, updates the Find Cameras button label, enables
        the combo + Test button, and auto-selects the last-used camera by name.
        """
        cache = self._camera_cache

        if not cache:
            self.find_cam_btn.setText("⚠  None found")
            self.find_cam_btn.setEnabled(True)
            self.camera_combo.clear()
            self.camera_combo.addItem("No cameras found", -1)
            self.camera_combo.setEnabled(False)
            self.test_cam_btn.setEnabled(False)
            self.start_btn.setEnabled(False)
            return

        self._populate_camera_combo()
        self.camera_combo.setEnabled(True)
        self.test_cam_btn.setEnabled(True)
        self.start_btn.setEnabled(True)

        n = self.camera_combo.count()
        self.find_cam_btn.setText(f"✅  Found ({n})")
        self.find_cam_btn.setEnabled(True)

    # Button handlers
    def _handle_find_cameras(self):
        """Triggered by 'Find Cameras' button.

        Transitions the button through three states:
          🔍 Find Cameras  →  ⏳ Searching...  →  ✅ Found (N)  or  ⚠ None found

        No camera LED ever activates here — MSMF enumerate-only.
        """
        if self._running:
            return

        self.find_cam_btn.setEnabled(False)
        self.find_cam_btn.setText("⏳  Searching...")
        self.camera_combo.setEnabled(False)
        self.test_cam_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self._refresh_camera_cache()

    def _handle_test_camera(self):
        """Open a live preview popup for the selected camera.

        Stays open until the user clicks anywhere — no auto-close timer.
        Uses CAP_DSHOW for the actual frame grab (MSMF is slow to produce
        the first frame on some drivers, and won't stream OBS at all).
        """
        if self._camera_index < 0 or self._running:
            return

        import cv2 as _cv2

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setObjectName("cameraTestDialog")
        dlg.setFixedSize(400, 300)

        lbl = QLabel("Starting preview…", dlg)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setGeometry(0, 0, 400, 270)
        lbl.setStyleSheet("background:#0a0a0a; color:#555555; font-size:12px;")

        close_lbl = QLabel("Click to close", dlg)
        close_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_lbl.setGeometry(0, 270, 400, 30)
        close_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        close_lbl.setStyleSheet("background:#111111; color:#444444; font-size:10px;")

        dlg.mousePressEvent = lambda _e: dlg.accept()

        from PyQt6.QtWidgets import QApplication as _QApp
        sg = _QApp.primaryScreen().availableGeometry()
        dlg.move(
            sg.x() + (sg.width()  - dlg.width())  // 2,
            sg.y() + (sg.height() - dlg.height()) // 2,
        )

        cap = _cv2.VideoCapture(self._camera_index, _cv2.CAP_DSHOW)

        def _tick():
            if not cap.isOpened():
                lbl.setText("⚠  Could not open camera")
                return
            ret, frame = cap.read()
            if not ret:
                return
            from PyQt6.QtGui import QImage as _QI, QPixmap as _QP
            rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = _QI(rgb.data, w, h, ch * w, _QI.Format.Format_RGB888)
            scaled = img.scaled(400, 270,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.FastTransformation)
            lbl.setPixmap(_QP.fromImage(scaled))

        timer = QTimer(dlg)
        timer.timeout.connect(_tick)
        timer.start(33)

        dlg.exec()
        timer.stop()
        cap.release()

    def _on_camera_changed(self, combo_idx: int):
        """Update camera index and desired name — takes effect on next START."""
        idx = self.camera_combo.itemData(combo_idx)
        if idx is not None and idx >= 0:
            self._camera_index = idx
            name = next((n for ix, n in self._camera_cache if ix == idx), "")
            if name:
                self._desired_camera_name = name

    # Guide card
    def _build_guide_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("cameraGuideCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

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

        div = QFrame()
        div.setObjectName("guideDivider")
        div.setFixedHeight(1)
        layout.addWidget(div)
        layout.addSpacing(2)

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

        self.camera_side_lbl = QLabel()
        self.camera_side_lbl.setObjectName("guideSideLabel")
        self.camera_side_lbl.setWordWrap(True)
        self.camera_side_lbl.setStyleSheet("font-size: 10px; background: transparent;")
        layout.addWidget(self.camera_side_lbl)

        layout.addSpacing(2)

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

    # Feed helpers
    def _show_idle_feed(self):
        self.feed_label.setText("Camera not started")
        self.feed_label.setObjectName("feedLabelIdle")
        self.feed_label.setPixmap(QPixmap())
        self.feed_label.style().unpolish(self.feed_label)
        self.feed_label.style().polish(self.feed_label)

    def update_frame(self, frame):
        """Called by PitchWorker to push a new frame (numpy BGR array)."""
        import cv2
        from PyQt6.QtGui import QImage, QPixmap as _QP
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
        self.feed_label.setPixmap(_QP.fromImage(scaled))

    # Disconnection handler (called by StartSessionPage._on_worker_error)
    def _handle_camera_disconnected(self):
        """Camera was lost mid-session — discard session, offer reconnect."""
        self._pitch_count = 0
        self._mistakes = 0
        self._worker_state = ""
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self._show_idle_feed()
        self.end_btn.setEnabled(False)
        self.session_finished.emit()

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
            self.find_cam_btn.setText("⏳  Searching...")
            self.find_cam_btn.setEnabled(False)
            self._refresh_camera_cache()
            toast_warning(
                self,
                f"\"{new_name}\" selected. Press START to begin a new session."
            )
        else:
            toast_warning(self, f"Session discarded — \"{lost_name}\" was disconnected.")
