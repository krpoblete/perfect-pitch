from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QDialog, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from src.utils.icons import get_icon
from src.utils.toast import toast_error

# LiveCameraCombo
class LiveCameraCombo(QComboBox):
    """Passive camera selector combo.

    Populated only when the user explicitly clicks 'Find Cameras'.
    Never probes hardware on its own - no LEDs activate, no startup lag.
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

# CameraMixin
class CameraMixin:
    # Static Hardware Query
    @staticmethod
    def _get_camera_names() -> tuple:
        """Return (physical_names, virtual_names) for the camera pairing step."""
        # Primary: PyGrabber
        try:
            from pygrabber.dshow_graph import FilterGraph as _FG
            import cv2 as _cv2

            all_names: list[str] = _FG().get_input_devices()  # DirectShow Order

            # Classify Physical VS Virtual Via MSMF (No LED - isOpened only)
            msmf_set: set[int] = set()
            for idx in range(len(all_names)):
                cap = _cv2.VideoCapture(idx, _cv2.CAP_MSMF)
                if cap.isOpened():
                    msmf_set.add(idx)
                cap.release()

            physical_names = [n for i, n in enumerate(all_names) if i in msmf_set]
            virtual_names = [n for i, n in enumerate(all_names) if i not in msmf_set]
            return (physical_names, virtual_names)

        except ImportError:
            pass  # pygrabber Not Installed - Fall through to PowerShell
        except Exception:
            pass  # COM Error, Driver Issue, etc. - Fall Through

        # Fallback: PowerShell + Registry
        import subprocess, json as _json

        ps_script = (
            # Physical Cameras from WMI PnP, Sorted by PNPDeviceID to Match
            # MSMF Enumeration Order OpenCV uses Internally.
            "$phys = Get-WmiObject Win32_PnPEntity -ErrorAction SilentlyContinue "
            "| Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } "
            "| Sort-Object PNPDeviceID "
            "| Select-Object -ExpandProperty Name; "

            # Virtual Cameras from KSCATEGORY_VIDEO registry.
            # Windows Virtual Camera Registers under this GUID.
            # KSCATEGORY_VIDEO_CAMERA (65e8773d) is for Physical UVC Devices
            # and is NOT where Windows Virtual Camera Appears.
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
            # Deduplicate: Drop Any Virtual Name that Already Appears in phys
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

    # Combo Population
    def _populate_camera_combo(self):
        """Fill the combo from _camera_cache and restore the user's desired camera.

        Selection priority:
          1. _desired_camera_name - the user's explicit choice (survives index shifts)
          2. _camera_index - fallback if name not found in new cache
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

        # Try to Match by Desired Name
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

        # Fall Back to Index Match
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
            virtual_names: list = []

            def _fetch_names():
                result = CameraMixin._get_camera_names()
                physical_names.extend(result[0])
                virtual_names.extend(result[1])

            def _enum_cameras(out_phys: list, out_virt: list):
                msmf_set = set()
                for idx in range(8):
                    cap = _cv2.VideoCapture(idx, _cv2.CAP_MSMF)
                    if cap.isOpened():
                        msmf_set.add(idx)
                    cap.release()

                for idx in range(8):
                    cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
                    if cap.isOpened():
                        if idx in msmf_set:
                            out_phys.append(idx)
                        else:
                            out_virt.append(idx)
                    cap.release()

            phys_indices: list = []
            virt_indices: list = []

            t_names = _t.Thread(target=_fetch_names, daemon=True)
            t_enum  = _t.Thread(target=_enum_cameras, args=(phys_indices, virt_indices), daemon=True)
            t_names.start()
            t_enum.start()
            t_names.join()
            t_enum.join()

            cache: list = []
            for i, idx in enumerate(phys_indices):
                name = physical_names[i] if i < len(physical_names) else f"Camera {idx}"
                cache.append((idx, name))
            for i, idx in enumerate(virt_indices):
                name = virtual_names[i] if i < len(virtual_names) else f"Camera {idx}"
                cache.append((idx, name))

            self._camera_cache = cache

            self._virt_indices = set(virt_indices)
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

        n = self.camera_combo.count()
        self.find_cam_btn.setText(f"✅  Found ({n})")
        self.find_cam_btn.setEnabled(True)

        idx = self.camera_combo.itemData(self.camera_combo.currentIndex())
        if idx is not None and idx >= 0:
            self._camera_index = idx
            cam_name = next((nm for ix, nm in self._camera_cache if ix == idx), "")
            if cam_name:
                self._desired_camera_name = cam_name
            self.test_cam_btn.setEnabled(True)
        else:
            self.test_cam_btn.setEnabled(False)

        self._start_device_change_listener()

        self._refresh_token_status()

    # Button Handlers
    def _handle_find_cameras(self):
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

        Stays open until the user clicks anywhere - no auto-close timer.
        Uses CAP_DSHOW for the actual frame grab (MSMF is slow to produce
        the first frame on some drivers, and won't stream OBS at all).
        """
        if self._running:
            return

        cam_idx = self.camera_combo.itemData(self.camera_combo.currentIndex())
        if cam_idx is None or cam_idx < 0:
            return
        self._camera_index = cam_idx

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
            sg.x() + (sg.width() - dlg.width()) // 2,
            sg.y() + (sg.height() - dlg.height()) // 2,
        )

        self._stop_device_change_listener()  # Re-Registered After Preview Closes

        cap = _cv2.VideoCapture(cam_idx, _cv2.CAP_DSHOW)

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
        self._start_device_change_listener()  # Re-Register After Camera Fully Released

    def _on_camera_changed(self, combo_idx: int):
        idx = self.camera_combo.itemData(combo_idx)
        if idx is not None and idx >= 0:
            self._camera_index = idx
            name = next((n for ix, n in self._camera_cache if ix == idx), "")
            if name:
                self._desired_camera_name = name
            self.test_cam_btn.setEnabled(True)
        else:
            self.test_cam_btn.setEnabled(False)

    # Guide Card
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

    # Feed Helpers
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

    # Device-Change Listener (WM_DEVICECHANGE)
    def _start_device_change_listener(self):
        """Register a hidden native window that receives WM_DEVICECHANGE from
        Windows whenever any device is plugged or unplugged.

        This replaces the old polling idle watcher entirely:
          - No background threads touching the camera driver
          - No QTimer firing every 2 s
          - No _watcher_busy races
          - No time.sleep() settle hacks
          - Detection is instant (~50 ms OS message latency)

        The listener stays registered the whole time.  During a live session
        _on_device_removed() returns immediately - PitchWorker already handles
        its own disconnection via error_occurred.
        """
        if getattr(self, "_devchange_listener", None) is not None:
            return  # Already Registered

        try:
            from PyQt6.QtGui import QWindow
            import ctypes, ctypes.wintypes as _wt

            page_ref = self   # Capture Mixin | Page Reference

            class _DevChangeWindow(QWindow):
                WM_DEVICECHANGE = 0x0219
                DBT_DEVICEREMOVECOMPLETE = 0x8004

                def nativeEvent(self, event_type, message):
                    import ctypes
                    msg = ctypes.cast(int(message), ctypes.POINTER(ctypes.c_uint * 7))
                    if msg and msg[0][1] == self.WM_DEVICECHANGE:
                        wparam = msg[0][2]
                        if wparam == self.DBT_DEVICEREMOVECOMPLETE:
                            QTimer.singleShot(300, page_ref._on_device_removed)
                    return False, 0

            win = _DevChangeWindow()
            win.create()                     # Allocates the Native HWND
            self._devchange_listener = win
        except Exception:
            self._devchange_listener = None  # Not on Windows or ctypes Issue

    def _stop_device_change_listener(self):
        """Destroy the native listener window (called on page teardown)."""
        listener = getattr(self, "_devchange_listener", None)
        if listener is not None:
            try:
                listener.destroy()
            except Exception:
                pass
            self._devchange_listener = None

    def _on_device_removed(self):
        """Called ~300 ms after Windows fires DBT_DEVICEREMOVECOMPLETE.

        The delay gives the OS time to finish unmounting the device before we
        attempt to open it for verification.  Only acts when:
          - No session is running (PitchWorker handles its own disconnect)
          - A camera has been selected (_camera_index >= 0)
          - The selected camera can no longer be opened
        """
        if self._running or self._camera_index < 0:
            return

        import cv2 as _cv2
        idx = self._camera_index
        cap = _cv2.VideoCapture(idx, _cv2.CAP_DSHOW)
        still_alive = cap.isOpened()
        cap.release()

        if still_alive:
            return      # Something Else was Unplugged - Our Camera is Fine

        lost_name = self._desired_camera_name or f"Camera {idx}"

        self._camera_index = -1
        self._desired_camera_name = ""
        self._active_camera_name = ""
        self._camera_cache = []

        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItem("No camera selected", -1)
        self.camera_combo.blockSignals(False)
        self.camera_combo.setEnabled(False)
        self.camera_combo.set_session_live(False)
        self.test_cam_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        self.find_cam_btn.setText("🔍  Find Cameras")
        self.find_cam_btn.setEnabled(True)

        toast_error(
            self,
            f"⚠  \"{lost_name}\" disconnected. "
            f"Click 'Find Cameras' to reconnect."
        )

    # Disconnection Handler (Called by StartSessionPage._on_worker_error)
    def _handle_camera_disconnected(self):
        # Reset Session Counters
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

        self._camera_index = -1
        self._desired_camera_name = ""
        self._active_camera_name = ""
        self._camera_cache = []

        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItem("No camera selected", -1)
        self.camera_combo.blockSignals(False)
        self.camera_combo.setEnabled(False)
        self.camera_combo.set_session_live(False)
        self.test_cam_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        self.find_cam_btn.setText("🔍  Find Cameras")
        self.find_cam_btn.setEnabled(True)

        toast_error(
            self,
            f"⚠  \"{lost_name}\" disconnected - session discarded. "
            f"Click 'Find Cameras' to reconnect."
        )
