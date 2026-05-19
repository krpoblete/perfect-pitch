from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDateEdit, QStackedWidget
)
from PyQt6.QtCore import Qt, QDate

from src.utils.toast import toast_error, toast_success, toast_info
from src.widgets.password_input import PasswordInput
from src.pages.auth.auth_base import AuthBasePage

MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 15 

class ForgotPasswordPage(AuthBasePage):
    def __init__(self, auth_window):
        super().__init__()
        self.auth = auth_window
        self.setObjectName("loginLeft")
        
        self._verified_user_id = None
        
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

    # Page 1: Verify Email + DOB
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

        # Lockout Label
        self.lockout_label = QLabel("")
        self.lockout_label.setObjectName("lockoutLabel")
        self.lockout_label.setWordWrap(True)
        self.lockout_label.hide()
        layout.addWidget(self.lockout_label)

        layout.addSpacing(14)

        # Continue Button
        self.verify_btn = QPushButton("Continue")
        self.verify_btn.setObjectName("loginBtn")
        self.verify_btn.setFixedHeight(50)
        self.verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_btn.clicked.connect(self._handle_verify)
        layout.addWidget(self.verify_btn)

        layout.addSpacing(16)

        # Back to Login
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

        # Enter Key Navigation
        self.verify_email_input.returnPressed.connect(self._handle_verify)
        return page
    
    # Page 2: Set New Password
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

        # Reset Button
        reset_btn = QPushButton("Reset Password")
        reset_btn.setObjectName("loginBtn")
        reset_btn.setFixedHeight(50)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._handle_reset)
        layout.addWidget(reset_btn)

        layout.addSpacing(16)

        # Back to Verify
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

        # Enter Key Navigation
        self.new_pw_input.line_edit.returnPressed.connect(
            self.confirm_pw_input.line_edit.setFocus
        )
        self.confirm_pw_input.line_edit.returnPressed.connect(self._handle_reset)
        return page
    
    # Handlers
    def _handle_verify(self):
        # Check Lockout
        if self.auth._fp_locked_until and datetime.now() < self.auth._fp_locked_until:
            return
        
        from src.db import get_user_by_email
        from src.utils.validators import validate_email

        email = self.verify_email_input.text().strip()
        dob = self.verify_dob_input.date().toString("yyyy-MM-dd")

        if not email:
            toast_error(self, "Please enter your email address.")
            return

        # Validate Domain - don't count as an attempt
        valid, msg = validate_email(email)
        if not valid:
            toast_error(self, msg)
            return

        user = get_user_by_email(email)
        if user is None or user["date_of_birth"] != dob:
            self.auth._fp_attempts += 1
            remaining = MAX_ATTEMPTS - self.auth._fp_attempts
            if self.auth._fp_attempts >= MAX_ATTEMPTS:
                self.auth._fp_locked_until = datetime.now() + timedelta(
                    minutes=LOCKOUT_MINUTES
                )
                self.verify_btn.setEnabled(False)
                self.lockout_label.show()
                self.auth._fp_lockout_timer.start(1000)
                self._update_lockout()
            else:
                toast_error(
                    self,
                    f"Email or date of birth is incorrect. "
                    f"{remaining} attempt{'s' if remaining != 1 else ''} remaining.",
                )
            return
        
        # Match - store user id and proceed to reset page
        self._verified_user_id = user["id"]
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
        self.stack.setCurrentIndex(1)

    def _handle_reset(self):
        from src.db import get_user_by_id, verify_password, update_user_password
        from src.utils.validators import validate_password

        password = self.new_pw_input.text()
        confirm = self.confirm_pw_input.text()

        if not password or not confirm:
            toast_error(self, "Please fill in all fields.")
            return

        valid_pw, pw_msg = validate_password(password)
        if not valid_pw:
            toast_error(self, pw_msg)
            return

        if password != confirm:
            toast_error(self, "Passwords do not match. Please try again.")
            return

        # Check New Password is Different from Current
        user = get_user_by_id(self._verified_user_id)
        if user and verify_password(password, user["password"]):
            toast_info(
                self,
                "New password must be different from your current password."
            )
            return 

        update_user_password(self._verified_user_id, password)

        toast_success(self, "Password reset successfully. Please log in.")
        self._reset_state()
        self.auth.show_page("login")

    def _update_lockout(self):
        if not self.auth._fp_locked_until:
            return
        remaining = self.auth._fp_locked_until - datetime.now()
        if remaining.total_seconds() <= 0:
            self.auth._fp_lockout_timer.stop()
            self.auth._fp_locked_until = None
            self.auth._fp_attempts = 0
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
        self.auth.show_page("login")

    def clear(self):
        """Reset form fields only - lockout state is intentionally preserved
        on AuthWindow so the countdown survives navigating away and back."""
        self.verify_email_input.clear()
        self.verify_dob_input.setDate(QDate(2000, 1, 1))
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
        self.stack.setCurrentIndex(0)
        self._verified_user_id = None

    def _reset_state(self):
        """Full reset including lockout - called only after a successful
        password reset, when the lockout is no longer relevant."""
        self.clear()
        self.auth._fp_attempts = 0
        self.auth._fp_locked_until = None
        if self.auth._fp_lockout_timer and self.auth._fp_lockout_timer.isActive():
            self.auth._fp_lockout_timer.stop()
        self.verify_btn.setEnabled(True)
        self.lockout_label.hide()
        self.lockout_label.setText("")        

    def refresh(self):
        pass
