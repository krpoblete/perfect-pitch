from datetime import datetime

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter, QPen, QFont

# Severity color map
SEV_COLORS: dict[str, QColor] = {
    "Normal": QColor("#4ecb71"),
    "Elevated": QColor("#f0e040"),
    "Moderate": QColor("#f0a500"),
    "High": QColor("#e07800"),
    "Critical": QColor("#e05555"),
}

_DEFAULT_DOT_COLOR = QColor("#4ecb71")

def _fmt_date_short(dt_str: str) -> str:
    """Return 'Mon DD' from an ISO datetime string, e.g. 'Jun 04'."""
    try:
        return datetime.fromisoformat(dt_str).strftime("%b %d")
    except Exception:
        return dt_str or "—"

def _nice_step(top: int) -> int:
    """Return a human-friendly step value so the right axis has ≤6 ticks."""
    for step in [1, 2, 5, 10, 20, 50, 100]:
        if top / step <= 6:
            return step
    return max(1, top // 6)

class TrendChart(QWidget):
    # Palette
    _BAR_COLOR = QColor("#1a3a5c")
    _ACC_COLOR = QColor("#4ecb71")
    _MISS_COLOR = QColor("#e05555")
    _GRID_COLOR = QColor("#1e1e1e")
    _LABEL_COLOR = QColor("#555555")
    _TEXT_COLOR = QColor("#888888")
    _BG_COLOR = QColor("#0d0d0d")

    # Layout constants
    CHART_H = 220  # chart drawing area height (px)
    _PAD_L = 52
    _PAD_R = 52
    _PAD_T = 16
    _PAD_B = 36
    _LEG_H = 60    # legend + x-label zone below chart

    def __init__(
        self,
        sessions: list,
        show_severity_dots: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._sessions = sessions
        self._show_severity_dots = show_severity_dots
        self.setObjectName("trendChart")
        self.setFixedHeight(self.CHART_H + self._LEG_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # Paint
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        sessions = self._sessions
        n = len(sessions)
        W = self.width()
        H = self.CHART_H
        PL, PR, PT, PB = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B

        cw = W - PL - PR  # chart width
        ch = H - PT - PB  # chart height

        painter.fillRect(0, 0, W, H, self._BG_COLOR)

        if n == 0:
            self._draw_empty(painter, W, H)
            painter.end()
            return

        # Data
        pitches = [int(s.get("total_pitch") or 0) for s in sessions]
        mistakes = [int(s.get("mistakes") or 0) for s in sessions]
        accuracies = [float(s.get("accuracy") or 0) for s in sessions]
        severities = [s.get("worst_severity") or "Normal" for s in sessions]

        max_pitch = max(pitches) or 1
        r_step = _nice_step(max_pitch)
        r_max = ((max_pitch + r_step - 1) // r_step) * r_step
        r_ticks = list(range(0, r_max + 1, r_step))

        f_small = QFont()
        f_small.setPointSize(8)
        painter.setFont(f_small)

        for v in r_ticks:
            frac = v / r_max
            y = PT + ch - int(ch * frac)
            painter.setPen(QPen(self._GRID_COLOR, 1))
            painter.drawLine(PL, y, PL + cw, y)
            # Left axis - accuracy
            painter.setPen(self._ACC_COLOR)
            painter.drawText(
                QRect(0, y - 8, PL - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{int(frac * 100)}%",
            )
            # Right axis - pitch count
            painter.setPen(self._LABEL_COLOR)
            painter.drawText(
                QRect(PL + cw + 4, y - 8, PR - 4, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                str(v),
            )

        bar_w = max(4, min(24, cw // n - 4))
        inner_pad = bar_w // 2 + 2
        plot_w = cw - 2 * inner_pad
        xs = (
            [PL + cw // 2]
            if n == 1
            else [PL + inner_pad + int(i * plot_w / (n - 1)) for i in range(n)]
        )

        # Bars
        painter.setPen(Qt.PenStyle.NoPen)
        for x, p in zip(xs, pitches):
            bh = int(ch * p / r_max)
            painter.setBrush(self._BAR_COLOR)
            painter.drawRoundedRect(x - bar_w // 2, PT + ch - bh, bar_w, bh, 3, 3)

        # Mistake line
        pts_m = [(x, PT + ch - int(ch * m / r_max)) for x, m in zip(xs, mistakes)]
        painter.setPen(QPen(self._MISS_COLOR, 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(len(pts_m) - 1):
            painter.drawLine(pts_m[i][0], pts_m[i][1], pts_m[i+1][0], pts_m[i+1][1])

        # Accuracy line
        pts_a = [(x, PT + ch - int(ch * a / 100.0)) for x, a in zip(xs, accuracies)]
        painter.setPen(QPen(self._ACC_COLOR, 2))
        for i in range(len(pts_a) - 1):
            painter.drawLine(pts_a[i][0], pts_a[i][1], pts_a[i+1][0], pts_a[i+1][1])

        # Dots
        for (x, y), sev in zip(pts_a, severities):
            color = (
                SEV_COLORS.get(sev, _DEFAULT_DOT_COLOR)
                if self._show_severity_dots
                else _DEFAULT_DOT_COLOR
            )
            painter.setPen(QPen(color.darker(130), 1))
            painter.setBrush(color)
            painter.drawEllipse(x - 5, y - 5, 10, 10)

        painter.setPen(self._LABEL_COLOR)
        painter.setFont(f_small)
        label_step = max(1, n // 8)
        for i in range(0, n, label_step):
            painter.drawText(
                QRect(xs[i] - 30, H - PB + 4, 60, 18),
                Qt.AlignmentFlag.AlignCenter,
                _fmt_date_short(sessions[i]["date"]),
            )

        # Legend
        self._draw_legend(painter, H, PL)

        painter.end()

    def _draw_empty(self, painter: QPainter, W: int, H: int) -> None:
        """Draw a centred placeholder when there are no sessions."""
        f = QFont()
        f.setPointSize(10)
        painter.setFont(f)
        painter.setPen(self._LABEL_COLOR)
        painter.drawText(
            QRect(0, 0, W, H),
            Qt.AlignmentFlag.AlignCenter,
            "No sessions yet — complete a session to see your trend.",
        )

    def _draw_legend(self, painter: QPainter, H: int, PL: int) -> None:
        """Draw the series legend below the chart area."""
        ly = H + 8
        lx = PL
        f = QFont()
        f.setPointSize(8)
        painter.setFont(f)

        series = [
            (self._ACC_COLOR, False, "Accuracy %", 110),
            (self._MISS_COLOR, True, "Mistakes", 100),
            (self._BAR_COLOR, False, "Pitch Count (right axis)", 180),
        ]
        for color, dashed, text, advance in series:
            style = Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine
            painter.setPen(QPen(color, 2, style))
            painter.drawLine(lx, ly + 5, lx + 18, ly + 5)
            painter.setPen(self._TEXT_COLOR)
            painter.drawText(lx + 22, ly + 9, text)
            lx += advance
