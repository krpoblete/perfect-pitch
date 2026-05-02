from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDateEdit, QStackedWidget
)
from PyQt6.QtCore import Qt, QDate, QTimer
from src.utils.icons import get_icon
from src.utils.toast import toast_error, toast_success, toast_info
from src.widgets.password_input import PasswordInput

MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 15 

class ForgotPasswordPage(QWidget):
    def __init__(self, auth_window):
        super().__init__()
        self.auth = auth_window
        self.setObjectName("loginLeft")
        
        self._attempts = 0
        self._locked_until = None
        self._verified_user_id = None
        self._lockout_timer = QTimer(self)
        self._lockout_timer.timeout.connect(self._update_lockout) 
        
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("authStack")

        self.stack.addWidget(self._build_verify_page())
        self.stack.addWidget(self._build_reset_page())

        layout.addWidget(self.stack)

    # Page 1: Verify email + DOB
    def _build_verify_page(self):
        page = QWidget() 
        page.setObjectName("loginLeft") 
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 55, 80, 55)
        layout.setSpacing(0)

        # Logo
        layout.addLayout(self._logo_row())
        layout.addStretch()

        # Title
        title = QLabel("Forgot your password?")
        title.setObjectName("loginTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel("Enter your email and date of birth to continue")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(32)

        # Email
        layout.addWidget(self._label("Email"))
        layout.addSpacing(8)
        self.verify_email_input = self._input("sample@gmail.com")
        layout.addWidget(self.verify_email_input)

        layout.addSpacing(18)

        # Date of Birth
        layout.addWidget(self._label("Date of Birth"))
        layout.addSpacing(8)
        self.verify_dob_input = QDateEdit()
        self.verify_dob_input.setObjectName("authInput")
        self.verify_dob_input.setFixedHeight(48)
        self.verify_dob_input.setCalendarPopup(True)
        self.verify_dob_input.setDisplayFormat("MMMM/dd/yyyy")
        self.verify_dob_input.setDate(QDate(2000, 1, 1))
        self.verify_dob_input.setMaximumDate(QDate.currentDate())
        layout.addWidget(self.verify_dob_input)

        layout.addSpacing(12)

        # Lockout label
        self.lockout_label = QLabel("")
        self.lockout_label.setObjectName("lockoutLabel")
        self.lockout_label.setWordWrap(True)
        self.lockout_label.hide()
        layout.addWidget(self.lockout_label)

        layout.addSpacing(14)

        # Continue button
        self.verify_btn = QPushButton("Continue")
        self.verify_btn.setObjectName("loginBtn")
        self.verify_btn.setFixedHeight(50)
        self.verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_btn.clicked.connect(self._handle_verify)
        layout.addWidget(self.verify_btn)

        layout.addSpacing(16)

        # Back to login
        back_row = QHBoxLayout()
        back_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back_lbl = QLabel("Remembered your password?")
        back_lbl.setObjectName("loginSubtitle")
        back_btn = QPushButton("Log in")
        back_btn.setObjectName("linkBtn")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self._go_back)
        back_row.addWidget(back_lbl)
        back_row.addWidget(back_btn)
        layout.addLayout(back_row)

        layout.addStretch()

        # Enter key navigation
        self.verify_email_input.returnPressed.connect(self._handle_verify)

        return page
    
    # Page 2: Set new password
    def _build_reset_page(self):
        page = QWidget()
        page.setObjectName("loginLeft")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 55, 80, 55)
        layout.setSpacing(0)

        layout.addLayout(self._logo_row())
        layout.addStretch()

        title = QLabel("Set a new password")
        title.setObjectName("loginTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel("Choose a strong password for your account")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(32)

        # New Password
        layout.addWidget(self._label("New Password"))
        layout.addSpacing(8)
        self.new_pw_input = PasswordInput("Minimum 8 characters")
        layout.addWidget(self.new_pw_input)

        layout.addSpacing(18)

        # Confirm Password 
        layout.addWidget(self._label("Confirm Password"))
        layout.addSpacing(8)
        self.confirm_pw_input = PasswordInput("Re-enter your password")
        layout.addWidget(self.confirm_pw_input)

        layout.addSpacing(26)

        # Reset button
        reset_btn = QPushButton("Reset Password")
        reset_btn.setObjectName("loginBtn")
        reset_btn.setFixedHeight(50)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._handle_reset)
        layout.addWidget(reset_btn)

        layout.addSpacing(16)

        # Back to verify
        back_row = QHBoxLayout()
        back_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back_lbl = QLabel("Wrong account?")
        back_lbl.setObjectName("loginSubtitle")
        back_btn = QPushButton("Go back")
        back_btn.setObjectName("linkBtn")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        back_row.addWidget(back_lbl)
        back_row.addWidget(back_btn)
        layout.addLayout(back_row)

        layout.addStretch()

        # Enter key navigation
        self.new_pw_input.line_edit.returnPressed.connect(self.confirm_pw_input.line_edit.setFocus)
        self.confirm_pw_input.line_edit.returnPressed.connect(self._handle_reset)

        return page
    
    # Handlers
    def _handle_verify(self):
        # Check lockout
        if self._locked_until and datetime.now() < self._locked_until:
            return
        
        from src.db import get_user_by_email
        from src.utils.validators import validate_email

        email = self.verify_email_input.text().strip()
        dob = self.verify_dob_input.date().toString("yyyy-MM-dd")

        if not email:
            toast_error(self, "Please enter your email address.")
            return

        # Validate domain — don't count as an attempt
        valid, msg = validate_email(email)
        if not valid:
            toast_error(self, msg)
            return

        user = get_user_by_email(email)

        if user is None or user["date_of_birth"] != dob:
            self._attempts += 1
            remaining = MAX_ATTEMPTS - self._attempts

            if self._attempts >= MAX_ATTEMPTS:
                self._locked_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
                self.verify_btn.setEnabled(False)
                self.lockout_label.show()
                self._lockout_timer.start(1000)
                self._update_lockout()
            else:
                toast_error(self, f"Email or date of birth is incorrect. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")
            return
        
        # Match — store user id and proceed to reset page
        self._verified_user_id = user["id"]
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
        self.stack.setCurrentIndex(1)

    def _handle_reset(self):
        import bcrypt
        from src.db import get_connection, get_user_by_id

        password = self.new_pw_input.text()
        confirm = self.confirm_pw_input.text()

        if not password or not confirm:
            toast_error(self, "Please fill in all fields.")
            return

        from src.utils.validators import validate_password
        valid_pw, pw_msg = validate_password(password)
        if not valid_pw:
            toast_error(self, pw_msg)
            return
        if password != confirm:
            toast_error(self, "Passwords do not match. Please try again.")
            return

        # Check new password is different from current
        user = get_user_by_id(self._verified_user_id)
        if user and bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            toast_info(self, "New password must be different from your current password.")
            return 

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        conn = get_connection()
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed.decode("utf-8"), self._verified_user_id),
        )
        conn.commit()
        conn.close()

        toast_success(self, "Password reset successfully. Please log in.")
        self._reset_state()
        self.auth.show_page("login")

    def _update_lockout(self):
        if not self._locked_until:
            return
        remaining = self._locked_until - datetime.now()
        if remaining.total_seconds() <= 0:
            self._lockout_timer.stop()
            self._locked_until = None
            self._attempts = 0
            self.verify_btn.setEnabled(True)
            self.lockout_label.hide()
            self.lockout_label.setText("")
        else:
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            self.lockout_label.setText(
                f"Too many failed attempts. Try again in {mins}m {secs}s."
            )

    def _go_back(self):
        self._reset_state()
        self.auth.show_page("login")

    def clear(self):
        """Reset to defaults — called by auth_window on every page switch."""
        self._reset_state()

    def _reset_state(self):
        self.verify_email_input.clear()
        self.verify_dob_input.setDate(QDate(2000, 1, 1))
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
        self.stack.setCurrentIndex(0)
        self._verified_user_id = None

    # Helpers
    def _logo_row(self):
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
        return logo_row
    
    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl
    
    def _input(self, placeholder, password=False):
        inp = QLineEdit()
        inp.setObjectName("authInput")
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(48)
        if password:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        return inp
    
    def refresh(self):
        pass
