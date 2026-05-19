from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit
from PyQt6.QtCore import Qt
from src.utils.icons import get_icon

class AuthBasePage(QWidget):
    # Logo Row
    def _logo_row(self) -> QHBoxLayout:
        """Return a horizontal layout containing the app logo and name."""
        row = QHBoxLayout()
        row.setSpacing(2)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("logoIcon")
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setPixmap(
            get_icon("ball-baseball", color="#ffffff", size=22).pixmap(22, 22)
        )

        text_lbl = QLabel("<u>PERFECT PITCH</u>.")
        text_lbl.setObjectName("logoText")
        text_lbl.setTextFormat(Qt.TextFormat.RichText)

        row.addWidget(icon_lbl)
        row.addWidget(text_lbl)
        row.addStretch()
        return row
    
    # Field Helpers
    def _label(self, text: str) -> QLabel:
        """Return a styled field-heading label."""
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl
 
    def _input(self, placeholder: str = "", password: bool = False) -> QLineEdit:
        """Return a styled auth input line edit."""
        inp = QLineEdit()
        inp.setObjectName("authInput")
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(48)
        if password:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        return inp 
