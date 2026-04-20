import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize
from qframelesswindow import FramelessMainWindow

from src.pages.dashboard_page import DashboardPage
from src.pages.tutorial_page import TutorialPage
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
    ("tutorial", "help", "Tutorial"),
    ("start_session", "play-handball", "Start Session"),
]

NAV_COACH = [
    ("dashboard", "home", "Dashboard"),
    ("tutorial", "help", "Tutorial"),
    ("pitchers", "users", "Pitchers"),
]

NAV_ADMIN = [
    ("dashboard", "home", "Dashboard"),
    ("tutorial", "help", "Tutorial"),
    ("users", "users-group", "Users"),
    ("start_session", "play-handball", "Start Session"),
]

class MainWindow(FramelessMainWindow):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self._logging_out = False
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

        # Account Settings
        divider = QWidget()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        sb_layout.addWidget(divider)

        acc_btn = QPushButton("Account Settings")
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
            "tutorial": TutorialPage(),
            "pitchers": PitchersPage(),
            "users": UsersPage(),
            "start_session": StartSessionPage(self.user_id),
            "account_settings": AccountSettingsPage(self.user_id),
        }

        # Give tutorial page the user's role
        self.pages["tutorial"].set_role(self.role)
        for page in self.pages.values():
            self.stack.addWidget(page)

        # Connect account settings signal to sidebar refresh
        self.pages["account_settings"].profile_updated.connect(self._reload_user_info)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack)

        # Window buttons
        self.win_btns = WindowButtons(parent=root)
        self.win_btns.adjustSize()
        bw = self.win_btns.sizeHint().width()
        self.win_btns.move(self.screen().availableGeometry().width() - bw - 10, 10)
        self.win_btns.raise_()

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
        # Stop tutorial video when leaving the page
        tutorial = self.pages.get("tutorial")
        if tutorial and key != "tutorial":
            tutorial._player.stop()

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

    def closeEvent(self, event):
        if self._logging_out:
            event.accept()
            return
        dlg = ConfirmDialog(self, title="Exit Perfect Pitch", message="Are you sure you want to exit?")
        dlg.exec()
        if dlg.result_yes():
            tutorial = self.pages.get("tutorial")
            if tutorial:
                tutorial._player.stop() 
            event.accept()
        else:
            event.ignore()

    def _logout(self):
        from src.windows.auth_window import AuthWindow
        dlg = ConfirmDialog(self, title="Logout", message="Are you sure you want to log out?")
        dlg.exec() 
        if not dlg.result_yes():
            return
        # Stop tutorial video if playing
        tutorial = self.pages.get("tutorial")
        if tutorial:
            tutorial._player.stop() 
        from src.utils.toast import dismiss_active_toast
        dismiss_active_toast()
        self._logging_out = True
        self.login = AuthWindow()
        self.login.show()
        self.close()
