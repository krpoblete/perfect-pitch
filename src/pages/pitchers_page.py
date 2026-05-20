from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit,
    QFrame, QDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QSize

from src.utils.icons import get_icon
from src.utils.toast import toast_success
from src.widgets.confirm_dialog import ConfirmDialog
from src.widgets.trend_chart import TrendChart

def _fmt_date(dt_str: str) -> str:
    """Return 'Mon DD, YYYY' from a date or datetime string."""
    try:
        return date.fromisoformat(dt_str[:10]).strftime("%b %d, %Y")
    except Exception:
        return dt_str

class PitcherTrendDialog(QDialog):
    """
    Modal dialog showing a single pitcher's full performance trend chart.
    Opened from the Coach Dashboard pitcher overview cards via 'View →'.
    """
    def __init__(self, parent, pitcher: dict, sessions: list):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("skeletonViewerDialog")
        self._name = f"{pitcher['first_name']} {pitcher['last_name']}"
        self._sessions = sessions
        self._build_ui()
        self._size_and_position(parent)

    def _size_and_position(self, parent):
        try:
            top = parent.window()
            geo = top.frameGeometry()
            w = int(geo.width() * 0.75)
            max_h = int(geo.height() * 0.75)
            cx = geo.x() + (geo.width() - w) // 2
            cy_base = geo.y() + (geo.height() - max_h) // 2
        except Exception:
            from PyQt6.QtWidgets import QApplication
            sg = QApplication.primaryScreen().availableGeometry()
            w = int(sg.width() * 0.75)
            max_h = int(sg.height() * 0.75)
            cx = sg.x() + (sg.width() - w) // 2
            cy_base = sg.y() + (sg.height() - max_h) // 2

        HEADER = 52
        DIVIDERS = 2
        STATS = 90
        CHART = 280
        FOOTER = 44
        PADDING = 56
        content_h = HEADER + DIVIDERS + STATS + CHART + FOOTER + PADDING
        h = min(content_h, max_h)
        cy = cy_base + (max_h - h) // 2

        self.setFixedSize(w, h)
        self.move(cx, cy)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("skeletonViewerHeader")
        header.setFixedHeight(52)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 16, 0)
        hl.setSpacing(10)

        badge = QLabel("PERFORMANCE TREND")
        badge.setObjectName("skeletonViewerBadge")
        hl.addWidget(badge)

        name_lbl = QLabel(self._name)
        name_lbl.setObjectName("skeletonViewerFooterLabel")
        hl.addWidget(name_lbl)

        hl.addStretch()

        close_btn = QPushButton("✕  Close")
        close_btn.setObjectName("skeletonViewerCloseBtn")
        close_btn.setFixedHeight(32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)

        root.addWidget(header)

        # Divider
        div_top = QFrame()
        div_top.setObjectName("skeletonViewerDivider")
        div_top.setFixedHeight(1)
        root.addWidget(div_top)

        # Scrollable Body
        scroll = QScrollArea()
        scroll.setObjectName("dashScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("dashContainer")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 28, 32, 28)
        bl.setSpacing(16)
        bl.setAlignment(Qt.AlignmentFlag.AlignTop)

        total = len(self._sessions)
        pitches = sum(s["total_pitch"] or 0 for s in self._sessions)
        mistakes = sum(s["mistakes"] or 0 for s in self._sessions)
        avg_acc = (
            sum(float(s["accuracy"] or 0) for s in self._sessions) / total
            if total else 0.0
        )

        # Summary Stats Strip
        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)
        for label, value in [
            ("Sessions", str(total)),
            ("Total Pitches", str(pitches)),
            ("Total Mistakes", str(mistakes)),
            ("Avg Accuracy", f"{avg_acc:.1f}%"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label)
            lbl.setObjectName("dashStatLabel")
            val = QLabel(value)
            val.setObjectName("dashStatValue")
            val.setStyleSheet("color: #4ecb71; background: transparent;")
            col.addWidget(lbl)
            col.addWidget(val)
            stats_row.addLayout(col)
        stats_row.addStretch()
        bl.addLayout(stats_row)

        # Divider
        div_mid = QFrame()
        div_mid.setObjectName("tableDivider")
        div_mid.setFixedHeight(1)
        bl.addWidget(div_mid)

        # Chart - Shared TrendChart, Severity Dots Off (Pitcher View is Clean)
        if self._sessions:
            chart = TrendChart(self._sessions, show_severity_dots=False, parent=body)
            bl.addWidget(chart)
        else:
            empty = QLabel("No session data available for this pitcher.")
            empty.setObjectName("tableEmptyLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bl.addWidget(empty)

        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # Footer Divider
        div_bot = QFrame()
        div_bot.setObjectName("skeletonViewerDivider")
        div_bot.setFixedHeight(1)
        root.addWidget(div_bot)

        # Footer
        footer = QWidget()
        footer.setObjectName("skeletonViewerFooter")
        footer.setFixedHeight(44)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        session_lbl = QLabel(
            f"{total} session{'s' if total != 1 else ''}  ·  {pitches} total pitch{'es' if pitches != 1 else ''}"
        )
        session_lbl.setObjectName("skeletonViewerFooterLabel")
        fl.addWidget(session_lbl)
        fl.addStretch()
        root.addWidget(footer)

ROWS_PER_PAGE = 10
COLUMNS = ["Full Name", "Email", "Throwing Hand", "Pitch Threshold", "Date Joined", ""]

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

        # Search Bar - Plain Input, Active Border on Focus
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

        # Table Header
        self.table_container = QWidget()
        self.table_container.setObjectName("tableContainer")
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        # Column Header Row
        header = self._make_header_row()
        table_layout.addWidget(header)

        # Divider
        div = QFrame()
        div.setObjectName("tableDivider")
        div.setFixedHeight(1)
        table_layout.addWidget(div)

        # Rows Area
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

    # Table Builders
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

        stretches = [3, 3, 2, 2, 2, 1]

        # Full Name - Plain Label
        name_lbl = QLabel(full_name)
        name_lbl.setObjectName("tableCell")
        h.addWidget(name_lbl, stretch=stretches[0])

        values = [user["email"], hand, threshold, joined]
        for val, stretch in zip(values, stretches[1:-1]):
            lbl = QLabel(str(val))
            lbl.setObjectName("tableCell")
            if val in ("RHP", "LHP"):
                lbl.setObjectName(
                    "handBadgeRHP" if val == "RHP" else "handBadgeLHP"
                )
            h.addWidget(lbl, stretch=stretch)

        # Delete Button
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
        # Clear Existing Rows
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

        # Pagination Controls
        self.page_lbl.setText(f"Page {self._page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)

        # Count Label
        self.count_lbl.setText(f"{total} pitcher{'s' if total != 1 else ''}")

    # Search and Pagination
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

        # Re-Apply Search if Active
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
