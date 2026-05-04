import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QSize, QPoint, QRect, QPropertyAnimation, QEasingCurve
from qframelesswindow import FramelessMainWindow

from src.pages.dashboard_page import DashboardPage
from src.pages.users_page import UsersPage
from src.pages.pitchers_page import PitchersPage
from src.pages.start_session_page import StartSessionPage
from src.pages.account_settings_page import AccountSettingsPage
from src.utils.icons import get_icon
from src.widgets.window_buttons import WindowButtons
from src.widgets.confirm_dialog import ConfirmDialog

# Nav items per role
NAV_PITCHER = [
    ("dashboard", "home", "Dashboard"),
    ("start_session", "play-handball", "Start Session"),
]

NAV_COACH = [
    ("dashboard", "home", "Dashboard"),
    ("pitchers", "users", "Pitchers"),
]

NAV_ADMIN = [
    ("dashboard", "home", "Dashboard"),
    ("users", "users-group", "Users"),
    ("start_session", "play-handball", "Start Session"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Tour steps per role
# ─────────────────────────────────────────────────────────────────────────────
# Each step dict:
#   target        – objectName string   → will be found via findChild(QWidget, name)
#                   QWidget reference   → used directly
#                   None                → centred card (no spotlight)
#   title / body  – text shown in the callout
#   callout_side  – "bottom" | "top" | "right" | "left"
#
# NOTE: Add these objectNames to DashboardPage for precise spotlights:
#   Stats container  →  widget.setObjectName("statsSection")
#   History frame    →  widget.setObjectName("historySection")
# Without them the tour still runs; spotlights just cover a wider area.

# helpers used by on_enter callbacks
def _scroll_dashboard_to_top(dashboard):
    """Scroll the dashboard's scroll-area back to the very top."""
    from PyQt6.QtWidgets import QScrollArea
    for sa in dashboard.findChildren(QScrollArea):
        vb = sa.verticalScrollBar()
        if vb:
            vb.setValue(0)
            break

def _scroll_dashboard_to_history(dashboard):
    """Scroll the dashboard's scroll-area down until the history section is visible."""
    from PyQt6.QtWidgets import QScrollArea, QAbstractScrollArea
    history = dashboard.findChild(QWidget, "historySection")
    for sa in dashboard.findChildren(QScrollArea):
        vb = sa.verticalScrollBar()
        if vb is None:
            continue
        if history:
            # Scroll just enough to show the history widget
            viewport_height = sa.viewport().height()
            pos = history.mapTo(sa.widget(), QPoint(0, 0)).y()
            target_val = max(0, pos - 20)          # 20 px breathing room above
            vb.setValue(target_val)
        else:
            vb.setValue(vb.maximum())
        break

def _build_tour_steps_pitcher(
    pages: dict,
    nav_buttons: dict,
    switch_page,
    content_stack: QWidget,
    overlay_parent: QWidget,
) -> list:
    """
    5-step pitcher tour:
      1. Dashboard — stats section (top half of content area)
      2. Dashboard — pitching history (bottom half of content area)
      3. Start Session page — navigate + spotlight left panel
      4. Account Settings page — navigate + centred card
      5. Finish — return to Dashboard

    Each "target" is a lazy callable so geometry is resolved *after* the page
    switch and Qt repaint have both happened (called from _apply_spotlight via
    a 160 ms QTimer delay).
    """
    dashboard = pages["dashboard"]
    start_page = pages["start_session"]

    # Lazy rect helpers
    PAD = 10   # spotlight padding around widget edges

    def _stats_rect() -> QRect:
        """Top portion of the content area — the six stat cards."""
        # Try the precisely-named widget first
        w = dashboard.findChild(QWidget, "statsSection")
        if w and w.isVisible():
            tl = w.mapTo(overlay_parent, QPoint(0, 0))
            return QRect(tl, w.size()).adjusted(-PAD, -PAD, PAD, PAD)
        # Fallback: top ~46 % of the content stack height
        cs = content_stack
        pos = cs.mapTo(overlay_parent, QPoint(0, 0))
        h = int(cs.height() * 0.46)
        return QRect(pos.x(), pos.y(), cs.width(), h).adjusted(-PAD, -PAD, PAD, PAD)

    def _history_rect() -> QRect:
        """Bottom portion of the content area — the pitching history table."""
        w = dashboard.findChild(QWidget, "historySection")
        if w and w.isVisible():
            tl = w.mapTo(overlay_parent, QPoint(0, 0))
            return QRect(tl, w.size()).adjusted(-PAD, -PAD, PAD, PAD)
        # Fallback: bottom ~54 % of the content stack height
        cs = content_stack
        pos = cs.mapTo(overlay_parent, QPoint(0, 0))
        top_off = int(cs.height() * 0.46)
        return QRect(
            pos.x(),
            pos.y() + top_off,
            cs.width(),
            cs.height() - top_off,
        ).adjusted(-PAD, -PAD, PAD, PAD)

    def _start_panel_rect() -> QRect:
        """Left panel of the Start Session page (camera / session controls)."""
        # Try common objectNames the start session page might use
        for name in ("sessionPanel", "sessionLeftPanel", "startPanel",
                     "sessionControls", "cameraPanel"):
            w = start_page.findChild(QWidget, name)
            if w and w.isVisible():
                tl = w.mapTo(overlay_parent, QPoint(0, 0))
                return QRect(tl, w.size()).adjusted(-PAD, -PAD, PAD, PAD)
        # Fallback: left ~45 % of the content stack – covers a typical left panel
        cs = content_stack
        pos = cs.mapTo(overlay_parent, QPoint(0, 0))
        return QRect(
            pos.x(),
            pos.y(),
            int(cs.width() * 0.45),
            cs.height(),
        ).adjusted(-PAD, -PAD, PAD, PAD)

    # Steps
    steps = [
        # 1: Stats (top half)
        {
            "target": _stats_rect,
            "title": "Your Statistics Overview",
            "body": (
                "These cards show your overall pitching performance. "
                "Total pitches thrown, Total mistakes, Total sessions completed, "
                "and your average pitch, mistake, and accuracy. "
                "Everything here updates automatically after every session."
            ),
            "callout_side": "bottom",
            "on_enter": lambda: (
                switch_page("dashboard"),
                _scroll_dashboard_to_top(dashboard),
            ),
        },
        # 2: History (bottom half)
        {
            "target": _history_rect,
            "title": "Session History",
            "body": (
                "Every session you complete is logged here with its date, "
                "pitch count, mistake count, and accuracy percentage. "
                "Use the pagination arrows at the bottom-right to browse "
                "older sessions and track how your performance improves."
            ),
            "callout_side": "top",
            "on_enter": lambda: (
                switch_page("dashboard"),
                _scroll_dashboard_to_history(dashboard),
            ),
        },
        # 3: Start Session page – spotlight left panel
        {
            "target": _start_panel_rect,
            "title": "Starting a Session",
            "body": (
                "This is the Start Session panel. "
                "This panel on the right shows you the summary of the session, "
                "showing the total pitches thrown, mistakes, accuracy, and pitches left "
                "for the session. You can also freely choose what camera to use by clicking "
                "find camera. Lastly, just stand infront of the camera of your choice and start "
                "the session. The system will track each pitch in real-time, flagging "
                "mistakes and logging your results automatically."
            ),
            "callout_side": "right",
            "on_enter": lambda: switch_page("start_session"),
        },
        # 4: Account Settings
        {
            "target": None,   # centred card over the settings page
            "title": "Account Settings",
            "body": (
                "Here you can personalize your pitching profile:\n"
                "-RHP / LHP lets you set whether you pitch right handed or "
                "left handed.\n"
                "-Pitch Threshold is the pitching limit you can set per session. "
                "It wont exceed the maximum pitch threshold you have per day based on"
                "your age.\n"
                "-Change Password to freely change your password anytime you want."
            ),
            "callout_side": "bottom",
            "on_enter": lambda: switch_page("account_settings"),
        },
        # 5: Finish
        {
            "target": None,
            "title": "You're All Set!",
            "body": (
                "That covers everything you need to get started with "
                "Perfect Pitch. You can replay this tour at any time by "
                "clicking the Guide button in the sidebar. Good luck!"
            ),
            "callout_side": "center",
            "on_enter": lambda: switch_page("dashboard"),
        },
    ]

    return steps


def _build_tour_steps_coach(
    pages: dict,
    nav_buttons: dict,
    switch_page,
    content_stack: QWidget,
    overlay_parent: QWidget,
) -> list:
    dashboard = pages["dashboard"]
    users_page = pages.get("users")

    PAD = 10

    def _stats_rect() -> QRect:
        w = dashboard.findChild(QWidget, "statsSection")
        if w and w.isVisible():
            tl = w.mapTo(overlay_parent, QPoint(0, 0))
            return QRect(tl, w.size()).adjusted(-PAD, -PAD, PAD, PAD)
        cs = content_stack
        pos = cs.mapTo(overlay_parent, QPoint(0, 0))
        h = int(cs.height() * 0.46)
        return QRect(pos.x(), pos.y(), cs.width(), h).adjusted(-PAD, -PAD, PAD, PAD)

    def _history_rect() -> QRect:
        w = dashboard.findChild(QWidget, "historySection")
        if w and w.isVisible():
            tl = w.mapTo(overlay_parent, QPoint(0, 0))
            return QRect(tl, w.size()).adjusted(-PAD, -PAD, PAD, PAD)
        cs = content_stack
        pos = cs.mapTo(overlay_parent, QPoint(0, 0))
        top_off = int(cs.height() * 0.46)
        return QRect(
            pos.x(), pos.y() + top_off,
            cs.width(), cs.height() - top_off,
        ).adjusted(-PAD, -PAD, PAD, PAD)

    def _users_rect() -> QRect:
        """Full content area of the users page."""
        page = users_page or (
            content_stack.currentWidget() if content_stack else None
        )
        if page and page.isVisible():
            tl = page.mapTo(overlay_parent, QPoint(0, 0))
            return QRect(tl, page.size()).adjusted(-PAD, -PAD, PAD, PAD)
        cs = content_stack
        pos = cs.mapTo(overlay_parent, QPoint(0, 0))
        return QRect(pos.x(), pos.y(), cs.width(), cs.height()).adjusted(
            -PAD, -PAD, PAD, PAD
        )

    steps = [
        # 1: Stats (top half)
        {
            "target": _stats_rect,
            "title": "All Players Statistics Overview",
            "body": (
                "These cards give you a summary of all "
                "pitching activities of your players, total pitches, "
                "mistakes, sessions, and averages across all your pitchers."
            ),
            "callout_side": "bottom",
            "on_enter": lambda: (
                switch_page("dashboard"),
                _scroll_dashboard_to_top(dashboard),
            ),
        },
        # 2: History (bottom half)
        {
            "target": _history_rect,
            "title": "Session History",
            "body": (
                "A log of every recorded session across all pitchers. "
                "You can review each pitcher's session date, pitch count, mistake "
                "rate, accuracy percentage, and the 2D skeleton model showing the "
                "severity level of each joints for the pitcher's session. Use the pagination arrows "
                "to browse older sessions."
            ),
            "callout_side": "top",
            "on_enter": lambda: (
                switch_page("dashboard"),
                _scroll_dashboard_to_history(dashboard),
            ),
        },
        # 3: Users page
        {
            "target": _users_rect,
            "title": "Manage Pitchers",
            "body": (
                "This page lists all pitchers registered to the system. "
                "From here you can view each pitcher's individual stats, "
                "check their profile details, or remove them from your "
                "roster. Use the search bar to quickly find a specific "
                "pitcher by name located on the top right of the screen."
            ),
            "callout_side": "bottom",
            "on_enter": lambda: switch_page("pitchers"),
        },
        # 4: Finish
        {
            "target": None,
            "title": "You're All Set!",
            "body": (
                "That's a quick overview of your Coach dashboard. "
                "Click Guide in the sidebar whenever you want to see "
                "this tour again."
            ),
            "callout_side": "center",
            "on_enter": lambda: switch_page("dashboard"),
        },
    ]

    return steps

class MainWindow(FramelessMainWindow):
    def __init__(self, user_id: int, ml_bundle=None):
        super().__init__()
        self.user_id = user_id
        self.ml_bundle = ml_bundle
        self._logging_out = False
        self._session_live = False
        self._active_tour = None    # reference to a live TourOverlay
        self.setWindowTitle("Perfect Pitch")
        self.titleBar.hide()
        self.setResizeEnabled(False)

        # Fetch user role
        from src.db import get_user_by_id
        user = get_user_by_id(user_id)
        self.role = user["role"] if user else "Pitcher"

        # Pick nav items based on role
        if self.role == "Admin":
            self.nav_items = NAV_ADMIN
        elif self.role == "Coach":
            self.nav_items = NAV_COACH
        else:
            self.nav_items = NAV_PITCHER

        self.build_ui()
        self._switch_page("dashboard")

        # Auto-open guided tour for first-time users (Pitcher and Coach only).
        # Deferred via singleShot so the window is fully rendered first.
        if self.role != "Admin":
            from src.db import get_has_seen_guide, set_has_seen_guide
            if not get_has_seen_guide(self.user_id):
                set_has_seen_guide(self.user_id)
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(400, self._launch_tour)

    # platform helpers
    def _disable_rounded_corners(self):
        import sys
        if sys.platform == "win32":
            import ctypes
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DONOTROUND = 1
                hwnd = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)),
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass

    def show(self):
        super().show()
        self._disable_rounded_corners()
        self._go_maximized()

    def _go_maximized(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(screen.width(), screen.height())
        self.move(screen.x(), screen.y())
        self.showMaximized()

    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if not self.isMinimized() and not self.isMaximized():
                self._go_maximized()
        super().changeEvent(event)

    def build_ui(self):
        root = QWidget()
        root.setObjectName("mainRoot")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Logo
        logo_widget = QWidget()
        logo_widget.setObjectName("sidebarLogo")
        logo_widget.setFixedHeight(72)
        logo_col = QVBoxLayout(logo_widget)
        logo_col.setContentsMargins(24, 0, 24, 0)
        logo_col.setSpacing(5)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(2)
        logo_icon = QLabel()
        logo_icon.setObjectName("sidebarLogoIcon")
        logo_icon.setFixedSize(22, 22)
        logo_icon.setPixmap(get_icon("ball-baseball", color="#ffffff", size=22).pixmap(22, 22))
        logo_text = QLabel("<u>PERFECT PITCH</u>.")
        logo_text.setObjectName("sidebarLogoText")
        logo_text.setTextFormat(Qt.TextFormat.RichText)
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()

        logo_col.addStretch()
        logo_col.addLayout(logo_row)
        logo_col.addStretch()
        sb_layout.addWidget(logo_widget)
        sb_layout.addSpacing(8)

        # Nav section label
        nav_section = QLabel("MENU")
        nav_section.setObjectName("navSectionLabel")
        nav_section.setContentsMargins(24, 8, 0, 4)
        sb_layout.addWidget(nav_section)

        # Nav buttons
        self.nav_buttons = {}
        for key, icon_name, label in self.nav_items:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("navBtn")
            btn.setFixedHeight(44)
            btn.setIcon(get_icon(icon_name, color="#666666", size=18))
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key, i=icon_name: self._switch_page(k, i))
            self.nav_buttons[key] = btn
            sb_layout.addWidget(btn)

        # Role badge
        sb_layout.addSpacing(12)
        role_badge = QLabel(self.role.upper())
        role_badge.setObjectName(f"roleBadge{self.role}")
        role_badge.setContentsMargins(24, 0, 0, 0)
        sb_layout.addWidget(role_badge)

        sb_layout.addStretch()

        # Help / Guide button (Pitcher and Coach only)
        if self.role != "Admin":
            self.guide_btn = QPushButton("  Guide")
            self.guide_btn.setObjectName("guideBtn")
            self.guide_btn.setFixedHeight(44)
            self.guide_btn.setIcon(get_icon("help", color="#555555", size=18))
            self.guide_btn.setIconSize(QSize(18, 18))
            self.guide_btn.setToolTip("Start interactive guide")
            self.guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.guide_btn.clicked.connect(self._launch_tour)
            sb_layout.addWidget(self.guide_btn)
        else:
            self.guide_btn = None

        # Account Settings
        divider = QWidget()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        sb_layout.addWidget(divider)

        acc_btn = QPushButton("  Account Settings")
        acc_btn.setObjectName("navBtn")
        acc_btn.setFixedHeight(44)
        acc_btn.setIcon(get_icon("settings", color="#666666", size=18))
        acc_btn.setIconSize(QSize(18, 18))
        acc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        acc_btn.setCheckable(True)
        acc_btn.clicked.connect(lambda: self._switch_page("account_settings", "settings"))
        self.nav_buttons["account_settings"] = acc_btn
        sb_layout.addWidget(acc_btn)
        sb_layout.addSpacing(8)

        # User info at bottom
        self._load_user_info(sb_layout)

        # Content stack
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")

        self.pages = {
            "dashboard":       DashboardPage(self.user_id),
            "pitchers":        PitchersPage(),
            "users":           UsersPage(),
            "start_session":   StartSessionPage(self.user_id, ml_bundle=self.ml_bundle),
            "account_settings": AccountSettingsPage(self.user_id),
        }

        for page in self.pages.values():
            self.stack.addWidget(page)

        self.pages["account_settings"].profile_updated.connect(self._reload_user_info)

        ss = self.pages["start_session"]
        ss.session_started.connect(self._lock_nav)
        ss.session_finished.connect(self._unlock_nav)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack)

        # Window buttons
        self.win_btns = WindowButtons(parent=root)
        self.win_btns.adjustSize()
        bw = self.win_btns.sizeHint().width()
        self.win_btns.move(self.screen().availableGeometry().width() - bw - 10, 10)
        self.win_btns.raise_()

    # Tour
    def _launch_tour(self):
        """Open the interactive guided tour overlay."""
        # Close any existing tour first
        if self._active_tour is not None:
            try:
                self._active_tour.close_tour()
            except Exception:
                pass
            self._active_tour = None

        # Always start on the dashboard so the spotlights make sense
        self._switch_page("dashboard")

        # Build role-appropriate steps (pass switch_page so on_enter callbacks
        # can navigate to the right page during the tour)
        if self.role == "Coach":
            steps = _build_tour_steps_coach(
                self.pages,
                self.nav_buttons,
                self._switch_page,
                self.stack,
                self.centralWidget(),
            )
        else:
            steps = _build_tour_steps_pitcher(
                self.pages,
                self.nav_buttons,
                self._switch_page,
                self.stack,                # QStackedWidget – content area
                self.centralWidget(),      # overlay parent – full window minus title bar
            )

        from src.widgets.tour_overlay import TourOverlay
        overlay = TourOverlay(self.centralWidget(), steps)
        overlay.closed.connect(self._on_tour_closed)
        self._active_tour = overlay

        # Highlight the Guide button while the tour is open
        if self.guide_btn:
            self.guide_btn.setObjectName("guideBtnActive")
            self.guide_btn.setIcon(get_icon("help", color="#ffffff", size=18))
            self.guide_btn.style().unpolish(self.guide_btn)
            self.guide_btn.style().polish(self.guide_btn)

    def _on_tour_closed(self):
        self._active_tour = None
        # Restore guide button appearance
        if self.guide_btn:
            self.guide_btn.setObjectName("guideBtn")
            self.guide_btn.setIcon(get_icon("help", color="#555555", size=18))
            self.guide_btn.style().unpolish(self.guide_btn)
            self.guide_btn.style().polish(self.guide_btn)

    # Sidebar user info
    def _load_user_info(self, sb_layout):
        from src.db import get_user_by_id
        user = get_user_by_id(self.user_id)

        bottom = QWidget()
        bottom.setObjectName("sidebarBottom")
        bottom.setFixedHeight(64)
        row = QHBoxLayout(bottom)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)

        initials = ""
        if user:
            first = user["first_name"].strip()
            last = user["last_name"].strip()
            initials = f"{first[0]}{last[0]}".upper() if first and last else "?"

        avatar = QLabel(initials)
        avatar.setObjectName("userAvatar")
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        full_name = f"{user['first_name']} {user['last_name']}" if user else "User"
        email_text = user["email"] if user else ""

        info_lbl = QLabel(
            f'<span style="font-size:13px; font-weight:600; color:#e0e0e0;">{full_name}</span>'
            f'<br>'
            f'<span style="font-size:11px; color:#555555;">{email_text}</span>'
        )
        info_lbl.setTextFormat(Qt.TextFormat.RichText)
        info_lbl.setObjectName("userInfoLabel")
        info_lbl.setMaximumWidth(175)

        logout_btn = QPushButton()
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setFixedSize(28, 28)
        logout_btn.setIcon(get_icon("logout", color="#555555", size=16))
        logout_btn.setIconSize(QSize(16, 16))
        logout_btn.setToolTip("Logout")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(lambda: self._logout())

        row.addWidget(avatar)
        row.addWidget(info_lbl)
        row.addStretch()
        row.addWidget(logout_btn)
        sb_layout.addWidget(bottom)
        self._sidebar_bottom = bottom
        self._sb_layout = sb_layout

    def _reload_user_info(self):
        self._sidebar_bottom.setVisible(False)
        self._sidebar_bottom.deleteLater()
        self._load_user_info(self._sb_layout)

    # Page switching
    def _switch_page(self, key: str, icon_name: str = None):
        icon_map = {k: i for k, i, _ in self.nav_items}
        icon_map["account_settings"] = "settings"

        for k, btn in self.nav_buttons.items():
            is_active = k == key
            btn.setChecked(is_active)
            btn.setObjectName("navBtnActive" if is_active else "navBtn")
            btn.setIcon(get_icon(icon_map[k], color="#ffffff" if is_active else "#666666", size=18))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        page = self.pages[key]
        self.stack.setCurrentWidget(page)

        if hasattr(page, "refresh"):
            page.refresh()

    # Session lock / unlock
    def _lock_nav(self):
        """Disable all nav and window actions while a session is live."""
        self._session_live = True
        for btn in self.nav_buttons.values():
            btn.setEnabled(False)
        if self.guide_btn:
            self.guide_btn.setEnabled(False)
        # Close any active tour
        if self._active_tour is not None:
            try:
                self._active_tour.close_tour()
            except Exception:
                pass
            self._active_tour = None
        bottom = getattr(self, "_sidebar_bottom", None)
        if bottom:
            for child in bottom.findChildren(QPushButton):
                if child.objectName() == "logoutBtn":
                    child.setEnabled(False)
        if hasattr(self, "win_btns"):
            self.win_btns.setEnabled(False)

    def _unlock_nav(self):
        """Re-enable all nav and window actions after session ends."""
        self._session_live = False
        for btn in self.nav_buttons.values():
            btn.setEnabled(True)
        if self.guide_btn:
            self.guide_btn.setEnabled(True)
        bottom = getattr(self, "_sidebar_bottom", None)
        if bottom:
            for child in bottom.findChildren(QPushButton):
                if child.objectName() == "logoutBtn":
                    child.setEnabled(True)
        if hasattr(self, "win_btns"):
            self.win_btns.setEnabled(True)

    def closeEvent(self, event):
        if self._logging_out:
            event.accept()
            return
        if self._session_live:
            event.ignore()
            return
        dlg = ConfirmDialog(self, title="Exit Perfect Pitch", message="Are you sure you want to exit?")
        dlg.exec()
        if dlg.result_yes():
            event.accept()
        else:
            event.ignore()

    def _logout(self):
        from src.windows.auth_window import AuthWindow
        dlg = ConfirmDialog(self, title="Logout", message="Are you sure you want to log out?")
        dlg.exec()
        if not dlg.result_yes():
            return
        from src.utils.toast import dismiss_active_toast
        dismiss_active_toast()
        self._logging_out = True
        self.login = AuthWindow()
        self.login.show()
        self.close()
