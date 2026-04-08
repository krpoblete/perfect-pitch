from pyqttoast import Toast, ToastPreset, ToastPosition
from PyQt6.QtWidgets import QLabel, QSizePolicy, QDialog
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QSize

def show_toast(parent, title: str, message: str, 
               preset: ToastPreset = ToastPreset.ERROR_DARK):
    """Show a toast with title + message."""
    Toast.setPosition(ToastPosition.BOTTOM_LEFT)
    Toast.setPositionRelativeToWidget(parent)

    toast = Toast(parent)
    toast.applyPreset(preset)
    toast.setTitle(title)
    toast.setText(message)
    toast.setTitleFont(QFont("Arial", 9, QFont.Weight.Bold))
    toast.setTextFont(QFont("Arial", 9))
    toast.setDuration(3500)
    toast.setShowDurationBar(True)
    toast.setShowCloseButton(False)
    toast.setStayOnTop(False)
    toast.setTextSectionMarginBottom(8)
    toast.show()

    for label in toast.findChildren(QLabel):
        if label.text() in (title, message) and label.text():
            label.setWordWrap(True)
            label.setMinimumWidth(310)
            label.setMaximumWidth(310)
            label.setMinimumHeight(0)
            label.setMaximumHeight(16777215)
            label.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Preferred
            )

    cur_w = toast.width()
    cur_h = toast.height()
    QDialog.setFixedSize(toast, QSize(cur_w, cur_h + 6))

    # for child in toast.children():
    #     from PyQt6.QtWidgets import QWidget as _QW
    #     if isinstance(child, _QW) and child is not toast:
    #         iw, ih = child.width(), child.height()
    #         if iw > 0 and ih > 0:
    #             child.setFixedSize(iw, ih + EXTRA_H)
    #             break

def toast_error(parent, message: str):
    show_toast(parent, "Error", message, ToastPreset.ERROR_DARK)

def toast_success(parent, message: str):
    show_toast(parent, "Success", message, ToastPreset.SUCCESS_DARK)

def toast_warning(parent, message: str):
    show_toast(parent, "Warning", message, ToastPreset.WARNING_DARK)

def toast_info(parent, message: str):
    show_toast(parent, "Info", message, ToastPreset.INFORMATION_DARK)
