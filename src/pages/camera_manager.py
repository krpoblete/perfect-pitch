from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from src.utils.icons import get_icon
from src.utils.toast import toast_warning, toast_error

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
        """Return (physical_names, virtual_names) in DSHOW index order.

        Uses raw ctypes to call CoCreateInstance(CLSID_SystemDeviceEnum) and
        enumerate CLSID_VideoInputDeviceCategory monikers — the exact same
        path OpenCV takes internally for CAP_DSHOW. Names and indices are
        guaranteed to match OpenCV's assignment, including Windows Virtual
        Camera (OBS 28+).

        IMoniker vtable on Windows 11:
          [0-2] IUnknown, [3] GetClassID, [4-7] IPersistStream,
          [8] BindToObject, [9] BindToStorage  ← slot 9, not 8

        Falls back to empty lists on any error so cameras still appear as
        "Camera N" rather than crashing.
        """
        import ctypes, uuid, cv2 as _cv2

        all_names: list[str] = []

        try:
            ole32    = ctypes.windll.ole32
            oleaut32 = ctypes.windll.oleaut32
            ole32.CoInitializeEx(None, 0)

            def _guid(s):
                return (ctypes.c_byte * 16)(*uuid.UUID(s).bytes_le)

            CLSID_SystemDeviceEnum         = _guid("62BE5D10-60EB-11D0-BD3B-00A0C911CE86")
            IID_ICreateDevEnum             = _guid("29840822-5B84-11D0-BD3B-00A0C911CE86")
            CLSID_VideoInputDeviceCategory = _guid("860BB310-5D01-11D0-BD3B-00A0C911CE86")
            IID_IPropertyBag               = _guid("55272A00-42CB-11CE-8135-00AA004BB851")

            # CoCreateInstance → ICreateDevEnum
            dev_enum = ctypes.c_void_p()
            hr = ole32.CoCreateInstance(
                CLSID_SystemDeviceEnum, None, 1,
                IID_ICreateDevEnum, ctypes.byref(dev_enum)
            )
            if hr != 0 or not dev_enum:
                raise OSError(f"CoCreateInstance hr={hr:#010x}")

            vt = ctypes.cast(
                ctypes.cast(dev_enum, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )
            CreateClassEnumerator = ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_byte * 16),
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_ulong
            )(vt[3])

            enum_ptr = ctypes.c_void_p()
            hr = CreateClassEnumerator(
                dev_enum,
                ctypes.byref(CLSID_VideoInputDeviceCategory),
                ctypes.byref(enum_ptr),
                0
            )
            if hr != 0 or not enum_ptr:
                raise OSError(f"CreateClassEnumerator hr={hr:#010x}")

            vt2 = ctypes.cast(
                ctypes.cast(enum_ptr, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )
            Next = ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_ulong)
            )(vt2[3])

            class VARIANT(ctypes.Structure):
                _fields_ = [
                    ("vt",  ctypes.c_ushort),
                    ("pad", ctypes.c_byte * 6),
                    ("val", ctypes.c_void_p),
                ]

            while True:
                moniker = ctypes.c_void_p()
                fetched = ctypes.c_ulong(0)
                hr = Next(enum_ptr, 1, ctypes.byref(moniker), ctypes.byref(fetched))
                if hr != 0 or fetched.value == 0 or not moniker:
                    break

                try:
                    vt3 = ctypes.cast(
                        ctypes.cast(moniker, ctypes.POINTER(ctypes.c_void_p))[0],
                        ctypes.POINTER(ctypes.c_void_p)
                    )
                    # Slot 9 = BindToStorage on Windows 11
                    BindToStorage = ctypes.WINFUNCTYPE(
                        ctypes.HRESULT,
                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                        ctypes.POINTER(ctypes.c_byte * 16),
                        ctypes.POINTER(ctypes.c_void_p)
                    )(vt3[9])

                    prop_bag = ctypes.c_void_p()
                    hr = BindToStorage(
                        moniker, None, None,
                        ctypes.byref(IID_IPropertyBag),
                        ctypes.byref(prop_bag)
                    )
                    if hr != 0 or not prop_bag:
                        all_names.append("")
                        continue

                    vt4 = ctypes.cast(
                        ctypes.cast(prop_bag, ctypes.POINTER(ctypes.c_void_p))[0],
                        ctypes.POINTER(ctypes.c_void_p)
                    )
                    Read = ctypes.WINFUNCTYPE(
                        ctypes.HRESULT,
                        ctypes.c_void_p,
                        ctypes.c_wchar_p,
                        ctypes.POINTER(VARIANT),
                        ctypes.c_void_p
                    )(vt4[3])

                    var = VARIANT()
                    hr  = Read(prop_bag, "FriendlyName", ctypes.byref(var), None)
                    if hr == 0 and var.vt == 8 and var.val:  # VT_BSTR = 8
                        name = ctypes.cast(var.val, ctypes.c_wchar_p).value or ""
                        all_names.append(name.strip())
                        oleaut32.SysFreeString(var.val)
                    else:
                        all_names.append("")

                except Exception:
                    all_names.append("")

        except Exception:
            pass

        if not all_names:
            return ([], [])

        # Classify physical vs virtual: MSMF opens physical cameras, not virtual ones.
        # Preserve the real DSHOW index for each device so callers can build an
        # accurate index→name map without re-enumerating sequentially.
        msmf_set: set[int] = set()
        for i in range(len(all_names)):
            cap = _cv2.VideoCapture(i, _cv2.CAP_MSMF)
            if cap.isOpened():
                msmf_set.add(i)
            cap.release()

        # Return (real_dshow_index, name) pairs — NOT stripped name lists.
        physical_pairs = [(i, n) for i, n in enumerate(all_names) if i in msmf_set]
        virtual_pairs  = [(i, n) for i, n in enumerate(all_names) if i not in msmf_set]
        return (physical_pairs, virtual_pairs)

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

        Names and indices are resolved in a single pass so they are guaranteed
        to be in the same order. _get_camera_names() enumerates via the DirectShow
        COM enumerator (same source as OpenCV CAP_DSHOW) and classifies each device
        as physical (MSMF-visible) or virtual (DSHOW-only). The resulting flat list
        is already in DSHOW index order — index 0 = first COM moniker, etc.

        Capped at 3 cameras maximum (1 physical + 1 virtual is the typical setup;
        3 covers the Integrated + USB + OBS case).
        """
        import threading as _t, cv2 as _cv2

        MAX_CAMERAS = 3

        def _probe():
            phys_pairs, virt_pairs = CameraMixin._get_camera_names()

            # Build a flat list of (real_dshow_index, name, is_virtual) in
            # ascending index order, preserving the actual OS-assigned indices.
            # Physical cameras come from MSMF enumeration; virtual (OBS etc.)
            # are DSHOW-only.  Both lists already carry the real index.
            all_pairs = sorted(
                [(i, n, False) for i, n in phys_pairs] +
                [(i, n, True)  for i, n in virt_pairs],
                key=lambda t: t[0]
            )

            # Confirm each index is openable via DSHOW, cap at MAX_CAMERAS.
            cache: list = []
            virt_set: set = set()

            for i, name, is_virt in all_pairs[:MAX_CAMERAS]:
                cap = _cv2.VideoCapture(i, _cv2.CAP_DSHOW)
                if cap.isOpened():
                    label = name if name else f"Camera {i}"
                    cache.append((i, label))
                    if is_virt:
                        virt_set.add(i)
                cap.release()

            self._camera_cache = cache
            self._virt_indices  = virt_set
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

        # _populate_camera_combo blocks signals so _on_camera_changed never
        # fires during auto-selection. Sync _camera_index and Test state here.
        idx = self.camera_combo.itemData(self.camera_combo.currentIndex())
        if idx is not None and idx >= 0:
            self._camera_index = idx
            cam_name = next((nm for ix, nm in self._camera_cache if ix == idx), "")
            if cam_name:
                self._desired_camera_name = cam_name
            self.test_cam_btn.setEnabled(True)
        else:
            self.test_cam_btn.setEnabled(False)

        # Register device-change listener (once; no-op if already registered)
        self._start_device_change_listener()

        # Do NOT enable START unconditionally — respect token status.
        # _refresh_token_status enables START only if tokens remain.
        self._refresh_token_status()

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

        Backend selection:
          - Physical cameras → CAP_DSHOW  (reliable, low latency)
          - Virtual cameras (OBS, etc.) → CAP_MSMF
            OBS Virtual Camera v27+ uses the Windows MF Platform sink.
            It appears in the DirectShow device list (so Find Cameras detects
            it correctly) but outputs black frames when opened via CAP_DSHOW.
            CAP_MSMF is the correct backend to actually receive its frames.
        """
        if self._running:
            return

        cam_idx = self.camera_combo.itemData(self.camera_combo.currentIndex())
        if cam_idx is None or cam_idx < 0:
            return
        self._camera_index = cam_idx

        import cv2 as _cv2

        # Pick the right backend for this device
        is_virtual = cam_idx in getattr(self, "_virt_indices", set())
        backend = _cv2.CAP_MSMF if is_virtual else _cv2.CAP_DSHOW

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setObjectName("cameraTestDialog")
        dlg.setFixedSize(400, 300)

        lbl = QLabel("Starting preview…", dlg)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setGeometry(0, 0, 400, 270)
        lbl.setStyleSheet("background:#0a0a0a; color:#555555; font-size:12px;")

        close_lbl = QLabel("Click anywhere to close", dlg)
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

        self._stop_device_change_listener()   # re-registered after preview closes

        cap = _cv2.VideoCapture(cam_idx, backend)

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
        self._start_device_change_listener()  # re-register after camera fully released

    def _on_camera_changed(self, combo_idx: int):
        """Update camera index and desired name — takes effect on next START.

        Also drives the Test button: enabled only when a real camera (idx >= 0)
        is selected, disabled for any placeholder item.
        """
        idx = self.camera_combo.itemData(combo_idx)
        if idx is not None and idx >= 0:
            self._camera_index = idx
            name = next((n for ix, n in self._camera_cache if ix == idx), "")
            if name:
                self._desired_camera_name = name
            self.test_cam_btn.setEnabled(True)
        else:
            self.test_cam_btn.setEnabled(False)

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
        # Use bytes() copy so QImage doesn't hold a reference to the numpy buffer
        img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        scaled = img.scaled(
            self.feed_label.width(),
            self.feed_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.feed_label.setObjectName("feedLabel")
        self.feed_label.setPixmap(_QP.fromImage(scaled))

    # Device-change listener (WM_DEVICECHANGE)
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
        _on_device_removed() returns immediately — PitchWorker already handles
        its own disconnection via error_occurred.
        """
        if getattr(self, "_devchange_listener", None) is not None:
            return   # already registered

        try:
            from PyQt6.QtGui import QWindow
            import ctypes, ctypes.wintypes as _wt

            page_ref = self   # capture mixin/page reference

            class _DevChangeWindow(QWindow):
                WM_DEVICECHANGE        = 0x0219
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
            win.create()   # allocates the native HWND
            self._devchange_listener = win
        except Exception:
            self._devchange_listener = None   # not on Windows or ctypes issue

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

        Uses MSMF for physical cameras (no LED activation) and DSHOW for
        virtual cameras such as OBS (MSMF cannot see them at all).
        """
        if self._running or self._camera_index < 0:
            return

        import cv2 as _cv2
        idx = self._camera_index
        is_virtual = idx in getattr(self, "_virt_indices", set())
        backend = _cv2.CAP_DSHOW if is_virtual else _cv2.CAP_MSMF
        cap = _cv2.VideoCapture(idx, backend)
        still_alive = cap.isOpened()
        cap.release()

        if still_alive:
            return   # something else was unplugged — our camera is fine

        # Selected camera is gone — reset UI exactly like a mid-session disconnect
        lost_name = self._desired_camera_name or f"Camera {idx}"

        self._camera_index        = -1
        self._desired_camera_name = ""
        self._active_camera_name  = ""
        self._camera_cache        = []

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

    # Disconnection handler (called by StartSessionPage._on_worker_error)
    def _handle_camera_disconnected(self):
        """Camera was lost mid-session.

        Discards the session, locks the combo and Test button so the user
        cannot interact with stale state, resets Find Cameras back to its
        idle state, and shows a toast telling the user exactly what to do.

        No reconnect dialog — the user simply clicks 'Find Cameras' to run
        a fresh probe, picks the working camera from the repopulated combo,
        and hits START. One code path, no modal, no stale indices.
        """
        # Reset session counters
        self._pitch_count  = 0
        self._mistakes     = 0
        self._worker_state = ""
        self.pitch_val.setText("0")
        self.mistake_val.setText("0")
        self.accuracy_val.setText("0.00%")
        self._show_idle_feed()
        self.end_btn.setEnabled(False)
        self.session_finished.emit()

        lost_name = self._active_camera_name or f"Camera {self._camera_index}"

        # Reset camera selection state — indices are stale after a disconnect
        self._camera_index        = -1
        self._desired_camera_name = ""
        self._active_camera_name  = ""
        self._camera_cache        = []

        # Lock combo and Test — their contents are stale
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItem("No camera selected", -1)
        self.camera_combo.blockSignals(False)
        self.camera_combo.setEnabled(False)
        self.camera_combo.set_session_live(False)
        self.test_cam_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        # Reset Find Cameras to idle so it's the obvious next action
        self.find_cam_btn.setText("🔍  Find Cameras")
        self.find_cam_btn.setEnabled(True)

        toast_error(
            self,
            f"⚠  \"{lost_name}\" disconnected — session discarded. "
            f"Click 'Find Cameras' to reconnect."
        )
