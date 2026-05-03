from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit,
    QFrame, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QTimer

from src.utils.icons import get_icon
from src.utils.toast import toast_success, toast_error

ROWS_PER_PAGE = 10
COLUMNS = ["Full Name", "Email", "Role", "Status", "Date Joined", "Deleted At", "Purge Date", ""]
ROLE_OPTIONS = ["Pitcher", "Coach"]
RETENTION_DAYS = 90 

def _fmt_date(dt_str: str) -> str:
    try:
        return date.fromisoformat(dt_str[:10]).strftime("%b %d, %Y")
    except Exception:
        return dt_str or "—"

def _fmt_purge_datetime(deleted_at_str: str) -> tuple[str, bool]:
    """Return (purge_datetime_string, is_critical).
    is_critical = True when less than 24 hours remain until purge.
    """
    try:
        from datetime import datetime, timezone, timedelta
        utc8 = timezone(timedelta(hours=8))
        deleted = datetime.fromisoformat(deleted_at_str).replace(tzinfo=utc8)
        purge = deleted + timedelta(days=RETENTION_DAYS)
        now = datetime.now(utc8)
        remaining = purge - now
        critical = remaining.total_seconds() < 86400
        purge_str = purge.strftime("%b %d, %Y  %H:%M:%S")
        return purge_str, critical
    except Exception:
        return "—", False

class UsersPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentPage")
        self._all_rows = []
        self._filtered = []
        self._page = 0
        self._build_ui()

        # Refresh every minute to keep status badges current (purge date is static)
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._refresh_days)
        self._timer.start()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 28)
        layout.setSpacing(0)

        # Header
        header_row = QHBoxLayout()

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("Users")
        title.setObjectName("pageTitle")
        self.count_lbl = QLabel()
        self.count_lbl.setObjectName("pitchersCountLabel")
        title_col.addWidget(title)
        title_col.addWidget(self.count_lbl)

        # Search bar — plain input, active border on focus
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBar")
        self.search_input.setPlaceholderText("Search users...")
        self.search_input.setFixedHeight(38)
        self.search_input.setFixedWidth(280)
        self.search_input.textChanged.connect(self._on_search)

        header_row.addLayout(title_col)
        header_row.addStretch()
        header_row.addWidget(self.search_input)
        layout.addLayout(header_row)
        layout.addSpacing(24) 

        # Table
        self.table_container = QWidget()
        self.table_container.setObjectName("tableContainer")
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        table_layout.addWidget(self._make_header_row())

        div = QFrame()
        div.setObjectName("tableDivider")
        div.setFixedHeight(1)
        table_layout.addWidget(div)

        self.rows_widget = QWidget()
        self.rows_widget.setObjectName("tableRows")
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        table_layout.addWidget(self.rows_widget)

        layout.addWidget(self.table_container)
        layout.addSpacing(16)

        # Pagination
        pag_row = QHBoxLayout()
        pag_row.setSpacing(8)

        self.prev_btn = QPushButton("← Prev")
        self.prev_btn.setObjectName("paginationBtn")
        self.prev_btn.setFixedHeight(34)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(self._prev_page)

        self.page_lbl = QLabel()
        self.page_lbl.setObjectName("pageLabel")
        self.page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_lbl.setFixedWidth(100)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setObjectName("paginationBtn")
        self.next_btn.setFixedHeight(34)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self._next_page)

        pag_row.addStretch()
        pag_row.addWidget(self.prev_btn)
        pag_row.addWidget(self.page_lbl)
        pag_row.addWidget(self.next_btn)
        layout.addLayout(pag_row)
        layout.addStretch()

    # Table builders
    def _make_header_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("tableHeaderRow")
        row.setFixedHeight(44)
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(0)
        stretches = [3, 3, 2, 2, 2, 2, 2, 1]
        for col, stretch in zip(COLUMNS, stretches):
            lbl = QLabel(col)
            lbl.setObjectName("tableHeaderCell")
            h.addWidget(lbl, stretch=stretch)
        return row
    
    def _make_data_row(self, user, alternate: bool) -> QWidget:
        is_active = bool(user["is_active"])
        deleted_at = user["deleted_at"]

        row = QWidget()
        row.setObjectName("tableRowAlt" if alternate else "tableRow")
        row.setFixedHeight(52)
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(0)

        stretches = [3, 3, 2, 2, 2, 2, 2, 1]
        full_name = f"{user['first_name']} {user['last_name']}"
        joined = _fmt_date(user["created_at"])

        # Full Name
        name_lbl = QLabel(full_name)
        name_lbl.setObjectName("tableCell")
        h.addWidget(name_lbl, stretch=stretches[0])

        # Email
        email_lbl = QLabel(user["email"])
        email_lbl.setObjectName("tableCell")
        h.addWidget(email_lbl, stretch=stretches[1])

        # Role — inline dropdown for non-admins, plain label for Admin
        current_role = user["role"]
        is_admin = current_role == "Admin"

        if is_admin:
            role_lbl = QLabel("Admin")
            role_lbl.setObjectName("roleAdminLabel")
            role_lbl.setFixedHeight(32)
            role_wrapper = QHBoxLayout()
            role_wrapper.setContentsMargins(0, 0, 16, 0)
            role_wrapper.addWidget(role_lbl)
            role_wrapper.addStretch()
            h.addLayout(role_wrapper)
            h.setStretch(h.count() - 1, stretches[2])
        else:
            role_combo = QComboBox()
            role_combo.setObjectName("roleCombo")
            role_combo.setFixedHeight(32)
            role_combo.addItems(ROLE_OPTIONS)
            if current_role in ROLE_OPTIONS:
                role_combo.setCurrentText(current_role)
            role_combo.setEnabled(is_active)
            role_combo.currentTextChanged.connect(
                lambda role, uid=user["id"], name=full_name, combo=role_combo:
                    self._handle_role_change(uid, name, role, combo)
            )
            role_wrapper = QHBoxLayout()
            role_wrapper.setContentsMargins(0, 0, 16, 0)
            role_wrapper.addWidget(role_combo)
            role_wrapper.addStretch()
            h.addLayout(role_wrapper)
            h.setStretch(h.count() - 1, stretches[2])

        # Status badge
        status_lbl = QLabel("Active" if is_active else "Inactive")
        status_lbl.setObjectName("statusBadgeActive" if is_active else "statusBadgeInactive")
        status_lbl.setFixedHeight(24)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setFixedWidth(70)

        status_wrapper = QHBoxLayout()
        status_wrapper.setContentsMargins(0, 0, 0, 0)
        status_wrapper.addWidget(status_lbl)
        status_wrapper.addStretch()
        h.addLayout(status_wrapper)
        h.setStretch(h.count() - 1, stretches[3])

        # Date Joined
        joined_lbl = QLabel(joined)
        joined_lbl.setObjectName("tableCell")
        h.addWidget(joined_lbl, stretch=stretches[4])

        # Deleted At
        deleted_lbl = QLabel(_fmt_date(deleted_at) if deleted_at else "—")
        deleted_lbl.setObjectName("tableCellMuted" if deleted_at else "tableCell")
        h.addWidget(deleted_lbl, stretch=stretches[5])

        # Purge Date — static datetime when the account will be permanently deleted
        if deleted_at:
            purge_str, critical = _fmt_purge_datetime(deleted_at)
            purge_obj = "daysLeftWarning" if critical else "daysLeftNormal"
        else:
            purge_str = "—"
            purge_obj = "tableCell"

        purge_lbl = QLabel(purge_str)
        purge_lbl.setObjectName(purge_obj)
        h.addWidget(purge_lbl, stretch=stretches[6])

        # Restore button — always visible; disabled/grey for active accounts
        can_restore = not is_active and bool(deleted_at)
        restore_btn = QPushButton()
        restore_btn.setObjectName("restoreBtn" if can_restore else "restoreBtnDisabled")
        restore_btn.setFixedSize(QSize(30, 30))
        restore_btn.setIcon(get_icon("restore"))
        restore_btn.setIconSize(QSize(16, 16))
        if can_restore:
            restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            restore_btn.setToolTip(f"Reactivate {full_name}")
            restore_btn.clicked.connect(
                lambda _, uid=user["id"], name=full_name:
                    self._handle_restore(uid, name)
            )
        else:
            restore_btn.setCursor(Qt.CursorShape.ForbiddenCursor)
            restore_btn.setToolTip("Account is already active")
            restore_btn.setEnabled(False)

        restore_wrapper = QHBoxLayout()
        restore_wrapper.setContentsMargins(0, 0, 0, 0)
        restore_wrapper.setSpacing(0)
        restore_wrapper.addStretch()
        restore_wrapper.addWidget(restore_btn)
        h.addLayout(restore_wrapper)
        h.setStretch(h.count() - 1, stretches[7])

        return row

    def _make_empty_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("tableEmptyRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 32, 20, 32)
        lbl = QLabel("No users found.")
        lbl.setObjectName("tableEmptyLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(lbl)
        return row

    # Render
    def _render_page(self):
        # Clear existing rows
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(self._filtered)
        total_pages = max(1, -(-total // ROWS_PER_PAGE))
        self._page = max(0, min(self._page, total_pages - 1))

        start = self._page * ROWS_PER_PAGE
        page_rows = self._filtered[start:start + ROWS_PER_PAGE]

        if not page_rows:
            self.rows_layout.addWidget(self._make_empty_row())
        else:
            for i, user in enumerate(page_rows):
                self.rows_layout.addWidget(self._make_data_row(user, alternate=i % 2 == 1))

                if i < len(page_rows) - 1:
                    div = QFrame()
                    div.setObjectName("tableRowDivider")
                    div.setFixedHeight(1)
                    self.rows_layout.addWidget(div)

        # Pagination controls
        self.page_lbl.setText(f"Page {self._page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)

        # Count label
        self.count_lbl.setText(f"{total} user{'s' if total != 1 else ''}")

    # Search & pagination
    def _on_search(self, text: str):
        q = text.strip().lower()
        if not q:
            self._filtered = list(self._all_rows)
        else:
            matches_active = "active".startswith(q) and not "inactive".startswith(q)
            matches_inactive = "inactive".startswith(q)
            self._filtered = [
                u for u in self._all_rows
                if q in f"{u['first_name']} {u['last_name']}".lower()
                or q in u["email"].lower()
                or q in u["role"].lower()
                or (matches_active and bool(u["is_active"]))
                or (matches_inactive and not bool(u["is_active"])) 
        ] 
        self._page = 0
        self._render_page()

    def _prev_page(self):
        self._page -= 1
        self._render_page()

    def _next_page(self):
        self._page += 1
        self._render_page()

    # Role change
    def _handle_role_change(self, user_id: int, name: str, role: str, combo: "QComboBox"):
        from src.db import update_user_role
        from src.widgets.confirm_dialog import ConfirmDialog

        dlg = ConfirmDialog(
            self.window(),
            title="Change Role",
            message=f"Set {name}'s role to {role}?"
        )
        dlg.exec()
        if not dlg.result_yes():
            # Revert combo to the current DB value without triggering signal
            combo.blockSignals(True)
            from src.db import get_user_by_id
            user = get_user_by_id(user_id)
            if user and user["role"] in ROLE_OPTIONS:
                combo.setCurrentText(user["role"])
            combo.blockSignals(False)
            return

        if update_user_role(user_id, role):
            toast_success(self, f"{name}'s role updated to {role}.")
            self.refresh()
        else:
            toast_error(self, f"Failed to update {name}'s role.")

    def _refresh_days(self):
        pass  # No-op — purge date is static, no per-second re-render needed

    # Restore
    def _handle_restore(self, user_id: int, name: str):
        from src.db import reactivate_user
        from src.widgets.confirm_dialog import ConfirmDialog

        dlg = ConfirmDialog(
            self.window(),
            title="Reactivate Account",
            message=f"Reactivate {name}'s account? Their data will be fully restored."
        )
        dlg.exec()
        if not dlg.result_yes():
            return

        if reactivate_user(user_id):
            toast_success(self, f"{name}'s account has been reactivated.")
            self.refresh()
        else:
            toast_error(self, f"Failed to reactivate {name}'s account.")

    # Lifecycle
    def refresh(self):
        from src.db import get_all_users
        self._all_rows = get_all_users()
        self._filtered = list(self._all_rows)

        # Re-apply search if active
        q = self.search_input.text().strip().lower()
        if q:
            matches_active = "active".startswith(q) and not "inactive".startswith(q)
            matches_inactive = "inactive".startswith(q)
            self._filtered = [
                u for u in self._all_rows
                if q in f"{u['first_name']} {u['last_name']}".lower()
                or q in u["email"].lower()
                or q in u["role"].lower()
                or (matches_active and bool(u["is_active"]))
                or (matches_inactive and not bool(u["is_active"])) 
            ]

        self._render_page()
