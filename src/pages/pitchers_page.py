from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit,
    QScrollArea, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QKeyEvent

from src.utils.icons import get_icon
from src.utils.toast import toast_success, toast_error
from src.widgets.confirm_dialog import ConfirmDialog

ROWS_PER_PAGE = 10
COLUMNS = ["Full Name", "Email", "Throwing Hand", "Pitch Threshold", "Date Joined", ""]

def _fmt_date(dt_str: str) -> str:
    try:
        return date.fromisoformat(dt_str[:10]).strftime("%b %d, %Y")
    except Exception:
        return dt_str

class PitchersPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentPage")
        self._all_rows = []
        self._filtered = []
        self._page = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 28)
        layout.setSpacing(0)

        # Header
        header_row = QHBoxLayout()

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("Pitchers")
        title.setObjectName("pageTitle")
        self.count_lbl = QLabel()
        self.count_lbl.setObjectName("pitchersCountLabel")
        title_col.addWidget(title)
        title_col.addWidget(self.count_lbl)

        # Search bar
        search_wrapper = QWidget()
        search_wrapper.setObjectName("searchWrapper")
        search_wrapper.setFixedHeight(40)
        search_wrapper.setFixedWidth(280)
        sw_layout = QHBoxLayout(search_wrapper)
        sw_layout.setContentsMargins(10, 0, 10, 0)
        sw_layout.setSpacing(6)

        search_icon = QLabel()
        search_icon.setFixedSize(16, 16)
        search_icon.setPixmap(get_icon("search", color="#555555", size=16).pixmap(16, 16))

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search pitchers...")
        self.search_input.textChanged.connect(self._on_search)

        sw_layout.addWidget(search_icon)
        sw_layout.addWidget(self.search_input)

        header_row.addLayout(title_col)
        header_row.addStretch()
        header_row.addWidget(search_wrapper)
        layout.addLayout(header_row)
        layout.addSpacing(24)

        # Table header
        self.table_container = QWidget()
        self.table_container.setObjectName("tableContainer")
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        # Column header row
        header = self._make_header_row()
        table_layout.addWidget(header)

        # Divider
        div = QFrame()
        div.setObjectName("tableDivider")
        div.setFixedHeight(1)
        table_layout.addWidget(div)

        # Rows area
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

        stretches = [3, 3, 2, 2, 2, 1]
        for col, stretch in zip(COLUMNS, stretches):
            lbl = QLabel(col)
            lbl.setObjectName("tableHeaderCell")
            h.addWidget(lbl, stretch=stretch)
        return row
    
    def _make_data_row(self, user, alternate: bool) -> QWidget:
        row = QWidget()
        row.setObjectName("tableRowAlt" if alternate else "tableRow")
        row.setFixedHeight(52)
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(0)

        full_name = f"{user['first_name']} {user['last_name']}"
        threshold = str(user["pitch_threshold"]) if user["pitch_threshold"] else "—"
        hand = user["throwing_hand"] if user["throwing_hand"] else "—"
        joined = _fmt_date(user["created_at"])

        values = [full_name, user["email"], hand, threshold, joined]
        stretches = [3, 3, 2, 2, 2, 1]

        for val, stretch in zip(values, stretches[:-1]):
            lbl = QLabel(str(val))
            lbl.setObjectName("tableCell")
            if val in ("RHP", "LHP"):
                lbl.setObjectName(
                    "handBadgeRHP" if val == "RHP" else "handBadgeLHP"
                )
            h.addWidget(lbl, stretch=stretch)

        # Delete button
        del_btn = QPushButton()
        del_btn.setObjectName("tableDeleteBtn")
        del_btn.setFixedSize(30, 30)
        del_btn.setIcon(get_icon("trash", color="#555555", size=15))
        del_btn.setIconSize(QSize(15, 15))
        del_btn.setToolTip(f"Remove {full_name}")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda _, uid=user["id"], name=full_name: self._handle_delete(uid, name))

        del_wrapper = QHBoxLayout()
        del_wrapper.setContentsMargins(0, 0, 0, 0)
        del_wrapper.addStretch()
        del_wrapper.addWidget(del_btn)
        h.addLayout(del_wrapper)
        h.setStretch(h.count() - 1, stretches[-1])

        return row
    
    def _make_empty_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("tableEmptyRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 32, 20, 32)
        lbl = QLabel("No pitchers found.")
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
        self.count_lbl.setText(f"{total} pitcher{'s' if total != 1 else ''}")

    # Search & pagination
    def _on_search(self, text: str):
        q = text.strip().lower()
        if not q:
            self._filtered = list(self._all_rows)
        else:
            matches_rhp = "rhp".startswith(q)
            matches_lhp = "lhp".startswith(q)
            self._filtered = [
                u for u in self._all_rows
                if q in f"{u['first_name']} {u['last_name']}".lower()
                or q in u["email"].lower()
                or q in str(u["pitch_threshold"] or "")
                or (matches_rhp and (u["throwing_hand"] or "") == "RHP")
                or (matches_lhp and (u["throwing_hand"] or "") == "LHP")
            ]
        self._page = 0
        self._render_page()

    def _prev_page(self):
        self._page -= 1
        self._render_page()

    def _next_page(self):
        self._page += 1
        self._render_page()

    # Delete
    def _handle_delete(self, user_id: int, name: str):
        dlg = ConfirmDialog(
            self.window(),
            title="Remove Pitcher",
            message=f"Are you sure you want to remove {name} from the team?"
        )
        dlg.exec()
        if not dlg.result_yes():
            return
        
        from src.db import deactivate_user
        deactivate_user(user_id)
        toast_success(self, f"{name} has been removed.")
        self.refresh()

    # Lifecycle
    def refresh(self):
        from src.db import get_pitchers
        self._all_rows = get_pitchers()
        self._filtered = list(self._all_rows)

        # Re-apply search if active
        q = self.search_input.text().strip().lower()
        if q:
            matches_rhp = "rhp".startswith(q)
            matches_lhp = "lhp".startswith(q)
            self._filtered = [
                u for u in self._all_rows
                if q in f"{u['first_name']} {u['last_name']}".lower()
                or q in u["email"].lower()
                or q in str(u["pitch_threshold"] or "")
                or (matches_rhp and (u["throwing_hand"] or "") == "RHP")
                or (matches_lhp and (u["throwing_hand"] or "") == "LHP")
            ]

        self._render_page()
