from pyqttoast import Toast, ToastPreset, ToastPosition
from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

_LABEL_OVERHEAD = 110
_TOAST_MIN_WIDTH = 400
_DURATION = 3500

_active_toast: Toast | None = None

def _restart_duration(toast: Toast):
    timers = toast.findChildren(QTimer)
    for timer in timers:
        if timer.isSingleShot():
            timer.stop()
            timer.start(_DURATION)
            break

def show_toast(parent, message: str, preset: ToastPreset = ToastPreset.ERROR_DARK):
    global _active_toast

    if _active_toast is not None:
        try:
            for label in _active_toast.findChildren(QLabel):
                if label.text() and label.text() != "":
                    label.setText(message)
                    label.updateGeometry()
                    break
            _restart_duration(_active_toast)
            return
        except RuntimeError:
            _active_toast = None

    Toast.setPosition(ToastPosition.BOTTOM_LEFT)
    Toast.setPositionRelativeToWidget(parent)

    toast = Toast(parent)
    toast.applyPreset(preset)

    toast.setTitle("")
    toast.setText(message)
    toast.setTextFont(QFont("Segoe UI", 12))

    toast.setDuration(_DURATION)
    toast.setShowDurationBar(True)
    # toast.setShowCloseButton(False)
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

    _active_toast = toast

    def _on_close():
        global _active_toast
        _active_toast = None

    toast.closed.connect(_on_close)

def toast_error(parent, message: str):
    show_toast(parent, message, ToastPreset.ERROR_DARK)

def toast_success(parent, message: str):
    show_toast(parent, message, ToastPreset.SUCCESS_DARK)

def toast_warning(parent, message: str):
    show_toast(parent, message, ToastPreset.WARNING_DARK)

def toast_info(parent, message: str):
    show_toast(parent, message, ToastPreset.INFORMATION_DARK)
