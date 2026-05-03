from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QDialog, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from src.utils.icons import get_icon

class SessionSummaryDialog(QDialog):
    """
    Session summary — fills the camera feed area:
        Left  : joint-severity skeleton PNG, large and readable
        Right : session stats, worst joint callout, save button

    Sized to match the feed label geometry so it overlays it exactly.
    """
    # Fallback size used when parent geometry is unavailable
    _W_DEFAULT = 940
    _H_DEFAULT = 620

    def __init__(self, parent, pitch_count: int, mistakes: int, accuracy: float,
                 skeleton_path: str):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("summaryRoot")
        self._pitch_count = pitch_count
        self._mistakes = mistakes
        self._accuracy = accuracy
        self._skeleton_path = skeleton_path
        self._build_ui()
        self._size_and_position(parent)

    def _size_and_position(self, parent):
        """Match the dialog to the parent's feed_label geometry."""
        try:
            feed = parent.feed_label
            tl = feed.mapToGlobal(feed.rect().topLeft())
            w, h = feed.width(), feed.height()
        except Exception:
            w, h = self._W_DEFAULT, self._H_DEFAULT
            from PyQt6.QtWidgets import QApplication
            sg = QApplication.primaryScreen().availableGeometry()
            tl = sg.topLeft()
            tl.setX(tl.x() + (sg.width() - w) // 2)
            tl.setY(tl.y() + (sg.height() - h) // 2)
        self.setFixedSize(w, h)
        self.move(tl)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._load_skeleton)

    def _load_skeleton(self):
        import os
        path = self._skeleton_path
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                tw = self.skeleton_lbl.width()
                th = self.skeleton_lbl.height()
                scaled = pixmap.scaled(
                    tw, th,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.skeleton_lbl.setPixmap(scaled)
                self.skeleton_pending_lbl.hide()
                return
        # Replace text label with icon + message
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(16, 16)
        icon_lbl.setStyleSheet("background: transparent;")
        try:
            icon_lbl.setPixmap(
                get_icon("alert-triangle", color="#e05555", size=16).pixmap(16, 16)
            )
        except Exception:
            pass
        self.skeleton_pending_lbl.setText("Skeleton image unavailable")
        parent_layout = self.skeleton_pending_lbl.parentWidget().layout()
        idx = parent_layout.indexOf(self.skeleton_pending_lbl)
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(icon_lbl)
        row.addWidget(self.skeleton_pending_lbl)
        parent_layout.insertWidget(idx, row_w)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left: skeleton panel
        self.skeleton_panel = QWidget()
        self.skeleton_panel.setObjectName("summarySkeletonPanel")
        sk_layout = QVBoxLayout(self.skeleton_panel)
        sk_layout.setContentsMargins(20, 18, 12, 16)
        sk_layout.setSpacing(6)

        self.skeleton_lbl = QLabel()
        self.skeleton_lbl.setObjectName("summarySkeletonImage")
        self.skeleton_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.skeleton_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        sk_layout.addWidget(self.skeleton_lbl, stretch=1)

        self.skeleton_pending_lbl = QLabel("⏳  Generating joint severity map…")
        self.skeleton_pending_lbl.setObjectName("summarySubtitle")
        self.skeleton_pending_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sk_layout.addWidget(self.skeleton_pending_lbl)

        root.addWidget(self.skeleton_panel, stretch=65)

        # Divider
        div = QFrame()
        div.setObjectName("summaryDivider")
        div.setFrameShape(QFrame.Shape.VLine)
        root.addWidget(div)

        # Right: stats panel
        right = QWidget()
        right.setObjectName("summaryStatsPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(32, 32, 32, 28)
        rl.setSpacing(0)

        badge = QLabel("SESSION COMPLETE")
        badge.setObjectName("summaryBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignLeft)
        rl.addWidget(badge)

        rl.addSpacing(10)

        title = QLabel("Session Summary")
        title.setObjectName("summaryTitle")
        rl.addWidget(title)

        subtitle = QLabel("Here's how you performed across all pitches.")
        subtitle.setObjectName("summarySubtitle")
        subtitle.setWordWrap(True)
        rl.addWidget(subtitle)

        rl.addSpacing(28)

        for label, value, color in [
            ("Pitch Count", str(self._pitch_count), "#4a9eff"),
            ("Mistakes", str(self._mistakes), "#e05555"),
            ("Accuracy", f"{self._accuracy:.2f}%", "#4ecb71"),
        ]:
            rl.addWidget(self._stat_card(label, value, color))
            rl.addSpacing(10)

        rl.addStretch()

        acc_int = int(self._accuracy)
        if acc_int >= 80:
            band_color = "#4ecb71"
            band_icon = "star-filled"
            band_head = "Great session!"
            band_body = "Your mechanics are on point. Keep up the consistency."
        elif acc_int >= 50:
            band_color = "#f0a500"
            band_icon = "star-half"
            band_head = "Room to improve."
            band_body = "Review joint feedback and focus on flagged areas."
        else:
            band_color = "#e05555"
            band_icon = "star"
            band_head = "Focus on mechanics."
            band_body = "Several joints exceeded threshold, prioritize form next session."

        note_card = QWidget()
        note_card.setObjectName("summaryNoteCard")
        note_card.setStyleSheet(
            f"QWidget#summaryNoteCard {{"
            f" background: rgba(255,255,255,0.03);"
            f" border: 1px solid {band_color}55;"
            f" border-left: 3px solid {band_color};"
            f" border-radius: 8px;"
            f"}}"
        )
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(14, 12, 14, 12)
        note_layout.setSpacing(5)

        note_head_row = QHBoxLayout()
        note_head_row.setSpacing(8)
        note_head_row.setContentsMargins(0, 0, 0, 0)

        star_lbl = QLabel()
        star_lbl.setFixedSize(15, 15)
        star_lbl.setStyleSheet("background: transparent; border: none;")
        try:
            star_lbl.setPixmap(get_icon(band_icon, color=band_color, size=15).pixmap(15, 15))
        except Exception:
            pass
        note_head_row.addWidget(star_lbl)

        note_head = QLabel(band_head)
        note_head.setStyleSheet(
            f"color: {band_color}; background: transparent; "
            f"font-size: 13px; font-weight: 700; border: none;"
        )
        note_head_row.addWidget(note_head)
        note_head_row.addStretch()

        note_body = QLabel(band_body)
        note_body.setWordWrap(True)
        note_body.setStyleSheet(
            "color: #777777; background: transparent; "
            "font-size: 12px; border: none;"
        )
        note_layout.addLayout(note_head_row)
        note_layout.addWidget(note_body)
        rl.addWidget(note_card)

        rl.addSpacing(16)

        save_btn = QPushButton("Save and Close")
        save_btn.setObjectName("summarySaveBtn")
        save_btn.setFixedHeight(52)
        save_btn.setAutoDefault(False)
        save_btn.setDefault(False)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        rl.addWidget(save_btn)

        root.addWidget(right, stretch=35)

    def _stat_card(self, label: str, value: str, color: str) -> QWidget:
        card = QWidget()
        card.setObjectName("summaryStatCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(0)

        lbl = QLabel(label)
        lbl.setObjectName("summaryStatLabel")

        val_lbl = QLabel(value)
        val_lbl.setObjectName("summaryStatValue")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setStyleSheet(f"color: {color}; background: transparent;")

        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val_lbl)
        return card
