from pyqttoast import Toast, ToastPreset, ToastPosition
from PyQt6.QtWidgets import QLabel, QSizePolicy 
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

_LABEL_OVERHEAD = 110
_TOAST_MIN_WIDTH = 400

_SHORT_DURATION = 3000
_LONG_DURATION = 5000
_CHAR_THRESHOLD = 40

Toast.setMaximumOnScreen(2)

def _get_duration(message: str) -> int:
    return _LONG_DURATION if len(message) > _CHAR_THRESHOLD else _SHORT_DURATION

def show_toast(parent, message: str, preset: ToastPreset = ToastPreset.ERROR_DARK):
    Toast.setPosition(ToastPosition.BOTTOM_LEFT)
    Toast.setPositionRelativeToWidget(parent)

    toast = Toast(parent)
    toast.applyPreset(preset)

    toast.setTitle("")
    toast.setText(message)
    toast.setTextFont(QFont("Segoe UI", 12))

    toast.setDuration(_get_duration(message))
    toast.setResetDurationOnHover(False)
    toast.setShowDurationBar(True)
    toast.setShowCloseButton(True)
    toast.setStayOnTop(False)

    toast.setMinimumWidth(_TOAST_MIN_WIDTH)
    toast.setMaximumWidth(_TOAST_MIN_WIDTH)
    toast.setTextSectionMarginBottom(14)

    toast.show()

    label_w = toast.width() - _LABEL_OVERHEAD
    for label in toast.findChildren(QLabel):
        if label.text() == message:
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.setMinimumWidth(label_w)
            label.setMaximumWidth(label_w)
            label.setMinimumHeight(0)
            label.setMaximumHeight(16777215)
            label.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.MinimumExpanding
            )
            label.updateGeometry()
            break

def dismiss_active_toast():
    """Forcefully dismiss any active toast — call before window transitions."""
    try:
        Toast.reset()
    except Exception:
        pass

def toast_error(parent, message: str):
    show_toast(parent, message, ToastPreset.ERROR_DARK)

def toast_success(parent, message: str):
    show_toast(parent, message, ToastPreset.SUCCESS_DARK)

def toast_warning(parent, message: str):
    show_toast(parent, message, ToastPreset.WARNING_DARK)

def toast_info(parent, message: str):
    show_toast(parent, message, ToastPreset.INFORMATION_DARK)
