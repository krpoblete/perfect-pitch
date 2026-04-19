from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDateEdit 
)
from PyQt6.QtCore import Qt, QDate
from src.utils.icons import get_icon
from src.utils.toast import toast_error, toast_success
from src.widgets.password_input import PasswordInput

class SignupPage(QWidget):
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
        title = QLabel("Create an account")
        title.setObjectName("loginTitle")
        layout.addWidget(title)

        subtitle = QLabel("Fill in the details below to get started")
        subtitle.setObjectName("loginSubtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(28)

        # First Name | Last Name
        name_row = QHBoxLayout()
        name_row.setSpacing(16)
        fn_col = QVBoxLayout()
        fn_col.setSpacing(7)
        fn_col.addWidget(self._label("First Name"))
        self.first_name_input = self._input("John")
        fn_col.addWidget(self.first_name_input)
        ln_col = QVBoxLayout()
        ln_col.setSpacing(7)
        ln_col.addWidget(self._label("Last Name"))
        self.last_name_input = self._input("Doe")
        ln_col.addWidget(self.last_name_input)
        name_row.addLayout(fn_col)
        name_row.addLayout(ln_col)
        layout.addLayout(name_row)
        layout.addSpacing(16)

        # Date of Birth | Throwing Hand
        dob_hand_row = QHBoxLayout()
        dob_hand_row.setSpacing(16)

        dob_col = QVBoxLayout()
        dob_col.setSpacing(7)
        dob_col.addWidget(self._label("Date of Birth"))
        self.dob_input = QDateEdit()
        self.dob_input.setObjectName("authInput")
        self.dob_input.setFixedHeight(48)
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("MMMM/dd/yyyy")
        self.dob_input.setDate(QDate(2000, 1, 1))
        self.dob_input.setMaximumDate(QDate.currentDate())
        dob_col.addWidget(self.dob_input)

        hand_col = QVBoxLayout()
        hand_col.setSpacing(7) 
        hand_col.addWidget(self._label("Throwing Hand"))
        hand_btn_row = QHBoxLayout()
        hand_btn_row.setSpacing(10)
        self.rhp_btn = QPushButton("RHP")
        self.rhp_btn.setObjectName("handBtnActive")
        self.rhp_btn.setFixedHeight(42)
        self.rhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rhp_btn.setCheckable(True)
        self.rhp_btn.setChecked(True)
        self.rhp_btn.clicked.connect(lambda: self._select_hand("RHP"))
        self.lhp_btn = QPushButton("LHP")
        self.lhp_btn.setObjectName("handBtn")
        self.lhp_btn.setFixedHeight(42)
        self.lhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lhp_btn.setCheckable(True)
        self.lhp_btn.clicked.connect(lambda: self._select_hand("LHP"))
        hand_btn_row.addWidget(self.rhp_btn)
        hand_btn_row.addWidget(self.lhp_btn)
        hand_col.addLayout(hand_btn_row)

        dob_hand_row.addLayout(dob_col)
        dob_hand_row.addLayout(hand_col)
        layout.addLayout(dob_hand_row)
        layout.addSpacing(16)

        # Email
        layout.addWidget(self._label("Email"))
        layout.addSpacing(7)
        self.email_input = self._input("sample@gmail.com")
        layout.addWidget(self.email_input)
        layout.addSpacing(16) 

        # Password | Confirm Password
        pw_row = QHBoxLayout()
        pw_row.setSpacing(16)
        pw_col = QVBoxLayout()
        pw_col.setSpacing(7)
        pw_col.addWidget(self._label("Password"))
        self.pw_input = PasswordInput("Minimum 8 characters")
        pw_col.addWidget(self.pw_input)
        cpw_col = QVBoxLayout()
        cpw_col.setSpacing(7)
        cpw_col.addWidget(self._label("Confirm Password"))
        self.confirm_pw_input = PasswordInput("Re-enter your password")
        cpw_col.addWidget(self.confirm_pw_input)
        pw_row.addLayout(pw_col)
        pw_row.addLayout(cpw_col)
        layout.addLayout(pw_row)
        layout.addSpacing(28)

        # Create Account button
        btn = QPushButton("Create Account")
        btn.setObjectName("loginBtn")
        btn.setFixedHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._handle_signup)
        layout.addWidget(btn)
        layout.addSpacing(16)

        # Back to login
        back_row = QHBoxLayout()
        back_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back_lbl = QLabel("Already have an account?")
        back_lbl.setObjectName("loginSubtitle")
        back_btn = QPushButton("Log in")
        back_btn.setObjectName("linkBtn")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(lambda: self.auth.show_page("login"))
        back_row.addWidget(back_lbl)
        back_row.addWidget(back_btn)
        layout.addLayout(back_row)
        
        layout.addStretch()

        # Enter key navigation
        self.first_name_input.returnPressed.connect(self.last_name_input.setFocus)
        self.last_name_input.returnPressed.connect(self.email_input.setFocus)
        self.email_input.returnPressed.connect(self.pw_input.line_edit.setFocus)
        self.pw_input.line_edit.returnPressed.connect(self.confirm_pw_input.line_edit.setFocus)
        self.confirm_pw_input.line_edit.returnPressed.connect(self._handle_signup)

    def _select_hand(self, hand: str):
        self.rhp_btn.setChecked(hand == "RHP")
        self.lhp_btn.setChecked(hand == "LHP")
        self.rhp_btn.setObjectName("handBtnActive" if hand == "RHP" else "handBtn")
        self.lhp_btn.setObjectName("handBtnActive" if hand == "LHP" else "handBtn")
        self.rhp_btn.style().unpolish(self.rhp_btn)
        self.rhp_btn.style().polish(self.rhp_btn)
        self.lhp_btn.style().unpolish(self.lhp_btn)
        self.lhp_btn.style().polish(self.lhp_btn)

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
        self.first_name_input.clear()
        self.last_name_input.clear()
        self.email_input.clear()
        self.pw_input.clear()
        self.confirm_pw_input.clear()
        self.dob_input.setDate(QDate(2000, 1, 1))
        self._select_hand("RHP")

    ALLOWED_DOMAINS = {"cvsu.edu.ph", "gmail.com", "yahoo.com", "outlook.com"}
    
    def _is_valid_email(self, email):
        import re
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", email):
            return False, "Please enter a valid email address."
        domain = email.split("@")[-1].lower()
        if domain not in self.ALLOWED_DOMAINS:
            return False, f"Only @cvsu.edu.ph, @gmail.com, @yahoo.com, and @outlook.com emails are allowed."
        return True, ""
    
    def _is_strong_password(self, password):
        import re
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter."
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter."
        if not re.search(r"\d", password):
            return False, "Password must contain at least one number."
        return True, ""

    def _handle_signup(self):
        from src.db import create_user

        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        dob = self.dob_input.date().toString("yyyy-MM-dd")
        email = self.email_input.text().strip()
        password = self.pw_input.text()
        confirm_pw = self.confirm_pw_input.text()
        throwing_hand = "RHP" if self.rhp_btn.isChecked() else "LHP"

        if not all([first_name, last_name, email, password, confirm_pw]):
            toast_error(self, "Please fill in all fields.")
            return
        valid_email, email_msg = self._is_valid_email(email)
        if not valid_email:
            toast_error(self, email_msg)
            return
        valid_pw, pw_msg = self._is_strong_password(password)
        if not valid_pw:
            toast_error(self, pw_msg)
            return 
        if password != confirm_pw:
            toast_error(self, "Passwords do not match. Please try again.")
            return
        age = self.dob_input.date().daysTo(QDate.currentDate()) // 365
        if age < 7:
            toast_error(self, "You must be at least 7 years old to register.")
            return
        
        ok, msg = create_user(first_name, last_name, dob, email, password, throwing_hand)
        if ok:
            if msg == "restored":
                toast_success(self, f"Welcome back, {first_name}! Your account has been restored.")
            else:
                toast_success(self, f"Welcome, {first_name}! Your account has been created.")
            self.clear()
            self.auth.show_page("login")
        else:
            toast_error(self.auth, msg)
