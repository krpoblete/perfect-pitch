"""
tour_overlay.py  —  Interactive guided-tour overlay for Perfect Pitch
=====================================================================
Drop this file at:  src/widgets/tour_overlay.py

Usage (from MainWindow):
    from src.widgets.tour_overlay import TourOverlay
    overlay = TourOverlay(self.centralWidget(), steps)
    overlay.closed.connect(some_callback)

Each step dict:
    {
        "target":        QWidget | str | None,  # widget/objectName to spotlight; None → centred card
        "title":         str,
        "body":          str,
        "callout_side":  "bottom" | "top" | "right" | "left"   (default "bottom")
        "on_enter":      callable | None        # called before spotlight is applied (page switches etc.)
    }

NOTE  — add these objectNames to DashboardPage so the spotlight snaps
        precisely onto the right widgets:
          • stats container  →  self.stats_section.setObjectName("statsSection")
          • history frame    →  self.history_frame.setObjectName("historySection")
        The tour still works without them (falls back to broader targets).
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import (
    Qt, QRect, QPoint, pyqtSignal, QEvent,
    QPropertyAnimation, QEasingCurve, QTimer,
)
from PyQt6.QtGui import QPainter, QColor, QPen

class TourOverlay(QWidget):
    """Full-window guided-tour overlay with animated spotlight highlighting."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget, steps: list):
        super().__init__(parent)
        self._steps          = steps
        self._step_index     = 0
        self._highlight_rect = QRect()

        # Cover the whole parent widget
        self.setGeometry(parent.rect())
        self.raise_()
        self.setMouseTracking(True)

        self._build_callout()
        parent.installEventFilter(self)

        # Fade-in
        self.setWindowOpacity(0.0)
        self.show()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_in = anim  # keep reference alive

        self._show_step(0)

    # event filter (track parent resize)
    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
            if hasattr(self, "callout"):
                self._show_step(self._step_index)
        return super().eventFilter(obj, event)

    # callout card
    # CARD_W is the only value you need to change if you want a wider/narrower card.
    CARD_W = 480

    def _build_callout(self):
        card = QFrame(self)
        card.setObjectName("tourCallout")
        card.setFixedWidth(self.CARD_W)
        card.raise_()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(0)

        # header row: step counter + close
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self._step_lbl = QLabel()
        self._step_lbl.setObjectName("tourStepLabel")
        header.addWidget(self._step_lbl)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("tourCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_tour)
        header.addWidget(close_btn)

        layout.addLayout(header)
        layout.addSpacing(10)

        # title
        self._title_lbl = QLabel()
        self._title_lbl.setObjectName("tourTitle")
        self._title_lbl.setWordWrap(True)
        # Pin width so Qt can compute heightForWidth correctly when adjustSize() runs
        self._title_lbl.setFixedWidth(self.CARD_W - 48)   # 48 = left(24) + right(24) margins
        layout.addWidget(self._title_lbl)
        layout.addSpacing(8)

        # body
        self._body_lbl = QLabel()
        self._body_lbl.setObjectName("tourBody")
        self._body_lbl.setWordWrap(True)
        # Same pin – this is the key fix for text being cropped on long steps
        self._body_lbl.setFixedWidth(self.CARD_W - 48)
        layout.addWidget(self._body_lbl)
        layout.addSpacing(18)

        # dot progress
        self._dots_row = QHBoxLayout()
        self._dots_row.setSpacing(6)
        self._dots_row.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._dots_row)
        layout.addSpacing(14)

        # button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._skip_btn = QPushButton("Skip tour")
        self._skip_btn.setObjectName("tourSkipBtn")
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.clicked.connect(self.close_tour)

        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("tourNavBtn")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self._prev_step)

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("tourNavBtnPrimary")
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._next_step)

        btn_row.addWidget(self._skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._back_btn)
        btn_row.addWidget(self._next_btn)
        layout.addLayout(btn_row)

        # Start hidden so the card never flashes at (0, 0) before being positioned
        card.hide()
        self.callout = card

    # step rendering
    def _show_step(self, index: int):
        self._step_index = index
        step  = self._steps[index]
        total = len(self._steps)

        # Labels (update immediately so user sees content right away)
        self._step_lbl.setText(f"STEP  {index + 1} / {total}")
        self._title_lbl.setText(step["title"])
        self._body_lbl.setText(step["body"])

        # Back button
        self._back_btn.setVisible(index > 0)

        # Next / Done
        if index == total - 1:
            self._next_btn.setText("Done")
            self._next_btn.setObjectName("tourNavBtnDone")
        else:
            self._next_btn.setText("Next")
            self._next_btn.setObjectName("tourNavBtnPrimary")
        self._next_btn.style().unpolish(self._next_btn)
        self._next_btn.style().polish(self._next_btn)

        # Rebuild progress dots
        while self._dots_row.count():
            item = self._dots_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i in range(total):
            dot = QLabel()
            dot.setObjectName("tourDotActive" if i == index else "tourDot")
            dot.setFixedSize(8, 8)
            self._dots_row.addWidget(dot)
        self._dots_row.addStretch()

        # Page switch / on_enter
        # If the step defines a page transition or scroll action, run it first,
        # then wait 160 ms for Qt to finish rendering before resolving the target.
        on_enter = step.get("on_enter")
        if on_enter:
            on_enter()
            # Hide the callout so it doesn't linger in the wrong spot
            # while the page redraws; _apply_spotlight will show it again.
            self.callout.hide()
            self._highlight_rect = QRect()
            self.update()
            QTimer.singleShot(
                160,
                lambda idx=index: self._apply_spotlight(idx),
            )
        else:
            self._apply_spotlight(index)

    # spotlight / callout positioning (deferred-safe)
    def _apply_spotlight(self, index: int):
        """Resolve the target widget and position the callout card.

        Safe to call after a QTimer delay because it checks _step_index hasn't
        changed (i.e. user didn't click Next super-fast).
        """
        if self._step_index != index:
            return  # user already moved on

        step = self._steps[index]
        self._highlight_rect = self._resolve_target(step.get("target"))
        self.callout.adjustSize()
        self._position_callout(step.get("callout_side", "bottom"))
        self.callout.raise_()
        self.callout.show()   # safe to show now that position is final
        self.update()

    # target resolution
    def _resolve_target(self, target) -> QRect:
        if target is None:
            return QRect()

        # callable: step provides its own geometry function 
        # The callable closes over whatever widgets/pages it needs and returns
        # a QRect already in overlay-parent coordinates.
        if callable(target):
            try:
                result = target()
                return result if (result and result.isValid()) else QRect()
            except Exception:
                return QRect()

        parent = self.parent()

        if isinstance(target, str):
            widget = parent.findChild(QWidget, target)
        elif isinstance(target, QWidget):
            widget = target
        else:
            return QRect()

        if widget and widget.isVisible():
            top_left = widget.mapTo(parent, QPoint(0, 0))
            pad = 12
            return QRect(top_left, widget.size()).adjusted(-pad, -pad, pad, pad)

        return QRect()

    # callout positioning 
    def _position_callout(self, side: str):
        self.callout.adjustSize()
        cw  = self.callout.width()
        ch  = self.callout.height()
        ow  = self.width()
        oh  = self.height()
        h   = self._highlight_rect
        gap = 22

        if h.isNull() or not h.isValid():
            # No spotlight → centre the card
            x = (ow - cw) // 2
            y = (oh - ch) // 2
        elif side == "bottom":
            x = h.left() + (h.width() - cw) // 2
            y = h.bottom() + gap
        elif side == "top":
            x = h.left() + (h.width() - cw) // 2
            y = h.top() - ch - gap
        elif side == "right":
            x = h.right() + gap
            y = h.top() + (h.height() - ch) // 2
        else:   # left
            x = h.left() - cw - gap
            y = h.top() + (h.height() - ch) // 2

        margin = 16
        x = max(margin, min(x, ow - cw - margin))
        y = max(margin, min(y, oh - ch - margin))
        self.callout.move(x, y)

    # navigation
    def _next_step(self):
        if self._step_index >= len(self._steps) - 1:
            self.close_tour()
        else:
            self._show_step(self._step_index + 1)

    def _prev_step(self):
        if self._step_index > 0:
            self._show_step(self._step_index - 1)

    def close_tour(self):
        try:
            self.parent().removeEventFilter(self)
        except Exception:
            pass
        self.closed.emit()
        self.hide()
        self.deleteLater()

    # painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        dim   = QColor(0, 0, 0, 192)
        r     = self.rect()
        h     = self._highlight_rect

        if h.isNull() or not h.isValid():
            painter.fillRect(r, dim)
        else:
            # Four dark rectangles surrounding the spotlight window
            painter.fillRect(QRect(0,         0,          r.width(), h.top()),               dim)
            painter.fillRect(QRect(0,         h.bottom(), r.width(), r.height()-h.bottom()), dim)
            painter.fillRect(QRect(0,         h.top(),    h.left(),  h.height()),             dim)
            painter.fillRect(QRect(h.right(), h.top(),    r.width()-h.right(), h.height()),   dim)

            # Spotlight glow border
            pen = QPen(QColor(255, 255, 255, 55), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(h.adjusted(1, 1, -1, -1), 12, 12)

            # Outer soft glow
            pen2 = QPen(QColor(74, 158, 255, 30), 6)
            painter.setPen(pen2)
            painter.drawRoundedRect(h.adjusted(-3, -3, 3, 3), 15, 15)

        painter.end()

    # navigation is button-only; clicks on the dim overlay are absorbed
    def mousePressEvent(self, event):
        # Intentionally do nothing – users must use the Next / Back buttons.
        # We still call super() so Qt can route the event to child buttons
        # (the callout card) without any side-effects on the overlay itself.
        super().mousePressEvent(event)
