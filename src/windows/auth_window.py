import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap
from qframelesswindow import FramelessMainWindow
from src.utils.animations import fade_in
from src.config import ASSETS_DIR
from src.widgets.window_buttons import WindowButtons
from src.widgets.confirm_dialog import ConfirmDialog
from src.pages.auth.login_page import LoginPage
from src.pages.auth.signup_page import SignupPage
from src.pages.auth.forgot_password_page import ForgotPasswordPage

WIN_W, WIN_H = 1200, 700

class AuthWindow(FramelessMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Perfect Pitch")
        self.setFixedSize(QSize(WIN_W, WIN_H))
        self.titleBar.hide()
        self.setResizeEnabled(False)
        self._suppress_close_dialog = False
        self._center_on_screen()
        self._build_ui()
        fade_in(self)

    def closeEvent(self, event):
        if self._suppress_close_dialog:
            event.accept()
            return
        dlg = ConfirmDialog(self, title="Exit Perfect Pitch", message="Are you sure you want to exit?")
        dlg.exec() 
        if dlg.result_yes():
            event.accept()
        else:
            event.ignore()

    def _center_on_screen(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - WIN_W) // 2,
            (screen.height() - WIN_H) // 2
        )

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("loginRoot")
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left panel — stacked pages
        left = QWidget()
        left.setObjectName("loginLeft")
        left.setFixedWidth(600)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("authStack")

        self.login_page = LoginPage(auth_window=self)
        self.signup_page = SignupPage(auth_window=self)
        self.forgot_page = ForgotPasswordPage(auth_window=self)

        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.signup_page)
        self.stack.addWidget(self.forgot_page)

        self._pages = {
            "login": 0,
            "signup": 1,
            "forgot": 2
        }

        left_layout.addWidget(self.stack)

        # Right panel — image
        right = QWidget()
        right.setObjectName("loginRight")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        image_label = QLabel()
        image_label.setObjectName("rightPanelImage")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(os.path.join(ASSETS_DIR, "side-banner.png"))
        image_label.setPixmap(pixmap.scaled(
            600, WIN_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        ))
        image_label.setFixedSize(600, WIN_H)
        right_layout.addWidget(image_label)

        main_layout.addWidget(left)
        main_layout.addWidget(right)

        # Window buttons
        self.win_btns = WindowButtons(parent=root)
        self.win_btns.adjustSize()
        bw = self.win_btns.sizeHint().width()
        self.win_btns.move(WIN_W - bw - 10, 10)
        self.win_btns.raise_()

    def show_page(self, page: str):
        """Switch to a named page and reset all forms to defaults."""
        for p in [self.login_page, self.signup_page, self.forgot_page]:
            if hasattr(p, "clear"):
                p.clear()
        target = self._pages.get(page, 0)
        self.stack.setCurrentIndex(target)
