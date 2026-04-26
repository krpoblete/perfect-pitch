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
    (13, 16, 95),
    (17, 18, 105),
    (19, 22, 120),
]

def get_pitch_limit(dob_str: str) -> int | None:
    """Return the recommended daily pitch limit based on date of birth.

    Age < 13 → 95  (signup floor — youngest allowed)
    Age > 22 → 120 (highest bracket ceiling)
    """
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        for min_age, max_age, limit in PITCH_LIMITS:
            if min_age <= age <= max_age:
                return limit
        if age > 22:
            return 120
        return 95
    except Exception:
        return 95

def get_pitch_max(dob_str: str) -> int:
    """Return the spinbox ceiling for the user's age.
 
    Age < 13 → 95  (signup floor — youngest allowed)
    Age > 22 → 120 (highest bracket ceiling)
    """ 
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        for min_age, max_age, limit in PITCH_LIMITS:
            if min_age <= age <= max_age:
                return limit
        if age > 22:
            return 120
        return 95
    except Exception:
        return 95 

class AccountSettingsPage(QWidget):
    # Emitted after a successful save so MainWindow can refresh the sidebar
    profile_updated = pyqtSignal()

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self._original_first = ""
        self._original_last = ""
        self._original_threshold = 0
        self._original_hand = "RHP"
        self._role = "Pitcher"
        self._dob = ""
        self._last_date = self._manila_today()
        self.setObjectName("contentPage")
        self.build_ui()

        # Check every 60s if Manila date has changed → replenish spinbox at midnight
        from PyQt6.QtCore import QTimer as _QTimer
        self._midnight_timer = _QTimer(self)
        self._midnight_timer.setInterval(60_000)
        self._midnight_timer.timeout.connect(self._check_midnight_reset)
        self._midnight_timer.start()
    
    @staticmethod
    def _manila_today() -> str:
        """Return today's date string in Manila time (UTC+8)."""
        from datetime import datetime, timezone, timedelta
        return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

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

        # First Name | Last Name 
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

        # Email | DOB | Throwing Hand
        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        email_col = QVBoxLayout()
        email_col.setSpacing(6)
        email_col.addWidget(self._field_label("Email"))
        self.email_display = self._field_input(read_only=True)
        email_col.addWidget(self.email_display)

        dob_col = QVBoxLayout()
        dob_col.setSpacing(6)
        dob_col.addWidget(self._field_label("Date of Birth"))
        self.dob_display = self._field_input(read_only=True)
        dob_col.addWidget(self.dob_display)

        hand_col = QVBoxLayout()
        hand_col.setSpacing(6)
        hand_header = QHBoxLayout()
        hand_header.setSpacing(8)
        hand_header.addWidget(self._field_label("Throwing Hand"))
        hand_header.addWidget(self._pitchers_only_badge())
        hand_header.addStretch()
        hand_col.addLayout(hand_header)
        hand_btn_row = QHBoxLayout()
        hand_btn_row.setSpacing(10)
        self.rhp_btn = QPushButton("RHP")
        self.rhp_btn.setObjectName("handBtnActive")
        self.rhp_btn.setFixedHeight(44)
        self.rhp_btn.setCheckable(True)
        self.rhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rhp_btn.clicked.connect(lambda: self._select_hand("RHP"))
        self.lhp_btn = QPushButton("LHP")
        self.lhp_btn.setObjectName("handBtn")
        self.lhp_btn.setFixedHeight(44)
        self.lhp_btn.setCheckable(True)
        self.lhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lhp_btn.clicked.connect(lambda: self._select_hand("LHP"))
        hand_btn_row.addWidget(self.rhp_btn)
        hand_btn_row.addWidget(self.lhp_btn)
        hand_col.addLayout(hand_btn_row)
        
        info_row.addLayout(email_col, stretch=3)
        info_row.addLayout(dob_col, stretch=2)
        info_row.addLayout(hand_col, stretch=2)
        card_layout.addLayout(info_row)
        card_layout.addSpacing(24)

        # Pitch threshold — editable spinbox 
        card_layout.addWidget(self._divider())
        card_layout.addSpacing(20)

        threshold_row = QHBoxLayout()
        threshold_col = QVBoxLayout()
        threshold_col.setSpacing(4)
        threshold_header = QHBoxLayout()
        threshold_header.setSpacing(8)
        threshold_lbl = QLabel("Daily Pitch Threshold")
        threshold_lbl.setObjectName("settingsFieldLabel")
        threshold_header.addWidget(threshold_lbl)
        threshold_header.addWidget(self._pitchers_only_badge())
        threshold_header.addStretch()
        threshold_col.addLayout(threshold_header)
        threshold_sub = QLabel(
            "Your daily pitch limit. The maximum is your recommended cap "
            "(USA Baseball guidelines). Pitches used today are deducted from "
            "your available limit and it fully replenishes at midnight."
        )
        threshold_sub.setObjectName("settingsSubtitle")
        threshold_col.addWidget(threshold_sub)

        self.threshold_input = QSpinBox()
        self.threshold_input.setObjectName("thresholdSpinBox")
        self.threshold_input.setFixedSize(120, 44)
        self.threshold_input.setSuffix(" pitches")
        self.threshold_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_input.valueChanged.connect(self._on_profile_changed)

        threshold_row.addLayout(threshold_col)
        threshold_row.addStretch()
        threshold_row.addWidget(self.threshold_input)
        card_layout.addLayout(threshold_row)
        card_layout.addSpacing(12)

        # Recommended cap + remaining pitches indicators
        indicators_row = QHBoxLayout()
        indicators_row.setSpacing(10)

        self.rec_cap_lbl = QLabel()
        self.rec_cap_lbl.setObjectName("thresholdIndicator")

        self.remaining_lbl = QLabel()
        self.remaining_lbl.setObjectName("thresholdIndicatorRemaining")

        indicators_row.addWidget(self.rec_cap_lbl)
        indicators_row.addStretch()
        indicators_row.addWidget(self.remaining_lbl)
        card_layout.addLayout(indicators_row)
        card_layout.addSpacing(16)

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

        # Enter key navigation
        self.first_name_input.returnPressed.connect(self.last_name_input.setFocus)
        self.last_name_input.returnPressed.connect(self._try_save_from_enter)

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

        pw_grid.addWidget(self._field_label("Current Password"), 0, 0)
        pw_grid.addWidget(self.current_pw_input, 1, 0)
        pw_grid.addWidget(self._field_label("New Password"), 0, 1)
        pw_grid.addWidget(self.new_pw_input, 1, 1)

        sec_layout.addLayout(pw_grid)
        sec_layout.addSpacing(16)
        confirm_row = QHBoxLayout()
        confirm_row.setSpacing(14)

        confirm_col = QVBoxLayout()
        confirm_col.setSpacing(6)
        confirm_col.addWidget(self._field_label("Confirm New Password"))
        self.confirm_pw_input = PasswordInput("Re-enter new password")
        confirm_col.addWidget(self.confirm_pw_input)

        change_pw_btn = QPushButton('Change Password')
        change_pw_btn.setObjectName("settingsSaveBtn")
        change_pw_btn.setFixedHeight(44)
        change_pw_btn.setFixedWidth(180)
        change_pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_pw_btn.clicked.connect(self._handle_change_password)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        btn_col.addWidget(QLabel())
        btn_col.addWidget(change_pw_btn)

        confirm_row.addLayout(confirm_col, stretch=1)
        confirm_row.addLayout(btn_col)
        sec_layout.addLayout(confirm_row)

        # Enter key navigation
        self.current_pw_input.line_edit.returnPressed.connect(self.new_pw_input.line_edit.setFocus)
        self.new_pw_input.line_edit.returnPressed.connect(self.confirm_pw_input.line_edit.setFocus)
        self.confirm_pw_input.line_edit.returnPressed.connect(self._handle_change_password)

        layout.addWidget(security_card)
        layout.addSpacing(28)

        # Danger Zone section
        layout.addWidget(self._section_label("Danger Zone"))
        layout.addSpacing(16)

        danger_card = self._card()
        danger_card.setObjectName("settingsDangerCard")
        danger_layout = QHBoxLayout(danger_card)
        danger_layout.setContentsMargins(28, 20, 28, 20)
        danger_layout.setSpacing(16)

        danger_text_col = QVBoxLayout()
        danger_text_col.setSpacing(4)
        danger_title = QLabel("Delete Account")
        danger_title.setObjectName("dangerTitle")
        danger_sub = QLabel(
            "Only available to Coaches."
        )
        danger_sub.setObjectName("settingsSubtitle")
        danger_text_col.addWidget(danger_title)
        danger_text_col.addWidget(danger_sub)

        self.delete_btn = QPushButton("Delete Account")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.setFixedHeight(44)
        self.delete_btn.setFixedWidth(160)
        self.delete_btn.clicked.connect(self._handle_delete_account)

        danger_layout.addLayout(danger_text_col, stretch=1)
        danger_layout.addWidget(self.delete_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(danger_card)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # Helpers
    def _select_hand(self, hand: str):
        self.rhp_btn.setChecked(hand == "RHP")
        self.lhp_btn.setChecked(hand == "LHP")
        self.rhp_btn.setObjectName("handBtnActive" if hand == "RHP" else "handBtn")
        self.lhp_btn.setObjectName("handBtnActive" if hand == "LHP" else "handBtn")
        self.rhp_btn.style().unpolish(self.rhp_btn)
        self.rhp_btn.style().polish(self.rhp_btn)
        self.lhp_btn.style().unpolish(self.lhp_btn)
        self.lhp_btn.style().polish(self.lhp_btn)
        self._on_profile_changed()

    def _pitchers_only_badge(self) -> QLabel:
        """Small inline badge indicating a field is only for Pitchers."""
        badge = QLabel("Pitchers only")
        badge.setObjectName("pitchersOnlyBadge")
        return badge
     
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
        hand = "RHP" if self.rhp_btn.isChecked() else "LHP"
        is_coach = self._role == "Coach"
        changed = (
            self.first_name_input.text().strip() != self._original_first or
            self.last_name_input.text().strip() != self._original_last or
            (not is_coach and self.threshold_input.value() != self._original_threshold) or
            (not is_coach and hand != self._original_hand)
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
        self._role = user["role"]
        hand = user["throwing_hand"] if user["throwing_hand"] else "RHP"
        self._original_hand = hand

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

        # Threshold with daily deduction logic
        from src.db import get_pitches_used_today
        recommended = get_pitch_limit(self._dob)
        cap = get_pitch_max(self._dob)
        user_today = get_pitches_used_today(self.user_id)

        # effective_max = remaining pitches available today 
        effective_max = max(1, cap - user_today)

        # Exhausted = user has used at or beyond their threshold today 
        saved = user["pitch_threshold"] or recommended
        is_exhausted = user_today >= saved

        # Clamp saved threshold to what's still available (handles mid-day changes) 
        threshold = min(saved, effective_max)
        self._original_threshold = threshold

        # Spinbox range: always 1 → effective_max so user can raise/lower freely
        self.threshold_input.blockSignals(True)
        self.threshold_input.setRange(1, effective_max)
        self.threshold_input.setValue(threshold)
        self.threshold_input.blockSignals(False)

        # Lock spinbox only when truly exhausted
        self.threshold_input.setEnabled(not is_exhausted and self._role != "Coach")
        if is_exhausted:
            self.threshold_input.setToolTip(
                "You've used all your pitches today. Replenishes at midnight."
            )
            self.threshold_input.setCursor(Qt.CursorShape.ForbiddenCursor)
        else:
            self.threshold_input.setToolTip("")
            self.threshold_input.setCursor(Qt.CursorShape.IBeamCursor)

        # Recommended cap indicator
        self.rec_cap_lbl.setText(f"Recommended: {cap} pitches/day")

        # Remaining pitches today indicator
        remaining = max(0, effective_max)
        self.remaining_lbl.setText(f"Remaining today: {remaining}")
        self.remaining_lbl.setStyleSheet(
            "color: #4ecb71; background: transparent;"
            if remaining > 0 else
            "color: #e05555; background: transparent;"
        )
        
        # Throwing hand — block signals to avoid triggering change detection
        self.rhp_btn.blockSignals(True)
        self.lhp_btn.blockSignals(True)
        self._select_hand(hand)
        self.rhp_btn.blockSignals(False)
        self.lhp_btn.blockSignals(False)

        # Coaches don't pitch — grey out hand buttons and threshold entirely
        is_coach = self._role == "Coach"
        self.rhp_btn.setEnabled(not is_coach)
        self.lhp_btn.setEnabled(not is_coach)
        
        if is_coach:
            # Grey out hand buttons — use disabled object names so QSS dims them
            self.rhp_btn.setObjectName("handBtnDisabled")
            self.lhp_btn.setObjectName("handBtnDisabled")
            self.rhp_btn.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.lhp_btn.setCursor(Qt.CursorShape.ForbiddenCursor)

            # Threshold — show 0, greyed out, fully locked
            self.threshold_input.blockSignals(True)
            self.threshold_input.setRange(0, 0)
            self.threshold_input.setValue(0)
            self.threshold_input.blockSignals(False)
            self.threshold_input.setEnabled(False)
            self.threshold_input.setObjectName("thresholdSpinBoxDisabled")
            self.threshold_input.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.threshold_input.setToolTip("Coaches do not have a pitch threshold.")

            # Grey out indicators for Coach
            self.rec_cap_lbl.setText("Recommended: N/A")
            self.rec_cap_lbl.setStyleSheet("color: #3a3a3a; background: transparent;")
            self.remaining_lbl.setText("Remaining today: 0")
            self.remaining_lbl.setStyleSheet("color: #3a3a3a; background: transparent;")
        else:
            # Restore hand buttons to correct active/inactive state
            active_hand = "RHP" if self.rhp_btn.isChecked() else "LHP"
            self.rhp_btn.setObjectName("handBtnActive" if active_hand == "RHP" else "handBtn") 
            self.lhp_btn.setObjectName("handBtnActive" if active_hand == "LHP" else "handBtn")
            self.rhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.lhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.threshold_input.setEnabled(True)
            self.threshold_input.setObjectName("thresholdSpinBox")
            self.threshold_input.setCursor(Qt.CursorShape.IBeamCursor)

        # Force QSS re-evaluation on hand buttons and spinbox
        for w in (self.rhp_btn, self.lhp_btn, self.threshold_input):
            w.style().unpolish(w)
            w.style().polish(w)

        self._set_save_enabled(False)

        # Delete button — only Coaches can delete their own account
        is_coach = self._role == "Coach"
        self.delete_btn.setEnabled(is_coach)
        self.delete_btn.setObjectName("dangerBtn" if is_coach else "dangerBtnDisabled")
        self.delete_btn.setCursor(
            Qt.CursorShape.PointingHandCursor if is_coach
            else Qt.CursorShape.ForbiddenCursor
        )
        self.delete_btn.setToolTip(
            "Delete your account" if is_coach
            else "Only Coaches can delete their account"
        )
        self.delete_btn.style().unpolish(self.delete_btn)
        self.delete_btn.style().polish(self.delete_btn)

        # Clear password fields
        self.current_pw_input.clear()
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()

    # Handlers
    def _try_save_from_enter(self):
        """Called when Enter is pressed on Last Name — only saves if there are changes."""
        is_coach = self._role == "Coach"
        hand = "RHP" if self.rhp_btn.isChecked() else "LHP"
        has_changes = (
            self.first_name_input.text().strip() != self._original_first or
            self.last_name_input.text().strip() != self._original_last or
            (not is_coach and self.threshold_input.value() != self._original_threshold) or
            (not is_coach and hand != self._original_hand)
        )
        if not has_changes:
            toast_info(self, "No changes to save.")
            return
        self._handle_save_profile()

    def _check_midnight_reset(self):
        """Called every 60s — detects Manila midnight and replenishes the spinbox."""
        today = self._manila_today()
        if today != self._last_date:
            self._last_date = today
            # New day in Manila — re-run refresh so spinbox resets to full cap
            self.refresh()

    def _handle_save_profile(self):
        from src.db import update_user_profile, update_pitch_threshold, update_throwing_hand
        from src.utils.validators import validate_name

        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        from src.db import get_pitches_used_today
        used_today = get_pitches_used_today(self.user_id)
        cap = get_pitch_max(self._dob)
        effective_max = max(1, cap - used_today)
        threshold = min(self.threshold_input.value(), effective_max)
        hand = "RHP" if self.rhp_btn.isChecked() else "LHP" 

        ok, msg = validate_name(first_name, "First Name")
        if not ok:
            toast_error(self, msg)
            return
        ok, msg = validate_name(last_name, "Last Name")
        if not ok:
            toast_error(self, msg)
            return

        update_user_profile(self.user_id, first_name, last_name)
        update_pitch_threshold(self.user_id, threshold)
        update_throwing_hand(self.user_id, hand)

        self._original_first = first_name
        self._original_last = last_name
        self._original_threshold = threshold
        self._original_hand = hand

        # Update avatar and header in this page immediately
        initials = f"{first_name[0]}{last_name[0]}".upper()
        self.avatar_label.setText(initials)
        self.header_name.setText(f"{first_name} {last_name}")

        self._set_save_enabled(False)

        # Signal MainWindow to reload sidebar user info
        self.profile_updated.emit()

        toast_success(self, "Profile updated successfully.")

    def _handle_delete_account(self):
        """Coach-only: soft-delete account and return to login."""
        if self._role != "Coach":
            return
        
        from src.widgets.confirm_dialog import ConfirmDialog
        dlg = ConfirmDialog(
            self.window(),
            title="Delete Account",
            message=(
                "Are you sure you want to delete your account?"
            ),
        )
        dlg.exec()
        if not dlg.result_yes():
            return
        
        from src.db import deactivate_user
        from src.windows.auth_window import AuthWindow
        from src.utils.animations import fade_out

        deactivate_user(self.user_id)

        # Return to login
        self._auth_window = AuthWindow()
        self._auth_window.show()

        def _close():
            w = self.window()
            w._logging_out = True
            w.close()

        fade_out(self.window(), on_finish=_close)

    def _handle_change_password(self):
        from src.db import get_user_by_id, verify_password, update_user_password
        import re

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
        if not re.search(r"[a-z]", new_pw):
            toast_error(self, "Password must contain at least one lowercase letter.")
            return
        if not re.search(r"[A-Z]", new_pw):
            toast_error(self, "Password must contain at least one uppercase letter.")
            return
        if not re.search(r"\d", new_pw):
            toast_error(self, "Password must contain at least one number.")
            return
        if new_pw != confirm:
            toast_error(self, "Passwords do not match. Please try again.")
            return
        if new_pw == current:
            toast_info(self, "New password must be different from your current password.")
            return
        
        update_user_password(self.user_id, new_pw)
        self.current_pw_input.clear()
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
        toast_success(self, "Password changed successfully.")
