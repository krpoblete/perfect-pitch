from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

class HandSelector(QWidget):
    """Two-button RHP / LHP toggle."""
    changed = pyqtSignal(str)  # emits "RHP" or "LHP" when the user clicks

    def __init__(self, default: str = "RHP", parent=None):
        super().__init__(parent)
        self._hand = default
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
 
        self._rhp_btn = QPushButton("RHP")
        self._rhp_btn.setFixedHeight(42)
        self._rhp_btn.setCheckable(True)
        self._rhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rhp_btn.clicked.connect(lambda: self._select("RHP"))
 
        self._lhp_btn = QPushButton("LHP")
        self._lhp_btn.setFixedHeight(42)
        self._lhp_btn.setCheckable(True)
        self._lhp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lhp_btn.clicked.connect(lambda: self._select("LHP"))
 
        layout.addWidget(self._rhp_btn)
        layout.addWidget(self._lhp_btn)
 
        self._apply(self._hand, emit=False)

    # public
    def hand(self) -> str:
        """Return the currently selected hand: 'RHP' or 'LHP'."""
        return self._hand
 
    def set_hand(self, hand: str, emit: bool = False):
        """Programmatically set the selected hand without triggering the signal
        (unless emit=True is passed explicitly)."""
        self._apply(hand, emit=emit)
 
    def set_enabled_both(self, enabled: bool):
        """Enable or disable both buttons at once."""
        self._rhp_btn.setEnabled(enabled)
        self._lhp_btn.setEnabled(enabled)
 
    def set_disabled_style(self, disabled: bool):
        """Switch both buttons to/from the disabled QSS object name."""
        name = "handBtnDisabled" if disabled else None
        for btn, active_hand in [(self._rhp_btn, "RHP"), (self._lhp_btn, "LHP")]:
            if disabled:
                btn.setObjectName("handBtnDisabled")
                btn.setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                is_active = self._hand == active_hand
                btn.setObjectName("handBtnActive" if is_active else "handBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # private
    def _select(self, hand: str):
        self._apply(hand, emit=True)
 
    def _apply(self, hand: str, emit: bool):
        self._hand = hand
        self._rhp_btn.setChecked(hand == "RHP")
        self._lhp_btn.setChecked(hand == "LHP")
        self._rhp_btn.setObjectName("handBtnActive" if hand == "RHP" else "handBtn")
        self._lhp_btn.setObjectName("handBtnActive" if hand == "LHP" else "handBtn")
        for btn in (self._rhp_btn, self._lhp_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if emit:
            self.changed.emit(hand)
