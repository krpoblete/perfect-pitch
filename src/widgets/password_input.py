from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from src.utils.icons import get_icon

EYE_COLOR = "#555555"
EYE_COLOR_HOVER = "#aaaaaa"

class PasswordInput(QWidget):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("passwordInputWrapper")
        self.setFixedHeight(48)
        self._visible = False
        self._build_ui(placeholder)

    def _build_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.line_edit = QLineEdit()
        self.line_edit.setObjectName("authInput")
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.line_edit.setFixedHeight(48)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("pwToggleBtn")
        self.toggle_btn.setFixedSize(36, 36)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setIcon(get_icon("eye", color=EYE_COLOR, size=18))
        self.toggle_btn.setIconSize(QSize(18, 18))
        self.toggle_btn.clicked.connect(self._toggle)

        self.line_edit.setTextMargins(0, 0, 36, 0)

        layout.addWidget(self.line_edit)

        self.toggle_btn.setParent(self.line_edit)
        self.toggle_btn.move(
            self.line_edit.width() - 38,
            (48 - 36) // 2
        )
        self.toggle_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.line_edit.setFixedWidth(self.width())
        self.toggle_btn.move(
            self.line_edit.width() - 38,
            (48 - 36) // 2
        )

    def _toggle(self):
        self._visible = not self._visible
        if self._visible:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setIcon(get_icon("eye-closed", color=EYE_COLOR, size=18))
        else:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setIcon(get_icon("eye", color=EYE_COLOR, size=18))

    def text(self) -> str:
        return self.line_edit.text()
    
    def clear(self):
        self.line_edit.clear()
