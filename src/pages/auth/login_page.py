from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton
)
from PyQt6.QtCore import Qt

from src.utils.toast import toast_error
from src.widgets.password_input import PasswordInput
from src.pages.auth.auth_base import AuthBasePage

class LoginPage(AuthBasePage):
    def __init__(self, auth_window):
        super().__init__()
        self.auth = auth_window
        self.setObjectName("loginLeft")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(80, 55, 80, 55)
        layout.setSpacing(0)

        layout.addLayout(self._logo_row())
        layout.addStretch()

        # Title
        title = QLabel("Login to your account")
        title.setObjectName("loginTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel("Enter your email below to login to your account")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(32)

        # Email
        layout.addWidget(self._label("Email"))
        layout.addSpacing(8)
        self.email_input = self._input("sample@gmail.com") 
        layout.addWidget(self.email_input)

        layout.addSpacing(18)

        # Password Row with Forgot Link
        pw_row = QHBoxLayout()
        pw_row.addWidget(self._label("Password"))
        pw_row.addStretch()
        forgot = QPushButton("Forgot your password?")
        forgot.setObjectName("linkBtn")
        forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot.clicked.connect(lambda: self.auth.show_page("forgot"))
        pw_row.addWidget(forgot)
        layout.addLayout(pw_row)
        layout.addSpacing(8)

        self.pw_input = PasswordInput("") 
        layout.addWidget(self.pw_input)

        layout.addSpacing(26)

        # Login Button
        login_btn = QPushButton("Login")
        login_btn.setObjectName("loginBtn")
        login_btn.setFixedHeight(50)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._handle_login)
        layout.addWidget(login_btn)

        layout.addSpacing(16)

        # Sign up Link
        signup_row = QHBoxLayout()
        signup_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        signup_row.addWidget(self._label_plain("Don't have an account?"))
        signup_link = QPushButton("Sign up")
        signup_link.setObjectName("linkBtn")
        signup_link.setCursor(Qt.CursorShape.PointingHandCursor)
        signup_link.clicked.connect(lambda: self.auth.show_page("signup"))
        signup_row.addWidget(signup_link)
        layout.addLayout(signup_row)

        layout.addStretch()

        # Enter Key Navigation
        self.email_input.returnPressed.connect(self.pw_input.line_edit.setFocus)
        self.pw_input.line_edit.returnPressed.connect(self._handle_login)

    def _label_plain(self, text: str) -> QLabel:
        """Subtitle-styled label (not a field heading)."""
        lbl = QLabel(text)
        lbl.setObjectName("loginSubtitle")
        return lbl

    def clear(self):
        self.email_input.clear()
        self.pw_input.clear()

    def  _handle_login(self):
        from src.db import get_user_by_email, verify_password
        from src.windows.main_window import MainWindow
        from src.utils.animations import fade_out

        email = self.email_input.text().strip()
        password = self.pw_input.text()

        if not email or not password:
            toast_error(self, "Please fill in all fields.")
            return
        
        user = get_user_by_email(email)
        if user is None or not verify_password(password, user["password"]):
            toast_error(self, "Invalid email or password.")
            return

        ml_bundle = getattr(self.auth, "ml_bundle", None)
        self.main_window = MainWindow(user_id=user["id"], ml_bundle=ml_bundle)
        self.main_window.show()

        def _close():
            self.auth._suppress_close_dialog = True
            self.auth.close()

        fade_out(self.auth, on_finish=_close)
