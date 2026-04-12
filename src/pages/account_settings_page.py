from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.utils.toast import toast_error, toast_success, toast_info
from src.widgets.password_input import PasswordInput

# USA Baseball pitch count limits by age bracket
PITCH_LIMITS = [
    (7, 8, 50),
    (9, 10, 75),
    (11, 12, 85),
    (13, 14, 95),
    (15, 16, 95),
    (17, 18, 105),
    (19, 22, 120),
]

def get_pitch_limit(dob_str: str) -> int | None:
    """Return the recommended daily pitch limit based on date of birth.""" 
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        for min_age, max_age, limit in PITCH_LIMITS:
            if min_age <= age <= max_age:
                return limit
        return None
    except Exception:
        return None

class AccountSettingsPage(QWidget):
    # Emitted after a successful save so MainWindow can refresh the sidebar
    profile_updated = pyqtSignal()

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self._original_first = ""
        self._original_last = ""
        self._original_threshold = 0
        self._dob = ""
        self.setObjectName("contentPage")
        self.build_ui()

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("settingsContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(48, 40, 48, 48)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Page Title
        title = QLabel("Account Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(6)

        subtitle = QLabel("Manage your profile and security preferences")
        subtitle.setObjectName("settingsSubtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(36)

        # Profile section
        layout.addWidget(self._section_label("Profile"))
        layout.addSpacing(16)

        profile_card = self._card()
        card_layout = QVBoxLayout(profile_card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(0)

        # Avatar + name header
        header_row = QHBoxLayout()
        header_row.setSpacing(20)

        self.avatar_label = QLabel()
        self.avatar_label.setObjectName("settingsAvatar")
        self.avatar_label.setFixedSize(56, 56)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        self.header_name = QLabel()
        self.header_name.setObjectName("settingsHeaderName")
        self.header_email = QLabel()
        self.header_email.setObjectName("settingsHeaderEmail")
        name_col.addWidget(self.header_name)
        name_col.addWidget(self.header_email)

        header_row.addWidget(self.avatar_label)
        header_row.addLayout(name_col)
        header_row.addStretch()
        card_layout.addLayout(header_row)
        card_layout.addSpacing(24)
        card_layout.addWidget(self._divider())
        card_layout.addSpacing(24)

        # Editable fields grid
        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.first_name_input = self._field_input()
        self.last_name_input = self._field_input()
        self.first_name_input.textChanged.connect(self._on_profile_changed)
        self.last_name_input.textChanged.connect(self._on_profile_changed)

        grid.addWidget(self._field_label("First Name"), 0, 0)
        grid.addWidget(self._field_label("Last Name"), 0, 1)
        grid.addWidget(self.first_name_input, 1, 0)
        grid.addWidget(self.last_name_input, 1, 1)
        card_layout.addLayout(grid)
        card_layout.addSpacing(16)

        # Email — read only
        card_layout.addWidget(self._field_label("Email"))
        card_layout.addSpacing(6)
        self.email_display = self._field_input(read_only=True)
        card_layout.addWidget(self.email_display)
        card_layout.addSpacing(16)

        # DOB — read only
        card_layout.addWidget(self._field_label("Date of Birth"))
        card_layout.addSpacing(6)
        self.dob_display = self._field_input(read_only=True)
        card_layout.addWidget(self.dob_display)
        card_layout.addSpacing(24)

        # Pitch threshold display
        card_layout.addWidget(self._divider())
        card_layout.addSpacing(20)

        threshold_row = QHBoxLayout()
        threshold_col = QVBoxLayout()
        threshold_col.setSpacing(4)
        threshold_lbl = QLabel("Daily Pitch Threshold")
        threshold_lbl.setObjectName("settingsFieldLabel")
        threshold_sub = QLabel("Auto-calculated from your age (USA Baseball guidelines). You may adjust it.")
        threshold_sub.setObjectName("settingsSubtitle")
        threshold_col.addWidget(threshold_lbl)
        threshold_col.addWidget(threshold_sub)

        self.threshold_input = QSpinBox()
        self.threshold_input.setObjectName("thresholdSpinBox")
        self.threshold_input.setFixedSize(120, 44)
        self.threshold_input.setRange(1, 999)
        self.threshold_input.setSuffix(" pitches")
        self.threshold_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_input.valueChanged.connect(self._on_profile_changed)

        threshold_row.addLayout(threshold_col)
        threshold_row.addStretch()
        threshold_row.addWidget(self.threshold_input)
        card_layout.addLayout(threshold_row)
        card_layout.addSpacing(24)

        # Save button — disabled until changes detected
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setObjectName("settingsSaveBtnDisabled")
        self.save_btn.setFixedHeight(44)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._handle_save_profile)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        card_layout.addLayout(btn_row)

        layout.addWidget(profile_card)
        layout.addSpacing(28)

        # Security section
        layout.addWidget(self._section_label("Security"))
        layout.addSpacing(16)

        security_card = self._card()
        sec_layout = QVBoxLayout(security_card)
        sec_layout.setContentsMargins(28, 24, 28, 28)
        sec_layout.setSpacing(0)

        pw_grid = QGridLayout()
        pw_grid.setSpacing(16)
        pw_grid.setColumnStretch(0, 1)
        pw_grid.setColumnStretch(1, 1)

        self.current_pw_input = PasswordInput("Enter current password")
        self.new_pw_input = PasswordInput("Minimum 8 characters")
        self.confirm_pw_input = PasswordInput("Re-enter new password")

        pw_grid.addWidget(self._field_label("Current Password"), 0, 0)
        pw_grid.addWidget(self.current_pw_input, 1, 0)
        pw_grid.addWidget(self._field_label("New Password"), 0, 1)
        pw_grid.addWidget(self.new_pw_input, 1, 1)

        sec_layout.addLayout(pw_grid)
        sec_layout.addSpacing(16)
        sec_layout.addWidget(self._field_label("Confirm New Password"))
        sec_layout.addSpacing(6)
        sec_layout.addWidget(self.confirm_pw_input)
        sec_layout.addSpacing(24)

        change_pw_btn = QPushButton('Change Password')
        change_pw_btn.setObjectName("settingsSaveBtn")
        change_pw_btn.setFixedHeight(44)
        change_pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_pw_btn.clicked.connect(self._handle_change_password)

        pw_btn_row = QHBoxLayout()
        pw_btn_row.addStretch()
        pw_btn_row.addWidget(change_pw_btn)
        sec_layout.addLayout(pw_btn_row)

        layout.addWidget(security_card)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # Helpers
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("settingsSectionLabel")
        return lbl

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("settingsFieldLabel")
        return lbl
    
    def _field_input(self, read_only: bool = False) -> QLineEdit:
        inp = QLineEdit()
        inp.setObjectName("settingsInputReadOnly" if read_only else "settingsInput")
        inp.setFixedHeight(44)
        inp.setReadOnly(read_only)
        return inp
    
    def _card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("settingsCard")
        return card

    def _divider(self) -> QWidget:
        line = QFrame()
        line.setObjectName("settingsDivider")
        line.setFixedHeight(1)    
        return line
    
    def _set_save_enabled(self, enabled: bool):
        self.save_btn.setEnabled(enabled)
        self.save_btn.setObjectName("settingsSaveBtn" if enabled else "settingsSaveBtnDisabled")
        self.save_btn.style().unpolish(self.save_btn)
        self.save_btn.style().polish(self.save_btn)

    # Change detection
    def _on_profile_changed(self):
        changed = (
            self.first_name_input.text().strip() != self._original_first or
            self.last_name_input.text().strip() != self._original_last or
            self.threshold_input.value() != self._original_threshold
        )
        self._set_save_enabled(changed)
    
    # Data
    def refresh(self):
        from src.db import get_user_by_id
        user = get_user_by_id(self.user_id)
        if not user:
            return
        
        first = user["first_name"].strip()
        last = user["last_name"].strip()

        self._original_first = first
        self._original_last = last
        self._dob = user["date_of_birth"]

        # Avatar 
        initials = f"{first[0]}{last[0]}".upper() if first and last else "?"
        self.avatar_label.setText(initials)

        # Header
        self.header_name.setText(f"{first} {last}")
        self.header_email.setText(user["email"])

        # Fields
        self.first_name_input.setText(first)
        self.last_name_input.setText(last)
        self.email_display.setText(user["email"])

        try:
            from datetime import date as _date
            parsed = _date.fromisoformat(self._dob)
            self.dob_display.setText(parsed.strftime("%B %d, %Y"))
        except Exception:
            self.dob_display.setText(self._dob)

        # Threshold — use saved value or auto-calculate from DOB
        saved = user["pitch_threshold"]
        recommended = get_pitch_limit(self._dob)
        threshold = saved if saved else (recommended if recommended else 50)
        self._original_threshold = threshold

        self.threshold_input.blockSignals(True)
        self.threshold_input.setValue(threshold)
        self.threshold_input.blockSignals(False)

        self._set_save_enabled(False)

        # Clear password fields
        self.current_pw_input.clear()
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()

    # Handlers
    def _handle_save_profile(self):
        from src.db import update_user_profile, update_pitch_threshold

        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        threshold = self.threshold_input.value()

        if not first_name or not last_name:
            toast_error(self, "First and last name cannot be empty.")
            return
        
        update_user_profile(self.user_id, first_name, last_name)
        update_pitch_threshold(self.user_id, threshold)

        self._original_first = first_name
        self._original_last = last_name
        self._original_threshold = threshold

        # Update avatar and header in this page immediately
        initials = f"{first_name[0]}{last_name[0]}".upper()
        self.avatar_label.setText(initials)
        self.header_name.setText(f"{first_name} {last_name}")

        self._set_save_enabled(False)

        # Signal MainWindow to reload sidebar user info
        self.profile_updated.emit()

        toast_success(self, "Profile updated sucessfully.")

    def _handle_change_password(self):
        from src.db import get_user_by_id, verify_password, update_user_password

        current = self.current_pw_input.text()
        new_pw = self.new_pw_input.text()
        confirm = self.confirm_pw_input.text()

        if not current or not new_pw or not confirm:
            toast_error(self, "Please fill in all password fields.")
            return
        
        user = get_user_by_id(self.user_id)
        if not verify_password(current, user["password"]):
            toast_error(self, "Current password is incorrect.")
            return
        if len(new_pw) < 8:
            toast_error(self, "New password must be at least 8 characters long.")
            return
        if new_pw != confirm:
            toast_error(self, "Passwords do not match. Pleast try again.")
            return
        if new_pw == current:
            toast_info(self, "New password must be different from your current password.")
            return
        
        update_user_password(self.user_id, new_pw)
        self.current_pw_input.clear()
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
        toast_success(self, "Password changed successfully.")
