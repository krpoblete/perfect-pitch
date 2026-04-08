from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QPoint

class WindowButtons(QWidget):
    """
    Minimal minimize + close buttons for frameless windows.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("windowButtons")
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

       # Minimize
        min_btn = QPushButton("—")
        min_btn.setObjectName("winMinBtn")
        min_btn.setFixedSize(28, 24)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self._minimize)

        # Close
        close_btn = QPushButton("✕")
        close_btn.setObjectName("winCloseBtn")
        close_btn.setFixedSize(28, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self._close)

        layout.addWidget(min_btn)
        layout.addWidget(close_btn)
        self.adjustSize()

    def _get_window(self):
        w = self.parent()
        while w and not w.isWindow():
            w = w.parent()
        return w

    def _minimize(self):
        w = self._get_window()
        if w:
            w.showMinimized()

    def _close(self):
        w = self._get_window()
        if w:
            w.close()
