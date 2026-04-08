from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class StartSessionPage(QWidget):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self.setObjectName("contentPage")
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Start Session")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Blank for now 
        layout.addStretch()

    def refresh(self):
        pass

