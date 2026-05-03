import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
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

# Guide actions per role: (label, icon_name, page_key or None)
GUIDE_ACTIONS = {
    "Pitcher": [
        ("View Dashboard",       "home",          "dashboard"),
        ("Start Session",        "play-handball", "start_session"),
        ("View Result",          "target",        "dashboard"),
        ("Account Settings",     "settings",      "account_settings"),
        ("Edit Pitch Threshold", "settings",      "account_settings"),
    ],
    "Coach": [
        ("View Dashboard",   "home",  "dashboard"),
        ("View Pitchers",    "users", "pitchers"),
        ("Remove Pitcher",   "trash", "pitchers"),
        ("Remove Own Account", "logout", "account_settings"),
    ],
}

class MainWindow(FramelessMainWindow):
    def __init__(self, user_id: int, ml_bundle=None):
        super().__init__()
        self.user_id = user_id
        self.ml_bundle = ml_bundle
        self._logging_out = False
        self._session_live = False
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

        self._guide_open = False
        self.build_ui()
        self._switch_page("dashboard")

        # Auto-open guide for first-time users (Pitcher and Coach only)
        # Deferred via singleShot so it runs after show() + _go_maximized(),
        # preventing the window from briefly rendering at its default small size.
        if self.role != "Admin":
            from src.db import get_has_seen_guide, set_has_seen_guide
            if not get_has_seen_guide(self.user_id):
                set_has_seen_guide(self.user_id)
                # self._open_guide()
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(300, self._open_guide)

    def _disable_rounded_corners(self):
        """Remove rounded corners on the main window (Windows 11 only)."""
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

        # Guide button + drawer (Pitcher and Coach only)
        if self.role != "Admin":
            self.guide_btn = QPushButton("  Help")
            self.guide_btn.setObjectName("guideBtn")
            self.guide_btn.setFixedHeight(44)
            self.guide_btn.setIcon(get_icon("help", color="#555555", size=18))
            self.guide_btn.setIconSize(QSize(18, 18))
            self.guide_btn.setToolTip("Quick guide")
            self.guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.guide_btn.clicked.connect(self._toggle_guide)
            sb_layout.addWidget(self.guide_btn)

            # Drawer — hidden by default via maximumHeight animation
            self.guide_drawer = self._build_guide_drawer()
            self.guide_drawer.setMaximumHeight(0)
            self.guide_drawer.setVisible(True)
            sb_layout.addWidget(self.guide_drawer)
        else:
            self.guide_btn = None
            self.guide_drawer = None

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
            "dashboard": DashboardPage(self.user_id),
            "pitchers": PitchersPage(),
            "users": UsersPage(),
            "start_session": StartSessionPage(self.user_id, ml_bundle=self.ml_bundle),
            "account_settings": AccountSettingsPage(self.user_id),
        }

        # Hide all pages before adding to the stack — prevents Qt from briefly
        # painting unparented QWidgets as top-level windows on first show().
        for page in self.pages.values():
            page.hide()

        for page in self.pages.values():
            self.stack.addWidget(page)

        # Connect account settings signal to sidebar refresh
        self.pages["account_settings"].profile_updated.connect(self._reload_user_info)

        # Lock nav during a session, unlock after
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


    def _build_guide_drawer(self) -> QWidget:
        """Build the inline sidebar drawer for the quick guide."""
        drawer = QWidget()
        drawer.setObjectName("guideDrawer")
        drawer.setSizePolicy(
            drawer.sizePolicy().horizontalPolicy(),
            __import__("PyQt6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Policy.Fixed
        )

        outer = QVBoxLayout(drawer)
        outer.setContentsMargins(12, 4, 12, 8)
        outer.setSpacing(4)

        # Role label
        role_lbl = QLabel(f"{self.role} Actions")
        role_lbl.setObjectName("guideDrawerRoleLabel")
        outer.addWidget(role_lbl)

        outer.addSpacing(2)

        # Action rows
        actions = GUIDE_ACTIONS.get(self.role, GUIDE_ACTIONS["Pitcher"])
        seen = set()
        for label, icon_name, page_key in actions:
            uid = (label, page_key)
            if uid in seen:
                continue
            seen.add(uid)

            row_btn = QPushButton()
            row_btn.setObjectName("guideActionRow")
            row_btn.setFixedHeight(40)
            row_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            row_layout = QHBoxLayout(row_btn)
            row_layout.setContentsMargins(10, 0, 10, 0)
            row_layout.setSpacing(10)

            icon_lbl = QLabel()
            icon_lbl.setObjectName("guideActionIcon")
            icon_lbl.setFixedSize(16, 16)
            icon_lbl.setPixmap(get_icon(icon_name, color="#555555", size=16).pixmap(16, 16))
            icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            text_lbl = QLabel(label)
            text_lbl.setObjectName("guideActionLabel")
            text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            arrow_lbl = QLabel("›")
            arrow_lbl.setObjectName("guideActionArrow")
            arrow_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            row_layout.addWidget(icon_lbl)
            row_layout.addWidget(text_lbl)
            row_layout.addStretch()
            row_layout.addWidget(arrow_lbl)

            def _make_handler(key):
                def _handler():
                    if self._session_live:
                        from src.utils.toast import toast_warning
                        toast_warning(self, "Finish your session before navigating.")
                        return
                    self._close_guide()
                    self._switch_page(key)
                return _handler

            row_btn.clicked.connect(_make_handler(page_key))
            outer.addWidget(row_btn)

        return drawer

    def _get_drawer_full_height(self) -> int:
        """Calculate the natural height of the drawer content."""
        if not self.guide_drawer:
            return 0
        self.guide_drawer.setMaximumHeight(16777215)
        h = self.guide_drawer.sizeHint().height()
        self.guide_drawer.setMaximumHeight(
            0 if not self._guide_open else h
        )
        return h

    def _toggle_guide(self):
        """Animate the guide drawer open or closed."""
        if self._guide_open:
            self._close_guide()
        else:
            self._open_guide()

    def _open_guide(self):
        if not self.guide_drawer:
            return
        self._guide_open = True
        full_h = self._get_drawer_full_height()
        anim = QPropertyAnimation(self.guide_drawer, b"maximumHeight", self)
        anim.setDuration(180)
        anim.setStartValue(self.guide_drawer.maximumHeight())
        anim.setEndValue(full_h)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._guide_anim = anim  # keep reference alive
        # Update button style
        if self.guide_btn:
            self.guide_btn.setObjectName("guideBtnActive")
            self.guide_btn.setIcon(get_icon("help", color="#ffffff", size=18))
            self.guide_btn.style().unpolish(self.guide_btn)
            self.guide_btn.style().polish(self.guide_btn)

    def _close_guide(self):
        if not self.guide_drawer:
            return
        self._guide_open = False
        anim = QPropertyAnimation(self.guide_drawer, b"maximumHeight", self)
        anim.setDuration(150)
        anim.setStartValue(self.guide_drawer.maximumHeight())
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.start()
        self._guide_anim = anim
        # Restore button style
        if self.guide_btn:
            self.guide_btn.setObjectName("guideBtn")
            self.guide_btn.setIcon(get_icon("help", color="#555555", size=18))
            self.guide_btn.style().unpolish(self.guide_btn)
            self.guide_btn.style().polish(self.guide_btn)

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
        """Rebuild the sidebar bottom user info after a profile update."""
        self._sidebar_bottom.setVisible(False)
        self._sidebar_bottom.deleteLater()
        self._load_user_info(self._sb_layout)

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

    def _lock_nav(self):
        """Disable all nav buttons and window actions while a session is live."""
        self._session_live = True
        for btn in self.nav_buttons.values():
            btn.setEnabled(False)
        if self.guide_btn is not None:
            self.guide_btn.setEnabled(False)
            self._close_guide()
        if self.guide_drawer is not None:
            for child in self.guide_drawer.findChildren(QPushButton):
                child.setEnabled(False)
        bottom = getattr(self, "_sidebar_bottom", None)
        if bottom:
            for child in bottom.findChildren(QPushButton):
                if child.objectName() == "logoutBtn":
                    child.setEnabled(False)
        if hasattr(self, "win_btns"):
            self.win_btns.setEnabled(False)

    def _unlock_nav(self):
        """Re-enable all nav, logout, and window actions after session ends."""
        self._session_live = False
        for btn in self.nav_buttons.values():
            btn.setEnabled(True)
        if self.guide_btn is not None:
            self.guide_btn.setEnabled(True)
        if self.guide_drawer is not None:
            for child in self.guide_drawer.findChildren(QPushButton):
                child.setEnabled(True)
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
