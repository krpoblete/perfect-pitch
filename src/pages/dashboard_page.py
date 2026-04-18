from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize

from src.utils.icons import get_icon

ROWS_PER_PAGE = 10

def _fmt_dt(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return dt_str or "—"

class DashboardPage(QWidget):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self._role = None
        self._sessions_all = []
        self._sessions_filtered = []
        self._page = 0
        self.setObjectName("contentPage")
        self.build_ui()

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("dashScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setObjectName("dashContainer")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(40, 36, 40, 40)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._container)
        outer.addWidget(scroll)

    # Stat card builders
    def _stat_card(self, icon_name: str, label: str,
                   value: str, color: str, wide: bool = False) -> QWidget:
        card = QWidget()
        card.setObjectName("dashStatCard")
        if wide:
            card.setMinimumWidth(200)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("dashStatIcon")
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setPixmap(get_icon(icon_name, color=color, size=22).pixmap(22, 22))

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        lbl = QLabel(label)
        lbl.setObjectName("dashStatLabel")

        val = QLabel(value)
        val.setObjectName("dashStatValue")
        val.setStyleSheet(f"color: {color}; background: transparent;")

        text_col.addWidget(lbl)
        text_col.addWidget(val)

        layout.addWidget(icon_lbl)
        layout.addLayout(text_col)
        layout.addStretch()
        return card
    
    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("dashSectionTitle")
        return lbl
    
    def _divider(self) -> QFrame:
        f = QFrame()
        f.setObjectName("tableDivider")
        f.setFixedHeight(1)
        return f
    
    # History table
    def _build_history_table(self, layout: QVBoxLayout,
                             columns: list, col_stretches: list,
                             rows: list, row_builder):
        layout.addWidget(self._section_title(
            "Pitching History" if self._role != "Admin" else "Recent Sessions"
        ))
        layout.addSpacing(14)

        table = QWidget()
        table.setObjectName("tableContainer")
        tl = QVBoxLayout(table)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)

        # Header
        hrow = QWidget()
        hrow.setObjectName("tableHeaderRow")
        hrow.setFixedHeight(44)
        hl = QHBoxLayout(hrow)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(0)
        for col, stretch in zip(columns, col_stretches):
            lbl = QLabel(col)
            lbl.setObjectName("tableHeaderCell")
            hl.addWidget(lbl, stretch=stretch)
        tl.addWidget(hrow)
        tl.addWidget(self._divider())

        # Rows container
        self._rows_widget = QWidget()
        self._rows_widget.setObjectName("tableRows")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setSpacing(0)
        tl.addWidget(self._rows_widget)

        layout.addWidget(table)
        layout.addSpacing(14)

        # Pagination
        pag = QHBoxLayout()
        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.setObjectName("paginationBtn")
        self._prev_btn.setFixedHeight(34)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(self._prev_page)

        self._page_lbl = QLabel()
        self._page_lbl.setObjectName("pageLabel")
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_lbl.setFixedWidth(100)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("paginationBtn")
        self._next_btn.setFixedHeight(34)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._next_page)

        pag.addStretch()
        pag.addWidget(self._prev_btn)
        pag.addWidget(self._page_lbl)
        pag.addWidget(self._next_btn)
        layout.addLayout(pag)

        # Store row builder for pagination
        self._row_builder = row_builder
        self._col_stretches = col_stretches

    def _render_rows(self):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(self._sessions_filtered)
        total_pages = max(1, -(-total // ROWS_PER_PAGE))
        self._page = max(0, min(self._page, total_pages - 1))

        start = self._page * ROWS_PER_PAGE
        page_rows = self._sessions_filtered[start:start + ROWS_PER_PAGE]

        if not page_rows:
            empty = QWidget()
            empty.setObjectName("tableEmptyRow")
            el = QHBoxLayout(empty)
            el.setContentsMargins(20, 32, 20, 32)
            lbl = QLabel("No sessions recorded yet.")
            lbl.setObjectName("tableEmptyLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            el.addWidget(lbl)
            self._rows_layout.addWidget(empty)
        else:
            for i, row in enumerate(page_rows):
                self._rows_layout.addWidget(
                    self._row_builder(row, alternate=i % 2 == 1)
                )
                if i < len(page_rows) - 1:
                    div = QFrame()
                    div.setObjectName("tableRowDivider")
                    div.setFixedHeight(1)
                    self._rows_layout.addWidget(div)

        self._page_lbl.setText(f"Page {self._page + 1} of {total_pages}")
        self._prev_btn.setEnabled(self._page > 0)
        self._next_btn.setEnabled(self._page < total_pages - 1)

    def _prev_page(self):
        self._page -= 1
        self._render_rows()

    def _next_page(self):
        self._page += 1
        self._render_rows()

    def _make_session_row(self, session, alternate: bool,
                          stretches: list, extra_col=None) -> QWidget:
        row = QWidget()
        row.setObjectName("tableRowAlt" if alternate else "tableRow")
        row.setFixedHeight(48)
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(0)

        accuracy = session["accuracy"]
        acc_str = f"{accuracy:.2f}%" if accuracy else "0.00%"

        cells = []
        if extra_col:
            cells.append((extra_col(session), stretches[0]))
            cells.append((_fmt_dt(session["date"]), stretches[1]))
            cells.append((str(session["total_pitch"]), stretches[2]))
            cells.append((str(session["mistakes"]), stretches[3]))
            cells.append((acc_str, stretches[4]))
        else:
            cells.append((_fmt_dt(session["date"]), stretches[0]))
            cells.append((str(session["total_pitch"]), stretches[1]))
            cells.append((str(session["mistakes"]), stretches[2]))
            cells.append((acc_str, stretches[3]))

        for text, stretch in cells:
            lbl = QLabel(str(text))
            lbl.setObjectName("tableCell")
            h.addWidget(lbl, stretch=stretch)
        return row
    
    # Role dasboards
    def _build_pitcher_dashboard(self):
        from src.db import get_dashboard_stats, get_sessions_for_user
        stats = get_dashboard_stats(self.user_id)
        sessions = get_sessions_for_user(self.user_id)

        layout = self._layout

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(6)
        sub = QLabel("Your personal pitching overview")
        sub.setObjectName("dashSubtitle")
        layout.addWidget(sub)
        layout.setSpacing(28)

        grid = QGridLayout()
        grid.setSpacing(14)

        cards = [
            ("play-handball", "Total Pitches", str(int(stats["total_pitches"])), "#4a9eff"),
            ("x-mark", "Total Mistakes", str(int(stats["total_mistakes"])), "#e05555"),
            ("target", "Total Sessions", str(int(stats["total_sessions"])), "#4ecb71"),
            ("play-handball", "Avg Pitch", f"{stats['avg_pitch']:.1f}", "#4a9eff"), 
            ("x-mark", "Avg Mistakes", f"{stats['avg_mistakes']:.1f}", "#e05555"), 
            ("target", "Avg Accuracy", f"{stats['avg_accuracy']:.1f}", "#4ecb71"), 
        ]
        for i, (icon, label, value, color) in enumerate(cards):
            grid.addWidget(self._stat_card(icon, label, value, color), i // 3, i % 3)

        layout.addLayout(grid)
        layout.addSpacing(32)

        # Session history
        self._sessions_filtered = list(sessions)
        columns = ["Date", "Pitches", "Mistakes", "Accuracy"]
        stretches = [4, 2, 2, 2]
        self._build_history_table(
            layout, columns, stretches, sessions,
            lambda s, alternate: self._make_session_row(s, alternate, stretches)
        ) 
        self._render_rows()

    def _build_coach_dashboard(self):
        from src.db import get_coach_dashboard_stats, get_coach_pitcher_sessions
        stats = get_coach_dashboard_stats()
        sessions = get_coach_pitcher_sessions()

        layout = self._layout

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(6)
        sub = QLabel("Combined overview across all your pitchers")
        sub.setObjectName("dashSubtitle")
        layout.addWidget(sub)
        layout.setSpacing(28)

        grid = QGridLayout()
        grid.setSpacing(14)

        cards = [
            ("play-handball", "Total Pitches", str(int(stats["total_pitches"])), "#4a9eff"),
            ("x-mark", "Total Mistakes", str(int(stats["total_mistakes"])), "#e05555"),
            ("target", "Total Sessions", str(int(stats["total_sessions"])), "#4ecb71"),
            ("play-handball", "Avg Pitch", f"{stats['avg_pitch']:.1f}", "#4a9eff"), 
            ("x-mark", "Avg Mistakes", f"{stats['avg_mistakes']:.1f}", "#e05555"), 
            ("target", "Avg Accuracy", f"{stats['avg_accuracy']:.1f}", "#4ecb71"), 
        ]
        for i, (icon, label, value, color) in enumerate(cards):
            grid.addWidget(self._stat_card(icon, label, value, color), i // 3, i % 3)

        layout.addLayout(grid)
        layout.addSpacing(32)

        # Session history with pitcher name column
        self._sessions_filtered = list(sessions)
        columns = ["Pitcher", "Date", "Pitches", "Mistakes", "Accuracy"]
        stretches = [3, 4, 2, 2, 2]
        self._build_history_table(
            layout, columns, stretches, sessions,
            lambda s, alternate: self._make_session_row(
                s, alternate, stretches,
                extra_col=lambda row: row["pitcher_name"]
            )
        )
        self._render_rows()

    def _build_admin_dashboard(self):
        from src.db import get_admin_dashboard_stats, get_dashboard_stats, get_sessions_for_user
        user_stats, session_stats = get_admin_dashboard_stats()
        personal_stats = get_dashboard_stats(self.user_id)
        sessions = get_sessions_for_user(self.user_id)

        layout = self._layout

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(6)
        sub = QLabel("App-wide overview and your personal session history")
        sub.setObjectName("dashSubtitle")
        layout.addWidget(sub)
        layout.setSpacing(28)

        # Users card — wide with active/inactive breakdown
        users_card = QWidget()
        users_card.setObjectName("dashStatCardWide")
        ul = QHBoxLayout(users_card)
        ul.setContentsMargins(24, 20, 24, 20)
        ul.setSpacing(0)

        # Total users
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setPixmap(get_icon("users-group", color="#4a9eff", size=22).pixmap(22, 22))
        total_col = QVBoxLayout()
        total_col.setSpacing(2)
        total_lbl = QLabel("Total Users")
        total_lbl.setObjectName("dashStatLabel")
        total_val = QLabel(str(int(user_stats["total_users"])))
        total_val.setObjectName("dashStatValue")
        total_val.setStyleSheet("color: #4a9eff; background: transparent;")
        total_col.addWidget(total_lbl)
        total_col.addWidget(total_val)
        ul.addWidget(icon_lbl)
        ul.addSpacing(14)
        ul.addLayout(total_col)
        ul.addStretch()

        # Active / Inactive breakdown
        for label, value, color in [
            ("Active", str(int(user_stats["active_users"])), "#4ecb71"),
            ("Inactive", str(int(user_stats["inactive_users"])), "#e05555"),
        ]:
            div = QFrame()
            div.setObjectName("dashVertDivider")
            div.setFixedWidth(1)
            ul.addWidget(div)
            ul.addSpacing(28)
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label)
            lbl.setObjectName("dashStatLabel")
            val = QLabel(value)
            val.setObjectName("dashStatValue")
            val.setStyleSheet(f"color: {color}; background: transparent;")
            col.addWidget(lbl)
            col.addWidget(val)
            ul.addLayout(col)
            ul.addSpacing(28)

        layout.addWidget(users_card)
        layout.addSpacing(14)

        # App-wide bottom stat grid
        grid = QGridLayout()
        grid.setSpacing(14)
        bottom_cards = [
            ("users", "Total Pitchers", str(int(user_stats["total_pitchers"])), "#4ecb71"),
            ("users", "Total Coaches", str(int(user_stats["total_coaches"])), "#f0a500"),
            ("user", "Total Admins", str(int(user_stats["total_admins"])), "#cc77ff"),
            ("play-handball", "Total Sessions", str(int(session_stats["total_sessions"])), "#4a9eff"),
        ]
        for i, (icon, label, value, color) in enumerate(bottom_cards):
            grid.addWidget(self._stat_card(icon, label, value, color), 0, i)
        layout.addLayout(grid)
        layout.addSpacing(32)

        # Personal session history
        self._sessions_filtered = list(sessions)
        columns = ["Date", "Pitches", "Mistakes", "Accuracy"]
        stretches = [4, 2, 2, 2]
        self._build_history_table(
            layout, columns, stretches, sessions,
            lambda s, alternate: self._make_session_row(s, alternate, stretches)
        ) 
        self._render_rows()

    # Lifecycle
    def refresh(self):
        from src.db import get_user_by_id

        # Clear layout
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear nested layouts
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        user = get_user_by_id(self.user_id)
        self._role = user["role"] if user else "Pitcher"
        self._page = 0

        if self._role == "Admin":
            self._build_admin_dashboard()
        elif self._role == "Coach":
            self._build_coach_dashboard()
        else:
            self._build_pitcher_dashboard()
