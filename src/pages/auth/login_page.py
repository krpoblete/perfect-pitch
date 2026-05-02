from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton
)
from PyQt6.QtCore import Qt
from src.utils.icons import get_icon
from src.utils.toast import toast_error
from src.widgets.password_input import PasswordInput

class LoginPage(QWidget):
    def __init__(self, auth_window):
        super().__init__()
        self.auth = auth_window
        self.setObjectName("loginLeft")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(80, 55, 80, 55)
        layout.setSpacing(0)

        # Logo
        logo_row = QHBoxLayout()
        logo_row.setSpacing(2)
        logo_icon = QLabel()
        logo_icon.setObjectName("logoIcon")
        logo_icon.setFixedSize(22, 22)
        logo_icon.setPixmap(get_icon("ball-baseball", color="#ffffff", size=22).pixmap(22, 22))
        logo_text = QLabel("<u>PERFECT PITCH</u>.")
        logo_text.setObjectName("logoText")
        logo_text.setTextFormat(Qt.TextFormat.RichText)
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        layout.addLayout(logo_row)

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

        # Password
        pw_row = QHBoxLayout()
        pw_label = QLabel("Password")
        pw_label.setObjectName("fieldLabel")
        forgot = QPushButton("Forgot your password?")
        forgot.setObjectName("linkBtn")
        forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot.clicked.connect(lambda: self.auth.show_page("forgot"))
        pw_row.addWidget(pw_label)
        pw_row.addStretch()
        pw_row.addWidget(forgot)
        layout.addLayout(pw_row)
        layout.addSpacing(8)

        self.pw_input = PasswordInput("") 
        layout.addWidget(self.pw_input)

        layout.addSpacing(26)

        # Login button
        login_btn = QPushButton("Login")
        login_btn.setObjectName("loginBtn")
        login_btn.setFixedHeight(50)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._handle_login)
        layout.addWidget(login_btn)

        layout.addSpacing(16)

        # Sign up link
        signup_row = QHBoxLayout()
        signup_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_acc = QLabel("Don't have an account?")
        no_acc.setObjectName("loginSubtitle")
        signup_link = QPushButton("Sign up")
        signup_link.setObjectName("linkBtn")
        signup_link.setCursor(Qt.CursorShape.PointingHandCursor)
        signup_link.clicked.connect(lambda: self.auth.show_page("signup"))
        signup_row.addWidget(no_acc)
        signup_row.addWidget(signup_link)
        layout.addLayout(signup_row)

        layout.addStretch()

        # Enter key navigation
        self.email_input.returnPressed.connect(self.pw_input.line_edit.setFocus)
        self.pw_input.line_edit.returnPressed.connect(self._handle_login)

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl
    
    def _input(self, placeholder):
        inp = QLineEdit()
        inp.setObjectName("authInput")
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(48)
        return inp

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

        def _close():
            self.auth._suppress_close_dialog = True
            self.auth.close()
            self.main_window = MainWindow(user_id=user["id"], ml_bundle=ml_bundle)
            self.main_window.show()

        fade_out(self.auth, on_finish=_close)
