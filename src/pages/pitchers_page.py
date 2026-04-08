from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class PitchersPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentPage")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Pitchers")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addStretch()

    def refresh(self):
        pass
