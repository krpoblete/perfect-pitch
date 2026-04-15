from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QKeyEvent

class ConfirmDialog(QDialog):
    def __init__(self, parent=None, title: str = "Confirm", message: str = "Are you sure?"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint) 
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("confirmRoot")
        self.setFixedSize(QSize(340, 152))
        self._result = False
        self._build_ui(title, message)
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        if parent:
            pr = parent.frameGeometry()
            self.move(
                pr.x() + (pr.width() - self.width()) // 2,
                pr.y() + (pr.height() - self.height()) // 2,
            )

    def _build_ui(self, title: str, message: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(0)

        # Title 
        title_lbl = QLabel(title)
        title_lbl.setObjectName("confirmTitle")
        layout.addWidget(title_lbl)

        layout.addSpacing(7)

        # Message
        msg_lbl = QLabel(message)
        msg_lbl.setObjectName("confirmMessage")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        no_btn = QPushButton("No")
        no_btn.setObjectName("confirmNoBtn")
        no_btn.setFixedSize(88, 36)
        no_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        no_btn.clicked.connect(self._on_no)

        yes_btn = QPushButton("Yes")
        yes_btn.setObjectName("confirmYesBtn")
        yes_btn.setFixedSize(88, 36)
        yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        yes_btn.clicked.connect(self._on_yes)

        btn_row.addWidget(yes_btn)
        btn_row.addWidget(no_btn)
        layout.addLayout(btn_row)

    def _on_yes(self):
        self._result = True
        self.accept()

    def _on_no(self):
        self._result = False
        self.reject()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._on_no()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_yes()
        else:
            super().keyPressEvent(event)

    def result_yes(self) -> bool:
        return self._result
